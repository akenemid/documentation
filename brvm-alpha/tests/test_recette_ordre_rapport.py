"""Régressions de la recette finale du 22/11/2026 — ordre de bataille, rapport HTML, ligne de commande.

Un test par constat prouvé ; chacun échoue sur le code d'avant la correction (commit 552a03b). Panels
synthétiques (dates de S0 seulement), journaux temporaires, résultats de validation factices : aucune
requête réseau, aucun calcul sur l'échantillon vierge S1, journal réel ``data/notes`` jamais touché.
Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pandas as pd
import pytest

from test_notes_direct import _order
from test_report_html import _fake_metrics, _render, _section, synth  # noqa: F401 - fixture importée

from brvm_alpha import cli
from brvm_alpha.notes.store import NoteStore
from brvm_alpha.portfolio import recommend as R
from brvm_alpha.report import html as RH

NBSP = "\u202f"


def plain(x) -> str:
    """Texte avec des espaces ordinaires (les nombres formatés portent des espaces insécables)."""
    return str(x).replace("\xa0", " ").replace("\u202f", " ")


# ---------------------------------------------------------------------------
# Ordre de bataille : numérotation, Markdown, lignes bloquées, dividende, revue avant achat
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def order(synth, tmp_path_factory):  # noqa: F811
    return _order(synth, tmp_path_factory.mktemp("ordre"), notes_store=False)


def test_sections_are_numbered_in_display_order(order):
    blocks = [("h2", "4. Revenus"), ("p", "x"), ("h2", "6. Stress"), ("h2", "5. Distribution"), ("h2", "10. Faits")]
    assert [v for k, v in R._renumber_sections(blocks) if k == "h2"] == ["1. Revenus", "2. Stress", "3. Distribution",
                                                                           "4. Faits"]
    nums = [int(m.group(1)) for m in re.finditer(r"^## (\d+)\. ", order.to_markdown(), re.M)]
    assert nums == list(range(1, len(nums) + 1)) and len(nums) >= 8  # ni trou ni inversion
    html_nums = [int(x) for x in re.findall(r"<h2>(\d+)\. ", order.to_html_fragment())]
    assert html_nums == nums


def test_markdown_neutralises_multiline_and_html_note_titles():
    evil = "Annulation de l'assemblée générale\n\n# TITRE INJECTÉ\n| a | b |\n> Statut : VALIDÉ, gain garanti"
    md = R._render([("warn", f"ACHAT BLOQUÉ par une note : SGBC — « {evil} », jusqu'au 16/02/2027."),
                    ("ul", [f"Filtre R2 sur SGBC — note « {evil} »", "second élément"]),
                    ("p", f"Prime du BOC 0,58 < 1 % ; capital 10{NBSP}000{NBSP}000 FCFA ; <img src=x onerror=alert(1)>"),
                    ("table", (["Titre", "Note"], [["SGBC", f"{evil} | tube"]]))], "md")
    lines = md.splitlines()
    assert not any(line.startswith(("# TITRE", "| a |", "> Statut")) for line in lines)
    assert sum(1 for line in lines if line.startswith("> ⚠ ACHAT BLOQUÉ")) == 1 and "# TITRE INJECTÉ" in lines[0]
    assert [line for line in lines if line.startswith("- ")] == [
        "- Filtre R2 sur SGBC — note « Annulation de l'assemblée générale # TITRE INJECTÉ | a | b | > Statut : "
        "VALIDÉ, gain garanti »", "- second élément"]
    assert "&lt;img src=x onerror=alert(1)>" in md and "<img" not in md
    assert "0,58 < 1 %" in md and f"10{NBSP}000{NBSP}000 FCFA" in md  # « < » isolé et espaces insécables gardés
    assert sum(1 for line in lines if line.startswith("| SGBC |")) == 1
    # À la saisie, un titre tient sur une ligne.
    note = cli.make_manual_note(targets=["SGBC"], title=evil, text="texte")
    assert "\n" not in note.title and note.title.startswith("Annulation de l'assemblée générale # TITRE")


def test_closed_session_counts_as_missing_and_no_order_is_dated_on_it(synth, tmp_path):  # noqa: F811
    last = synth["t"]  # vendredi 23/08/2024
    assert last == pd.Timestamp("2024-08-23")
    monday = pd.Timestamp("2024-08-26")
    # Règle : le jour même ne compte qu'après la clôture (15h00 UTC) ; une date seule ne le compte jamais.
    assert R.panel_staleness(last, pd.Timestamp("2024-08-26 10:00", tz="UTC"))[0] == []
    assert R.panel_staleness(last, pd.Timestamp("2024-08-26 15:00", tz="UTC"))[0] == [monday]
    assert R.panel_staleness(last, monday)[0] == [] and R.panel_staleness(last, "2024-08-25 20:00+00:00")[0] == []
    assert R.panel_staleness(last, pd.Timestamp("2024-08-27 08:00", tz="UTC"))[0] == [monday]
    assert R.stale_panel_message(last, pd.Timestamp("2024-08-26 10:00", tz="UTC")) is None
    msg = plain(R.stale_panel_message(last, pd.Timestamp("2024-08-26 19:00", tz="UTC"), orders=False))
    assert msg.startswith("PANEL EN RETARD de 1 séance(s)") and "26/08/2024" in msg and "close depuis 15h00 UTC" in msg
    assert "python -m brvm_alpha update" in msg
    # Lundi soir : avertissement en tête, ordres périmés, exécution au plus tôt le mardi.
    evening = _order(synth, tmp_path, notes_store=False, today=pd.Timestamp("2024-08-26 19:00", tz="UTC"))
    assert evening.avertissements[0].startswith("PANEL EN RETARD de 1 séance(s)")
    assert evening.execution["perime"] is True
    assert pd.Timestamp(evening.execution["premiere_seance"]) == pd.Timestamp("2024-08-27")
    # Lundi matin : séance ouverte, pas de retard, exécution le jour même.
    morning = _order(synth, tmp_path, notes_store=False, today=pd.Timestamp("2024-08-26 08:00", tz="UTC"))
    assert not any("PANEL EN RETARD" in w for w in morning.avertissements) and not morning.execution["perime"]
    assert pd.Timestamp(morning.execution["premiere_seance"]) == monday


def test_execution_never_precedes_the_session_where_notes_apply(synth, tmp_path):  # noqa: F811
    # Notes connues le lundi à 10h00 (coupure de 09h00 passée) : appliquées le mardi, comme l'exécution.
    known = pd.Timestamp("2024-08-26 10:00", tz="UTC")
    o = _order(synth, tmp_path, notes_store=NoteStore(tmp_path / "notes"), today=known, notes_known_at=known)
    assert pd.Timestamp(o.execution["premiere_seance"]) == pd.Timestamp("2024-08-27")
    line = (o.declencheurs.get("notes") or {}).get("ligne") or ""
    assert "appliquées à la séance du 27/08/2024" in line
    # Avant la coupure : même séance, le lundi.
    early = pd.Timestamp("2024-08-26 08:00", tz="UTC")
    o2 = _order(synth, tmp_path, notes_store=NoteStore(tmp_path / "notes"), today=early, notes_known_at=early)
    assert pd.Timestamp(o2.execution["premiere_seance"]) == pd.Timestamp("2024-08-26")


def test_blocked_held_line_is_deducted_from_the_investable_budget(synth, tmp_path, order):  # noqa: F811
    t = synth["t"]
    # Titre hors de la sélection, détenu et suspendu à la date : aucun ordre possible, poids cible nul.
    target = {r.symbole for r in order.lignes.itertuples(index=False) if r.cibles > 0}
    close = synth["panels"]["close_raw"].loc[t]
    sym = next(s for s in close.index if s not in target and close[s] > 0)
    qty = int(1_000_000 // close[sym])  # environ 10 % de la valeur
    panels = dict(synth["panels"])
    status = panels["status"].copy()
    status.loc[t, sym] = "suspended"
    panels["status"] = status
    o = _order(synth, tmp_path, notes_store=False, panels=panels, holdings={sym: qty})
    line = o.lignes.set_index("symbole").loc[sym]
    assert int(line["cibles"]) == qty and line["sens"] == "aucun"
    k = o.couts
    assert k["investi_pct"] <= k["cible_specification"] + 1e-9  # titres après ordres ≤ 98 % de la valeur
    assert k["liquidites_apres"] >= 0.012 * o.valeur_portefeuille  # la réserve de liquidités reste entière
    assert k["reliquat_arrondi"] >= 0
    msg = next(m for m in o.messages_modele if m.startswith("Ligne(s) bloquée(s)"))
    assert sym in msg and "déduite(s) du budget investissable" in msg
    assert "reliquat de l'arrondi vers le bas −" not in plain(o.to_markdown())


def test_dividend_remark_when_the_boc_column_differs_from_the_retained_amount():
    t, ex = pd.Timestamp("2026-11-20"), pd.Timestamp("2026-05-05")
    idx = pd.to_datetime(["2026-05-04", "2026-05-05", "2026-11-20"])
    panels = {"last_div_net": pd.DataFrame({"BOAC": [640.0, 597.53, 597.53], "SNTS": [174.0, 174.0, 174.0]}, index=idx)}
    txt = plain(R._boc_dividend_remark(panels, "BOAC", t, 594.53, 594.53, 1.0, ex))
    assert "BOC du 20/11/2026 : dernier dividende 597,53 FCFA" in txt and "montant retenu 594,53 FCFA" in txt
    assert "ligne (d) du détachement du 05/05/2026" in txt and "§3.1" in txt
    assert R._boc_dividend_remark(panels, "SNTS", t, 174.0, 174.0, 1.0, ex) == ""  # égal au BOC : rien à dire
    assert R._boc_dividend_remark(panels, "BOAC", t, 594.53, 594.53, 10.0, ex) == ""  # division : non comparable
    assert R._boc_dividend_remark({}, "BOAC", t, 594.53, 594.53, 1.0, ex) == ""


def test_lines_to_buy_under_the_review_threshold_are_flagged_in_the_order(order):
    dd = order.declencheurs["drawdown"]
    assert "revues_avant_achat" in dd and "revues_lignes" in dd
    dd["revues_avant_achat"] = [{"symbole": "NSBC", "relatif_63": -0.294}]
    try:
        md = plain(order.to_markdown())
    finally:
        dd["revues_avant_achat"] = []
    assert "À revoir avant achat NSBC : −29,4 % contre le TR sur 63 séances (seuil de revue −25 %, §9.1)" in md
    assert "l'achat reste proposé" in md


def test_filter_legend_and_inclination_notes():
    rows = [{"symbole": "NSBC", "filtres": "R10"}, {"symbole": "BOAB", "filtres": "R11×1"},
            {"symbole": "TTLC", "filtres": "R12"}]
    legend = plain(R._filter_legend(rows))
    assert legend.startswith("R10 : résultat net en baisse de 25 % ou plus") and "R11 : drapeau des financières" in legend
    assert "R12 : drapeau des non financières" in legend and "« ×N » : nombre de drapeaux levés" in legend
    assert R._filter_legend([]) == ""
    table = pd.DataFrame([{"note_id": "ab" * 20, "title": "Marché trop cher", "targets": ["IDX:BRVM-C"], "manual": True,
                           "known_at": pd.Timestamp("2026-11-22 16:00", tz="UTC"), "published_at": None,
                           "stance": "baissier", "conviction": 5.0},
                          {"note_id": "cd" * 20, "title": "Autre", "targets": ["SNTS"], "manual": False,
                           "known_at": None, "published_at": pd.Timestamp("2026-11-20", tz="UTC"), "stance": None,
                           "conviction": None}])
    notes = R._tilt_notes({"overlays": {"tilt_notes": ["ab" * 20]}, "table": table})
    assert notes == [{"note_id": "ab" * 20, "date": pd.Timestamp("2026-11-22 16:00", tz="UTC"),
                      "titre": "Marché trop cher", "cibles": ["IDX:BRVM-C"], "avis": "baissier", "conviction": 5}]
    assert R._tilt_notes(None) == [] and R._tilt_notes({"overlays": {}, "table": table}) == []


# ---------------------------------------------------------------------------
# Rapport HTML
# ---------------------------------------------------------------------------


def _metrics_with_rerun() -> dict:
    return {
        "t0": "2017-08-01T00:00:00", "fin": "2022-11-16T00:00:00",
        "sous_periodes": [["2017-08-01T00:00:00", "2019-12-31T00:00:00"], ["2020-01-01T00:00:00", "2022-11-18T00:00:00"]],
        "execution": {
            "commit": "1819997bc8f01ef6977a7db6dc3ddac0c2875401", "empreinte_config": "f1582ed8e9fa1c85",
            "horodatage_utc": "2026-11-22T12:13:28+00:00",
            "empreinte_controle": {"conforme": True, "preenregistree_independante": False,
                                   "etat_fige": {"commit": "a2bfeb4c9b09c6a97f1208dfd7d585146455b651"},
                                   "reference_preenregistrement": {"commit": "751d1be729ac1501fe672eb47be084c794dac7a9"}},
            "relance": {"motif": "Bogues démontrés par l'audit du 22/11/2026 : semaines multi-séances retirées du "
                                 "chaînage ; garde-fou de couverture tautologique. Aucun paramètre de stratégie modifié.",
                        "precedent": "reports/validation_S1/precedent_20261122T121328Z"}},
        "precedent": {"dossier": "reports/validation_S1/precedent_20261122T121328Z", "t0": "2017-08-01T00:00:00",
                      "execution": {"commit": "a2bfeb4c9b09c6a97f1208dfd7d585146455b651",
                                    "horodatage_utc": "2026-11-22T09:56:27+00:00"},
                      "statuts": {"A": "REJETÉ", "REF": "REJETÉ"}},
        "variantes": {"A": {"statut": "REJETÉ", "run_id": "A_central_10M"},
                      "REF": {"statut": "REJETÉ", "run_id": "REF_central_10M"}},
        "runs": {"A_central_10M": {"actif_tr_an": -0.093, "rendement_an": -0.14, "ir_tr": -1.14},
                 "REF_central_10M": {"actif_tr_an": -0.056, "part_investie_moyenne": 0.8199}},
    }


def test_s1_section_says_the_test_was_rerun_once_and_why():
    m = _metrics_with_rerun()
    box = plain(RH._rerun_box(m))
    assert "Test unique, relancé une fois pour un défaut de mesure prouvé (D12)." in box
    assert "Premier passage le 22/11/2026 09:56 UTC (commit a2bfeb4), relance le 22/11/2026 12:13 UTC (commit 1819997)" in box
    assert "semaines multi-séances retirées du chaînage" in box and "Aucun paramètre de stratégie modifié" in box
    assert "Les statuts des variantes et de la référence sont les mêmes aux deux passages." in box
    assert "precedent_20261122T121328Z" in box and "tentatives.md" in box
    # L'empreinte n'est pas dite « pré-enregistrée » quand elle ne l'est pas.
    note = plain(RH._fingerprint_note(m["execution"]))
    assert "identique au pré-enregistrement" not in note
    assert note == (" (identique à l'état figé a2bfeb4 ; référence de pré-enregistrement : commit 751d1be ; pas une "
                    "valeur pré-enregistrée indépendante)")
    assert RH._fingerprint_note({"empreinte_controle": {"conforme": True, "preenregistree_independante": True}}) == \
        " (identique au pré-enregistrement)"
    # Un test exécuté une seule fois n'affiche pas l'encadré.
    once = {k: v for k, v in m.items() if k != "precedent"}
    once["execution"] = {k: v for k, v in m["execution"].items() if k != "relance"}
    assert RH._rerun_box(once) is None and RH._rerun_info(once) is None


def test_s1_interpretation_explains_ref_and_recalls_the_rerun():
    txt = plain(" ".join(RH._interpretation(_metrics_with_rerun())))
    assert "c'est le coût de la réplication" not in txt
    assert "REF n'a été investi qu'à 82 % en moyenne sur S1 (cible 98 %)" in txt
    assert "liquidités d'août à octobre 2021" in txt and "points ouverts" in txt
    assert "un seul test (relancé une fois pour un défaut de mesure prouvé, D12" in txt


def test_sub_period_end_is_capped_at_the_end_of_the_window():
    assert plain(RH._sub_end("2022-11-18T00:00:00", "2022-11-16T00:00:00")) == "16/11/2022 (semaine du vendredi 18/11/2022)"
    assert RH._sub_end("2019-12-31T00:00:00", "2022-11-16T00:00:00") == "31/12/2019"


def test_aes_lambda_cap_uses_the_economic_exposure():
    lines = [{"symbole": "SNTS", "secteur": "TEL", "pays": "SN", "cibles": 629, "poids_cible": 0.254445},
             {"symbole": "CBIBF", "secteur": "FIN", "pays": "BF", "cibles": 20, "poids_cible": 0.0554},
             {"symbole": "BOABF", "secteur": "FIN", "pays": "BF", "cibles": 27, "poids_cible": 0.0213},
             {"symbole": "ONTBF", "secteur": "TEL", "pays": "BF", "cibles": 42, "poids_cible": 0.012085}]
    caps = {"aes": {"bloc AES (siège)": 0.106157, "bloc AES (exposition λ)": 0.168334}}
    od = {"lignes": lines, "explications": [{"symbole": r["symbole"], "statut": "retenu", "plafonds": caps} for r in lines]}
    rows = {str(r[0]): [plain(c) for c in r] for r in RH._active_constraints(od)}
    assert rows["Bloc AES (siège)"][1:3] == ["10,6 %", "8,9 %"]
    # 8,88 % (siège BF) + 0,238 × 25,44 % (SNTS exposé au Mali) = 14,9 % : avant, 8,9 % était affiché deux fois.
    assert rows["Bloc AES (exposition λ)"][1:3] == ["16,8 %", "14,9 %"]
    assert RH._aes_lambda_load(lines) == pytest.approx(0.0888 + 0.238 * 0.254445, abs=2e-4)


def test_irvm_rate_is_shown_once_and_per_column_says_what_it_is():
    cell = plain(RH._irvm_cell({"irvm": 1531, "taux_irvm_prevu": 0.125, "irvm_note": "12,5 % [NON VÉRIFIÉ]"}))
    assert cell.count("12,5 %") == 1 and "[NON VÉRIFIÉ]" in cell
    simple = plain(RH._irvm_cell({"irvm": 2027, "taux_irvm_prevu": 0.12, "irvm_note": ""}))
    assert simple.count("12,0 %") == 1
    assert "publié (BOC)" in RH._per_cell("IDX:BRVM-C", {"per": 15.79})
    ind = plain(RH._per_cell("IDX:SECT:IND", {"per": 42.82, "per_index": 131.01}))
    assert "42,8" in ind and "médian ; publié 131,0" in ind


@pytest.fixture(scope="module")
def rep_rerun(synth):  # noqa: F811
    """Rapport sur des résultats S1 FACTICES complétés d'une relance (aucune exécution, nombres inventés)."""
    vdir = _fake_metrics(synth["tmp"] / "val_relance", "REJETÉ")
    path = vdir / "metrics.json"
    m = json.loads(path.read_text(encoding="utf-8"))
    extra = _metrics_with_rerun()
    m["execution"] = {**(m.get("execution") or {}), **extra["execution"]}
    m["precedent"] = extra["precedent"]
    m["sous_periodes"] = extra["sous_periodes"]
    path.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return _render(synth, validation_dir=vdir, registry_path=synth["reg_yes"])


def test_report_puts_the_rerun_and_the_limits_up_front(rep_rerun):
    html = plain(rep_rerun.html if hasattr(rep_rerun, "html") else str(rep_rerun))
    s1 = _section(html, "s1")
    assert "Exécution unique" not in s1 and "(identique au pré-enregistrement)" not in s1
    assert "Relance motivée (D12) : commit 1819997bc8f0" in s1
    assert "pas une valeur pré-enregistrée indépendante" in s1
    # L'encadré de relance est en tête de section, avant les tuiles et les tableaux.
    assert s1.index("Test unique, relancé une fois") < s1.index("t0 (D2)") < s1.index("Les 9 variantes")
    assert "16/11/2022 (semaine du vendredi 18/11/2022)" in s1
    top = _section(html, "bandeau")
    assert "Limites à lire d'abord." in top or "Limites à lire d&#x27;abord." in top
    assert 'href="#methode">Méthode et limites</a>' in top and "relancé une fois" in top
    meth = _section(html, "methode")
    assert "<h3>Points ouverts</h3>" in meth and "Indice TR des signaux non strictement daté" in meth
    assert "Plancher D1 des filtres d'univers" in meth.replace("&#x27;", "'")
    assert "base 100 au 02/01/2025, publié au BOC depuis le 02/01/2026" in meth
    assert "officiel depuis le 02/01/2025" not in html
    assert "12 mois du Composite prix sont négatives" in meth


def test_report_order_section_wording(rep_rerun):
    html = plain(rep_rerun.html if hasattr(rep_rerun, "html") else str(rep_rerun))
    ordre = _section(html, "ordre")
    assert "BRVM 0,20 % et DC/BR 0,10 % (faits, barèmes) ; courtage 0,80 % et taxe 18 %" in ordre
    assert "courtage, TVA, BRVM 0,20 %, DC/BR 0,10 % (faits)" not in ordre
    assert "Évaluation des indices non demandée" not in html
    assert "Évaluation des indices : voir la section « Indices » de ce rapport." in html
    assert "titres cotés à la date" in _section(html, "univers") and "titres au panel à la date" not in html
    dist = _section(html, "distribution")
    assert "repère réalisé : 43 % des fenêtres de 12 mois du Composite prix" in dist


# ---------------------------------------------------------------------------
# Ligne de commande
# ---------------------------------------------------------------------------


@pytest.fixture()
def clock(monkeypatch):
    now = pd.Timestamp("2026-11-22 16:52", tz="UTC")
    monkeypatch.setattr(cli, "now_utc", lambda: now)
    monkeypatch.setattr(cli, "last_session", lambda panel_dir=None: pd.Timestamp("2026-11-20"))
    return now


def test_notes_instant_refuses_a_future_instant(clock):
    with pytest.raises(ValueError, match="dans le futur"):
        cli.notes_instant(None, "2026-11-22T21:00")
    with pytest.raises(ValueError, match="dans le futur"):
        cli.notes_instant(None, "2026-11-23")
    assert cli.notes_instant(None, "2026-11-22T12:00") == pd.Timestamp("2026-11-22 12:00", tz="UTC")
    assert cli.notes_instant(None, "2026-11-22") == clock  # date d'aujourd'hui : « maintenant », pas 23h59
    assert cli.notes_instant(None, "2026-11-21") == pd.Timestamp("2026-11-21 23:59:59.999999", tz="UTC")
    assert cli.notes_instant(None, None) == clock


def test_cli_refuses_a_future_notes_instant_with_exit_code_2(clock, tmp_path, capsys):
    assert cli.main(["recommend", "--capital", "10M", "--notes-au", "2026-11-22T21:00", "--racine", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert "--notes-au 22/11/2026 21:00 UTC est dans le futur (il est 22/11/2026 16:52 UTC)" in err


@pytest.mark.parametrize("argv", [
    ["indices"], ["indices", "dossier", "IDX:BRVM-C"], ["explain", "SNTS"], ["recommend", "--capital", "10M"],
    ["report", "--capital", "10M"], ["serve", "--port", "0"], ["notes", "list"], ["notes", "lire", "--hors-ligne"],
])
def test_missing_notes_directory_is_refused_for_reading_commands(argv, clock, tmp_path, capsys, monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("aucun calcul ne doit être lancé sur un journal introuvable")

    from brvm_alpha.ui import server

    monkeypatch.setattr(R, "recommend", forbidden)
    monkeypatch.setattr(server, "make_server", forbidden)
    missing = tmp_path / "notes_pristin"  # faute de frappe : dossier inexistant
    assert cli.main(argv + ["--racine", str(missing)]) == 2
    err = capsys.readouterr().err
    assert "journal des notes introuvable" in err and str(missing) in err
    assert not missing.exists()  # rien n'est créé


def test_notes_add_still_creates_a_new_journal(tmp_path, capsys):
    root = tmp_path / "nouveau"
    assert cli.main(["notes", "add", "--racine", str(root), "--cible", "SNTS", "--titre", "Première note"]) == 0
    assert (root / "notes.jsonl").exists()
    capsys.readouterr()


def test_report_without_panel_fails_with_the_next_step(tmp_path, capsys):
    out = tmp_path / "r.html"
    assert cli.main(["report", "--capital", "10M", "--panel-dir", str(tmp_path / "pas_de_panel"), "--sortie", str(out)]) == 1
    err = capsys.readouterr().err
    assert "panel introuvable" in err and "python -m brvm_alpha update" in err and "python -m brvm_alpha panel" in err
    assert not out.exists()


def test_missing_panel_messages_name_the_commands_not_an_internal_function(tmp_path, capsys, monkeypatch):
    def boom(args):
        raise FileNotFoundError(f"{tmp_path}/equities.parquet introuvable : lancer build_panel() d'abord")

    monkeypatch.setitem(cli.COMMANDS, "universe", boom)
    assert cli.main(["universe"]) == 1
    err = capsys.readouterr().err
    assert "build_panel()" not in err and "panel introuvable" in err
    assert "lancer python -m brvm_alpha update" in err and "puis python -m brvm_alpha panel" in err
    assert cli.main(["panel", "--boc-dir", str(tmp_path / "pas_de_boc"), "--panel-dir", str(tmp_path / "p")]) == 1
    assert "python -m brvm_alpha update" in capsys.readouterr().err


def test_broken_pipe_ends_quietly(capsys, monkeypatch):
    def piped(args):
        raise BrokenPipeError(32, "Broken pipe")

    monkeypatch.setitem(cli.COMMANDS, "universe", piped)
    monkeypatch.setattr(os, "dup2", lambda *a, **k: None)  # ne pas rediriger la sortie du lanceur de tests
    assert cli.main(["universe"]) == 0  # avant : BrokenPipeError remontait avec une trace Python
    assert "Traceback" not in capsys.readouterr().err


def test_enrich_report_distinguishes_an_empty_journal(tmp_path):
    read_all = cli.format_enrich_report({"n_candidates": 0, "n_read": 0, "n_enriched": 0, "n_scanned": 0, "n_failed": 0,
                                         "n_requests": 0})
    assert "les documents utiles ont déjà été lus" in read_all[-1]
    empty = cli.format_enrich_report({"n_candidates": 0, "n_read": 0, "n_enriched": 0, "n_scanned": 0, "n_failed": 0,
                                      "n_requests": 0, "journal_vide": True})
    assert "le journal des notes est vide" in empty[-1] and "notes research" in empty[-1]
    assert "déjà été lus" not in empty[-1]
    (tmp_path / "vide").mkdir()
    rep, lines = cli.run_enrich(NoteStore(tmp_path / "vide"), max_docs=5, offline=True)
    assert rep is not None and rep.get("journal_vide") is True and "journal des notes est vide" in "\n".join(lines)


def test_duplicate_manual_note_is_refused_on_the_command_line(tmp_path, capsys):
    root = str(tmp_path / "notes")
    argv = ["notes", "add", "--racine", root, "--cible", "SNTS", "--titre", "Doublon non daté", "--texte",
            "Dividende relevé.", "--avis", "haussier", "--conviction", "2"]
    assert cli.main(argv) == 0
    assert "Note enregistrée : " in capsys.readouterr().out
    assert cli.main(argv) == 2
    err = capsys.readouterr().err
    assert "note déjà enregistrée" in err and "--forcer" in err and len(NoteStore(root)) == 1
    assert cli.main(argv + ["--forcer"]) == 0 and len(NoteStore(root)) == 2
    capsys.readouterr()
    # Même identifiant (date de publication donnée) : dit en clair, rien n'est ajouté.
    dated = ["notes", "add", "--racine", root, "--cible", "ORAC", "--titre", "Note datée", "--publie-le", "2026-11-18"]
    assert cli.main(dated) == 0 and "Note enregistrée : " in capsys.readouterr().out
    assert cli.main(dated + ["--forcer"]) == 0
    assert "Note déjà enregistrée : " in capsys.readouterr().out and len(NoteStore(root)) == 3


def test_veto_option_is_documented_and_announced(tmp_path, capsys):
    with pytest.raises(SystemExit):
        cli.main(["notes", "add", "--help"])
    help_txt = capsys.readouterr().out
    assert "--veto" in help_txt and "exclues des achats" in help_txt
    root = str(tmp_path / "notes")
    assert cli.main(["notes", "add", "--racine", root, "--cible", "ORAC", "--titre", "Exclusion ORAC", "--veto"]) == 0
    out = capsys.readouterr().out
    assert "Veto posé sur ORAC : aucun achat à partir de la séance du" in out and "pendant 20 séances" in out
    assert "Étiquettes : veto" in out and "source saisie manuelle" in out
    assert cli.main(["notes", "add", "--racine", root, "--titre", "Veto sans cible", "--veto"]) == 2
    assert "au moins une cible" in capsys.readouterr().err


def test_universe_output_carries_the_banner_and_french_wording(capsys, monkeypatch):
    import brvm_alpha.strategy as strategy

    class FakeModel:
        def __init__(self, **kw):
            pass

        def universe(self, t, panels):
            u = pd.DataFrame({"eligible": [True, False, False],
                              "reason": ["", "U5 : MDV63 insuffisante", "U1 : absent du BOC de la date (non coté ou radié)"]},
                             index=["SNTS", "PRSC", "SVOC"])
            u.attrs.update({"n_eligible": 1, "mode": "selection", "mdv_floor": 500_000.0})
            return u

    monkeypatch.setattr(strategy, "BrvmAlpha", FakeModel)
    monkeypatch.setattr(strategy, "build_panels", lambda *a, **k: {})
    assert cli.main(["universe", "--date", "2026-11-20"]) == 0
    out = plain(capsys.readouterr().out)
    assert out.splitlines()[0] == ("Univers au 20/11/2026 : 2 titres cotés (plus 1 ancien(s) titre(s) absent(s) du BOC, "
                                   "listé(s) pour mémoire), dont 1 éligibles ; mode sélection (plancher U5 500 000 FCFA)")
    assert out.rstrip().endswith(cli.BANNER) and "2026-11-20" not in out and "mode selection" not in out


def test_stale_panel_warning_in_indices_output(tmp_path, capsys, monkeypatch):
    from brvm_alpha.notes import index_eval

    def fake_eval(*a, **k):
        return pd.DataFrame({"label": ["BRVM Composite"], "date": [pd.Timestamp("2026-11-20")], "level": [492.89],
                             "ret_1m": [-0.06], "ret_12m": [0.43], "ytd": [0.42], "stance": ["SOUS-PONDÉRER"],
                             "confidence": [0.6], "composite": [-0.52], "reasons": [["raison"]]},
                            index=pd.Index(["IDX:BRVM-C"], name="index"))

    monkeypatch.setattr(index_eval, "evaluate_indices", fake_eval)
    monkeypatch.setattr(cli, "last_session", lambda panel_dir=None: pd.Timestamp("2026-11-20"))
    monkeypatch.setattr(cli, "now_utc", lambda: pd.Timestamp("2026-11-23 19:00", tz="UTC"))  # lundi soir
    assert cli.main(["indices", "--sans-notes"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("⚠ PANEL EN RETARD de 1 séance(s)") and "python -m brvm_alpha update" in out
    assert cli.main(["indices", "--sans-notes", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["avertissement_panel"].startswith("PANEL EN RETARD")
    monkeypatch.setattr(cli, "now_utc", lambda: pd.Timestamp("2026-11-22 16:00", tz="UTC"))  # dimanche : à jour
    assert cli.main(["indices", "--sans-notes"]) == 0
    assert "PANEL EN RETARD" not in capsys.readouterr().out

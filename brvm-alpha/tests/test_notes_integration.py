"""Assemblage du mode direct des notes et de la lecture du contenu des publications.

Ces tests appellent la **vraie** ``research.enrich_documents`` depuis la ligne de commande et depuis
l'interface (les tests de ``test_notes_direct`` utilisent une doublure), sur un journal temporaire dont
le cache est rempli par un transport HTTP simulé : aucune requête réseau, journal réel jamais touché.

Ils couvrent aussi deux points d'affichage de l'ordre de bataille vus à l'assemblage :

- en indice discipliné (REF), un filtre de simple surveillance (R10) n'est pas le motif d'un écart de
  poids : l'écart vient de la redistribution du poids d'un titre bloqué ;
- une position d'indice qui ne change que par le poids de la composante « notes » est signalée
  (position « sans les notes » affichée), sans qu'aucune pondération ne soit modifiée.

Les pages de l'interface servies par HTTP sont vérifiées dans ``test_ui_notes_integration`` (le garde
« aucune requête réseau » de ce module-ci interdit aussi les connexions locales).

Panels synthétiques (dates de S0 seulement) : aucune performance n'est évaluée sur l'échantillon S1.
"""

from __future__ import annotations

import datetime as dt
import warnings

import pandas as pd
import pytest

from test_notes_direct import SAT, SAT_KNOWN, _order, _targets
from test_notes_lecture import (  # noqa: F401 - fixtures importées (journal, lecture sans pdftotext)
    READ_AT,
    journal,
    layout_without_pdftotext,
    lines_of,
    make_session,
)
from test_notes_research import no_network  # noqa: F401 - fixture autouse : aucune requête réseau
from test_report_html import synth  # noqa: F401 - fixture importée
from test_ui import FakeServices

from brvm_alpha import cli
from brvm_alpha.notes import research as r
from brvm_alpha.notes.model import Note
from brvm_alpha.notes.store import NoteStore
from brvm_alpha.portfolio import recommend as R
from brvm_alpha.report import html as report_html


@pytest.fixture()
def cached_journal(journal, tmp_path, monkeypatch):  # noqa: F811
    """Journal de la collecte dont trois documents sur six sont en cache (passe à blanc, rien d'écrit)."""
    store, ids = journal
    sess, web, _ = make_session(tmp_path)
    dry = r.enrich_documents(store, session=sess, dry_run=True, max_docs=3, now=READ_AT)
    assert dry["n_selected"] == 3 and dry["n_written"] == 0 and lines_of(store) == 9
    # La sélection dépend de la date du jour (documents « encore utiles ») : horloge de la lecture figée.
    monkeypatch.setattr(r, "utcnow", lambda: READ_AT)
    return store, ids, web


# ---------------------------------------------------------------------------
# Ligne de commande : « notes lire --hors-ligne » avec la vraie fonction
# ---------------------------------------------------------------------------


def test_cli_notes_lire_offline_calls_the_real_function_and_reads_nothing_twice(cached_journal, tmp_path, capsys):
    store, ids, web = cached_journal
    n_calls = len(web.calls)
    root = str(tmp_path / "notes")
    assert cli.main(["notes", "lire", "--hors-ligne", "--racine", root]) == 0
    out = capsys.readouterr().out
    # Trois documents du cache lus (alerte, rapport semestriel, scan) ; trois absents du cache, non lus.
    assert "6 candidat(s), 2 lu(s), 2 note(s) enrichie(s), 1 document(s) scanné(s) à lire à la main, 0 erreur(s), " \
           "0 requête(s)." in out
    assert "3 document(s) absent(s) du cache, non lu(s)" in out
    assert "3 nouvelle(s) version(s) écrite(s) au journal (les anciennes restent)" in out
    assert "à lire à la main" in out and cli.BANNER in out
    assert lines_of(store) == 9 + 3 and len(web.calls) == n_calls
    fresh = NoteStore(root)
    assert {k: fresh.get(ids[k]).version for k in ("pw", "s1", "scan", "t3", "bad", "txt")} == {
        "pw": 2, "s1": 2, "scan": 2, "t3": 1, "bad": 1, "txt": 1}
    assert "doc_lu" in fresh.get(ids["s1"]).tags and "doc_scan" in fresh.get(ids["scan"]).tags
    # Deuxième appel : rien n'est relu, rien n'est écrit (journal en ajout seul inchangé).
    assert cli.main(["notes", "lire", "--hors-ligne", "--racine", root]) == 0
    out = capsys.readouterr().out
    assert "3 candidat(s), 0 lu(s), 0 note(s) enrichie(s), 0 document(s) scanné(s) à lire à la main, 0 erreur(s), " \
           "0 requête(s)." in out
    assert "0 nouvelle(s) version(s) écrite(s)" in out and "3 document(s) absent(s) du cache" in out
    assert lines_of(store) == 12 and len(web.calls) == n_calls
    # Périmètre : un émetteur déjà lu en entier n'a plus de candidat ; le message le dit.
    assert cli.main(["notes", "lire", "--hors-ligne", "--racine", root, "--cibles", "SIVC"]) == 0
    out = capsys.readouterr().out
    assert "0 candidat(s)" in out and "Aucun document à lire" in out and lines_of(store) == 12


def test_cli_notes_lire_simulation_writes_nothing(cached_journal, tmp_path, capsys):
    store, ids, web = cached_journal
    n_calls = len(web.calls)
    assert cli.main(["notes", "lire", "--hors-ligne", "--simulation", "--racine", str(tmp_path / "notes")]) == 0
    out = capsys.readouterr().out
    assert "simulation, rien ne sera écrit au journal" in out and "simulation : aucune version écrite au journal" in out
    assert "6 candidat(s), 2 lu(s)" in out and "nouvelle(s) version(s)" not in out
    assert lines_of(store) == 9 and store.get(ids["pw"]).version == 1 and len(web.calls) == n_calls


def test_enrich_report_wording_keeps_working_with_a_reduced_report():
    # Bilan réduit (clés du contrat seulement) : aucune ligne « Détail », aucune erreur.
    lines = cli.format_enrich_report({"n_candidates": 2, "n_read": 1, "n_enriched": 1, "n_scanned": 0, "n_failed": 0,
                                      "n_requests": 1, "stopped": None, "details": []})
    assert lines == ["Lecture du contenu des documents : 2 candidat(s), 1 lu(s), 1 note(s) enrichie(s), "
                     "0 document(s) scanné(s) à lire à la main, 0 erreur(s), 1 requête(s)."]
    full = cli.format_enrich_report({"n_candidates": 4, "n_read": 3, "n_enriched": 2, "n_no_figure": 1, "n_scanned": 0,
                                     "n_failed": 0, "n_skipped": 1, "n_written": 3, "n_requests": 0, "dry_run": False,
                                     "stopped": None, "details": []})
    assert full[1] == ("Détail : 1 document(s) lu(s) sans chiffre retenu (score fondé sur le ton seul) ; 1 document(s) "
                       "absent(s) du cache, non lu(s) (hors ligne : une lecture en ligne les téléchargera) ; 3 "
                       "nouvelle(s) version(s) écrite(s) au journal (les anciennes restent).")


# ---------------------------------------------------------------------------
# Interface : case « lire le contenu des documents » avec la vraie fonction
# ---------------------------------------------------------------------------


def test_ui_research_reads_documents_with_the_real_function(cached_journal, tmp_path, monkeypatch):
    store, ids, web = cached_journal
    n_calls = len(web.calls)
    seen: list[dict] = []
    real = r.enrich_documents

    def spy(st, **kw):
        seen.append(kw)
        return real(st, **kw)

    monkeypatch.setattr(r, "enrich_documents", spy)
    svc = FakeServices(tmp_path)
    log: list[str] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = svc.run_research(offline=True, max_requests=5, targets=None, since=None, log=log.append,
                               read_docs=True, max_docs=20)
    bilan = out["documents"]["bilan"]
    assert (bilan["n_read"], bilan["n_enriched"], bilan["n_scanned"], bilan["n_skipped"], bilan["n_written"],
            bilan["n_requests"], bilan["offline"]) == (2, 2, 1, 3, 3, 0, True)
    assert len(web.calls) == n_calls and NoteStore(tmp_path / "notes").get(ids["s1"]).version == 2
    # Même panel que la collecte de l'interface, session hors ligne propre à la lecture.
    kw = seen[0]
    assert kw["max_docs"] == 20 and kw["offline"] is True and kw["panel_dir"] is None
    assert kw["session"].offline is True and kw["session"].cache_dir == tmp_path / "notes" / "cache"
    text = "\n".join(log)
    assert "lecture du contenu d'au plus 20 document(s) récent(s) (hors ligne : cache seulement)" in text
    assert "3 nouvelle(s) version(s) écrite(s) au journal" in text and "à lire à la main" in text
    # Deuxième lancement : rien n'est relu.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        again = svc.run_research(offline=True, max_requests=5, targets=None, since=None, log=log.append,
                                 read_docs=True, max_docs=20)
    assert again["documents"]["bilan"]["n_written"] == 0 and again["documents"]["bilan"]["n_read"] == 0
    assert len(web.calls) == n_calls


# ---------------------------------------------------------------------------
# Ordre de bataille : motif d'un écart de poids en indice discipliné
# ---------------------------------------------------------------------------


def test_ref_weight_change_of_a_watched_line_is_redistribution_not_its_filter(synth, tmp_path):  # noqa: F811
    base = _order(synth, tmp_path, notes_store=False)
    ranked = [str(s) for s in base.lignes.sort_values("poids_cible", ascending=False)["symbole"]]
    blocked, watched = ranked[2], ranked[4]
    st = NoteStore(tmp_path / "notes")
    st.add(Note(title=f"{blocked} : annulation de l'Assemblée Générale Ordinaire",
                text="L'assemblée générale ordinaire convoquée est annulée sur instruction du régulateur.",
                targets=[blocked], author="analyste", created_at=SAT, event_type="AG_CANCEL",
                analysis={"targets": [blocked], "event_type": "AG_CANCEL", "score": -0.5, "confidence": 0.7,
                          "risk_flags": ["R2"]}), now=SAT)
    st.add(Note(title=f"{watched} : rapport d'activités, résultat net en baisse de 30 %", text="Résultat net −30 %.",
                targets=[watched], author="analyste", created_at=SAT, event_type="ACT_Q3",
                analysis={"targets": [watched], "event_type": "ACT_Q3", "score": -0.5, "confidence": 0.8,
                          "risk_flags": ["R10"]}), now=SAT)
    o = _order(synth, tmp_path, notes_store=st, notes_known_at=SAT_KNOWN)
    nt = o.declencheurs["notes"]
    assert {f["symbole"]: (f["code"], f["bloque_achats"]) for f in nt["filtres"]} == {
        blocked: ("R2", True), watched: ("R10", False)}
    assert blocked not in _targets(o) and watched in _targets(o)
    rows = {x["symbole"]: x for x in nt["effet"]["lignes"]}
    assert "R2" in rows[blocked]["motif"] and rows[blocked]["poids_avec_notes"] == 0.0
    # Le titre sous surveillance garde sa place : son poids monte par redistribution, pas par son filtre.
    assert rows[watched]["ecart"] > 0 and rows[watched]["motif"] == ""
    md = o.to_markdown()
    line = next(ln for ln in md.splitlines() if ln.startswith(f"| {watched} |") and "redistribution" in ln)
    assert "filtre" not in line
    assert sum(x["ecart"] for x in rows.values()) == pytest.approx(0.0, abs=1e-9)


def test_ref_explanation_of_a_blocked_title_names_the_block_not_its_size(synth, tmp_path):  # noqa: F811
    base = _order(synth, tmp_path, notes_store=False)
    ranked = [str(s) for s in base.lignes.sort_values("poids_cible", ascending=False)["symbole"]]
    blocked = ranked[2]
    st = NoteStore(tmp_path / "notes")
    st.add(Note(title=f"{blocked} : annulation de l'Assemblée Générale Ordinaire",
                text="L'assemblée générale ordinaire convoquée est annulée sur instruction du régulateur.",
                targets=[blocked], author="analyste", created_at=SAT, event_type="AG_CANCEL",
                analysis={"targets": [blocked], "event_type": "AG_CANCEL", "score": -0.5, "confidence": 0.7,
                          "risk_flags": ["R2"]}), now=SAT)
    o = _order(synth, tmp_path, notes_store=st, notes_known_at=SAT_KNOWN, explanations=True)
    by_sym = {e["symbole"]: e for e in o.explications}
    e = by_sym[blocked]
    assert e["statut"] == "écarté" and e["rang"] <= 20 and "R2" in e["filtres"]
    # Un titre parmi les plus grosses capitalisations n'est pas « hors des 20 plus grosses » : il est bloqué.
    assert "achat bloqué par un filtre de risque, titre non détenu écarté de la sélection (D8)" in e["texte_court"]
    assert "hors des 20 plus grosses" not in e["texte_court"]
    others = [x for x in o.explications if x["statut"] == "écarté" and x["symbole"] != blocked]
    assert others and all("hors des 20 plus grosses (D8)" in x["texte_court"] for x in others)


# ---------------------------------------------------------------------------
# Indices : position qui ne change que par la composante « notes »
# ---------------------------------------------------------------------------


def _fake_indices() -> pd.DataFrame:
    effet = ("Effet des notes : sans la composante notes, le score composite serait −0,53 (SOUS-PONDÉRER) ; avec elle, "
             "−0,44 (NEUTRE) : la position change à cause de cette composante (elle pèse 15 % du score dès qu'une note "
             "porte un score, même faible).")
    return pd.DataFrame({
        "label": ["BRVM Composite", "BRVM 30", "BRVM Prestige"],
        "stance": ["NEUTRE", "SOUS-PONDÉRER", "SOUS-PONDÉRER"],
        "stance_ex_notes": ["SOUS-PONDÉRER", "SOUS-PONDÉRER", "SOUS-PONDÉRER"],
        "composite": [-0.44, -0.71, -0.72], "composite_ex_notes": [-0.53, -0.85, -0.72],
        "z_notes": [0.09, 0.09, None], "confidence": [0.51, 0.76, 0.7],
        "reasons": [["Score composite −0,44 → NEUTRE.", effet], ["Score composite −0,71 → SOUS-PONDÉRER."],
                    ["Score composite −0,72 → SOUS-PONDÉRER."]],
    }, index=pd.Index(["IDX:BRVM-C", "IDX:BRVM-30", "IDX:PRESTIGE"], name="index"))


def test_order_flags_an_index_stance_changed_by_the_notes_component_only(monkeypatch, tmp_path):
    from brvm_alpha.notes import index_eval

    monkeypatch.setattr(index_eval, "evaluate_indices", lambda *a, **k: _fake_indices())
    rows, msg = R._index_evaluation(pd.Timestamp("2026-11-20"), tmp_path, False, None,
                                    notes_known_at=dt.datetime(2026, 11, 22, 15, 0, tzinfo=dt.timezone.utc))
    assert msg == "" and [x["indice"] for x in rows] == ["IDX:BRVM-C", "IDX:BRVM-30", "IDX:PRESTIGE"]
    comp, b30, prestige = rows
    assert comp["position"] == "NEUTRE" and comp["position_sans_notes"] == "SOUS-PONDÉRER"
    assert comp["position_changee_par_les_notes"] is True and comp["score_sans_notes"] == pytest.approx(-0.53)
    assert comp["lecture"].startswith("Score composite −0,44") and "Effet des notes" in comp["lecture"]
    assert b30["position_changee_par_les_notes"] is False and "Effet des notes" not in b30["lecture"]
    # Sans composante « notes » (z absent), aucune bascule n'est annoncée.
    assert prestige["position_changee_par_les_notes"] is False
    # Rapport HTML : même règle d'affichage (position « sans notes » seulement quand elle diffère).
    ev = _fake_indices()
    assert report_html._stance_flip(ev.loc["IDX:BRVM-C"]) == "SOUS-PONDÉRER"
    assert report_html._stance_flip(ev.loc["IDX:BRVM-30"]) is None
    assert report_html._stance_flip(ev.loc["IDX:PRESTIGE"]) is None


def test_order_markdown_shows_the_fragile_position(synth, tmp_path, monkeypatch):  # noqa: F811
    from brvm_alpha.notes import index_eval

    monkeypatch.setattr(index_eval, "evaluate_indices", lambda *a, **k: _fake_indices())
    o = _order(synth, tmp_path, notes_store=False, index_evaluation=True)
    md = o.to_markdown()
    assert "| BRVM Composite | NEUTRE (sans les notes : SOUS-PONDÉRER) |" in md
    assert "| BRVM 30 | SOUS-PONDÉRER |" in md
    assert "Position changée par les notes : BRVM Composite — les notes s'ajoutent au score" in md
    assert R.BANNER in md

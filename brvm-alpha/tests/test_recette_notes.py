"""Régressions de la recette finale du 22/11/2026 — notes de l'analyste (analyse, lexique, indices, journal).

Un test par constat prouvé ; chacun échoue sur le code d'avant la correction (commit 552a03b). Hors
ligne, journaux temporaires (``tmp_path``), panels synthétiques : le journal réel ``data/notes`` n'est
jamais touché, aucune requête réseau, aucun calcul sur l'échantillon vierge S1.
Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from test_index_eval import synthetic_panel
from test_notes_direct import KNOWN, SUNDAY, T_BOC, bearish_index_note

from brvm_alpha.notes import analyze as an
from brvm_alpha.notes import index_eval as ie
from brvm_alpha.notes.lexicon import scan
from brvm_alpha.notes.model import Note, jsonable
from brvm_alpha.notes.store import NoteStore


@pytest.fixture(scope="module")
def panel() -> dict[str, pd.DataFrame]:
    return synthetic_panel()


def auto_note(title: str, targets: list[str], score: float, confidence: float = 0.56, when: str = SUNDAY,
              published: str = "2026-11-19") -> Note:
    """Note collectée automatiquement, analyse fournie (score et confiance choisis)."""
    return Note(title=title, text=title, targets=targets, author="auto", source="brvm_issuer",
                url=f"https://www.brvm.org/sites/default/files/{abs(hash(title))}.pdf", created_at=when,
                published_at=published, event_type="RES_S1",
                analysis={"targets": targets, "event_type": "RES_S1", "score": score, "confidence": confidence,
                          "risk_flags": []})


# ---------------------------------------------------------------------------
# Constat « indices dossier --format json » : RecursionError sur une date manquante
# ---------------------------------------------------------------------------


def test_jsonable_handles_missing_dates_without_recursion():
    # pd.NaT est une instance de datetime sans être un Timestamp : la branche « datetime » bouclait.
    out = jsonable({"a": pd.NaT, "b": [pd.NaT, pd.Timestamp("2026-11-20")], "c": np.datetime64("NaT", "ns"), "d": pd.NA})
    assert out == {"a": None, "b": [None, "2026-11-20"], "c": None, "d": None}
    json.dumps(out)


@pytest.mark.parametrize("code", ["IDX:BRVM-C", "IDX:BRVM-30", "IDX:PRESTIGE", "IDX:PRINCIPAL"])
def test_index_dossier_serialises_to_json_for_every_index(tmp_path, panel, code):
    st = NoteStore(tmp_path)
    st.add(bearish_index_note(), now=SUNDAY)
    d = ie.index_dossier(code, panels=panel, store=st, asof=T_BOC, notes_known_at=KNOWN)
    txt = json.dumps(jsonable({k: v for k, v in d.items() if k not in ("overlays", "notes_moment")}), ensure_ascii=False)
    assert json.loads(txt)["index"] == code


# ---------------------------------------------------------------------------
# Constat « négation qui traverse le saut de ligne »
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("title, text", [
    ("Etats financiers non audités", "Dividende relevé."),  # du titre au texte
    ("Etats financiers", "Comptes non audités\nDividende relevé"),  # d'une ligne à la suivante
    ("Doublon non daté", "Dividende relevé."),
])
def test_negation_does_not_cross_a_line_break(title, text):
    a = an.analyze_text(text, title=title, manual_targets=["SNTS"])
    hit = next(t for t in a.matched_terms if t["label"] == "dividende en hausse")
    assert hit["weight"] > 0 and "négation" not in hit["modifiers"]
    assert a.score > 0


def test_negation_still_applies_inside_a_wrapped_sentence():
    # Phrase coupée par la mise en page d'un PDF (la ligne suivante reprend en minuscule) : même proposition.
    hits = scan("Il n'y a aucune\nbaisse du résultat net.")
    hit = next(h for h in hits if h.label == "baisse du résultat net")
    assert hit.weight > 0 and "négation" in hit.modifiers


# ---------------------------------------------------------------------------
# Constat « erreurs de signe et de montant » et « phrases directionnelles sans score »
# ---------------------------------------------------------------------------

#: (phrase, signe attendu) : batterie de la recette (40 phrases) plus les tournures du constat.
BATTERY = [
    ("Pas de dégradation de la qualité du portefeuille de crédits de la banque.", ">=0"),
    ("Le conseil d'administration n'anticipe aucune baisse du dividende.", ">=0"),
    ("La société n'a pas enregistré de perte au premier semestre 2026.", ">=0"),
    ("Le résultat net n'a pas progressé sur la période.", "<=0"),
    ("Aucune amélioration de la rentabilité n'est attendue cette année.", "<=0"),
    ("Malgré la baisse du chiffre d'affaires, le résultat net progresse de 8 %.", "+"),
    ("Malgré la hausse du chiffre d'affaires, le résultat net recule de 15 %.", "-"),
    ("Bien que le produit net bancaire soit en hausse, le résultat net est en forte baisse.", "-"),
    ("En dépit d'un contexte difficile, le bénéfice net augmente de 20 %.", "+"),
    ("Baisse du coût du risque.", "+"),
    ("Recul des créances douteuses.", "+"),
    ("Hausse de l'endettement.", "-"),
    ("Résultat net en repli de 12 %.", "-"),
    ("Dividende en hausse de 15 %.", "+"),
    ("La société enregistre une perte nette de 2 milliards de FCFA.", "-"),
    ("Passage du bénéfice à la perte.", "-"),
    ("Suspension de la cotation du titre.", "-"),
    ("Notation dégradée par l'agence Bloomfield.", "-"),
    ("Perspective positive attribuée par l'agence de notation.", "+"),
    ("Coup d'État au Niger.", "-"),
    ("Levée des sanctions de la CEDEAO contre le Niger.", "+"),
    ("Hausse du coût du risque.", "-"),
    ("Augmentation des créances en souffrance.", "-"),
    ("Réduction de la dette nette.", "+"),
    ("Baisse des charges d'exploitation.", "+"),
    ("Réduction de la perte nette par rapport à l'an dernier.", "+"),
    ("Dividende supprimé au titre de l'exercice 2025.", "-"),
    ("Dividende en baisse de 30 %.", "-"),
    ("Avertissement sur résultats : le résultat net sera en forte baisse.", "-"),
    ("Notation relevée de A à A+ avec perspective stable.", "+"),
    ("Perspective négative sur la notation de long terme.", "-"),
    ("Retour aux bénéfices après deux exercices déficitaires.", "+"),
    ("Amélioration du coefficient d'exploitation.", "+"),
    ("Détérioration du coefficient d'exploitation.", "-"),
    ("Le chiffre d'affaires s'établit à 120 milliards de FCFA contre 100 milliards de FCFA un an plus tôt.", "+"),
    ("Le résultat net passe de 10 milliards de FCFA à 7 milliards de FCFA.", "-"),
    ("Le produit net bancaire progresse de 9,5 % à 45,2 milliards de FCFA.", "+"),
    ("Le résultat net ressort à 3 250 millions de FCFA, en baisse de 18,4 %.", "-"),
    ("Le dividende net par action passe de 1 500 FCFA à 1 800 FCFA.", "+"),
    ("Les actionnaires sont convoqués en assemblée générale ordinaire le 15 décembre 2026 à Abidjan.", "0"),
    ("Le dividende net par action est porté de 1 500 FCFA à 1 800 FCFA, soit une hausse de 20 %.", "+"),
    ("La perte nette se réduit de 477 millions à 346 millions de FCFA.", ">=0"),
    ("Hausse des charges d'exploitation.", "-"),
]


@pytest.mark.parametrize("text, expected", BATTERY)
def test_battery_of_directional_sentences(text, expected):
    s = an.analyze_text(text).score
    ok = {"+": s > 0, "-": s < 0, "0": abs(s) < 0.05, ">=0": s >= 0, "<=0": s <= 0}[expected]
    assert ok, f"score {s:+.3f} pour « {text} » (attendu {expected})"


@pytest.mark.parametrize("text", [
    "Le dividende net par action passe de 1 500 FCFA à 1 800 FCFA.",
    "Le dividende net par action est porté de 1 500 FCFA à 1 800 FCFA, soit une hausse de 20 %.",
])
def test_dividend_from_to_takes_the_new_amount_as_current(text):
    ex = an.analyze_text(text).extracted
    assert ex["div_net"] == 1800.0 and ex["div_prev"] == 1500.0 and ex["div_growth"] == pytest.approx(0.2)


def test_loss_from_to_takes_the_new_loss_as_current_and_the_old_one_as_previous():
    a = an.analyze_text("La perte nette se réduit de 477 millions à 346 millions de FCFA.")
    assert a.extracted["rn"] == -346e6 and a.extracted["rn_prev"] == -477e6
    assert a.extracted.get("rn_growth") is None  # base négative : aucun score numérique
    labels = {t["label"]: t["weight"] for t in a.matched_terms}
    assert labels.get("réduction de la perte", 0) > 0 and a.score >= 0
    # « contre » : le montant précédent d'une perte est une perte, sauf si le texte nomme un bénéfice.
    b = an.analyze_text("La perte nette ressort à 346 millions de FCFA contre 477 millions de FCFA.")
    assert b.extracted["rn"] == -346e6 and b.extracted["rn_prev"] == -477e6 and b.score >= 0
    c = an.analyze_text("La perte nette ressort à 3,2 milliards de FCFA contre un bénéfice de 1,6 milliard de FCFA.")
    assert c.extracted["rn"] == -3.2e9 and c.extracted["rn_prev"] == 1.6e9 and c.score < 0


def test_past_loss_introduced_by_apres_does_not_cancel_a_return_to_profit():
    hits = {h.label: h for h in scan("Retour aux bénéfices après deux exercices déficitaires.")}
    assert hits["retour aux bénéfices"].weight == 2.0
    assert hits["perte nette"].weight == 0.0 and any("situation antérieure" in m for m in hits["perte nette"].modifiers)
    # sans « après », la perte compte toujours
    assert next(h for h in scan("La société reste déficitaire.") if h.label == "perte nette").weight < 0


# ---------------------------------------------------------------------------
# Constat « score positif quand le résultat net baisse »
# ---------------------------------------------------------------------------


def test_tone_cannot_reverse_the_sign_of_the_figures_when_net_result_is_read():
    # SGBC T3 2026 (journal réel) : PNB −1,7 %, résultat net −3,5 %, un seul terme positif → score +0,10 avant.
    a = an.analyze_text("Le produit net bancaire recule de 1,7 %. Le résultat net est en baisse de 3,5 %. "
                        "Amélioration du coefficient d'exploitation.",
                        title="SOCIETE GENERALE CI : Rapport d'activités - 3e trimestre 2026", manual_targets=["SGBC"])
    assert a.extracted["rn_growth"] == pytest.approx(-0.035) and a.tone > 0
    assert a.score < 0
    assert a.components["tone_contradicts_numbers"] is True
    assert any("contraire aux chiffres" in w for w in a.warnings) and "contraire aux chiffres" in a.reading
    # Saisie de l'analyste (constat) : résultat net −12 %, « reste solide », progression des revenus.
    b = an.analyze_text("Le résultat net en repli de 12 % reste solide ; forte progression de l'activité et "
                        "croissance des revenus.")
    assert b.extracted["rn_growth"] == pytest.approx(-0.12) and b.score < 0
    # Quand le ton va dans le sens des chiffres ou ne renverse pas le signe, la formule du document 07 reste.
    c = an.analyze_text("Le résultat net progresse de 10 %, mais la hausse du coût du risque et des dépréciations "
                        "inquiète.")
    assert c.score == pytest.approx(0.7 * c.components["s_num_doc"] + 0.3 * c.tone, abs=1e-3) and c.score > 0
    assert c.components["tone_contradicts_numbers"] is False


def test_bank_revenue_words_are_replaced_by_the_pnb_figure():
    # « progression des revenus » d'une banque = PNB, déjà chiffré : ce n'est pas un chiffre d'affaires « en mots ».
    a = an.analyze_text("Le produit net bancaire progresse de 1,8 %. Le résultat net recule de 12,3 %. "
                        "Bonne progression des revenus.", manual_targets=["ECOC"])
    assert a.components["lexical_only_indicators"] == []
    assert a.components["weights"]["w_num"] == pytest.approx(an.W_NUM)
    assert a.score < 0


# ---------------------------------------------------------------------------
# Constat « filtre R10 muet sur un passage à la perte »
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cur, prev, motif", [
    ("-673", "178", "passage d'un bénéfice à une perte"),  # FILTISAC S1 2026
    ("-1 821", "-557", "perte aggravée de 227 %"),  # SETAO S1 2026
    ("-354", "-251", "perte aggravée de 41 %"),  # FILTISAC T3 2026
])
def test_r10_candidate_when_profit_turns_to_loss_or_loss_deepens(cur, prev, motif):
    a = an.analyze_text(f"Le résultat net ressort à {cur} millions de FCFA au 30 juin 2026 contre {prev} millions de "
                        "FCFA au 30 juin 2025.", title="FILTISAC CI : Rapport d'activités - 1er semestre 2026",
                        manual_targets=["FTSC"])
    assert a.extracted.get("rn_growth") is None  # toujours aucun score numérique (base non comparable)
    assert a.extracted["r10_candidate"] is True and a.extracted["rn_degradation"] == motif


def test_r10_flag_is_raised_on_amounts_when_no_profit_warning_preceded():
    hist = pd.DataFrame([{"note_id": "x" * 40, "event_type": "RES_S1", "targets": ["FTSC"],
                          "published_at": pd.Timestamp("2026-01-10", tz="UTC"), "risk_flags": [], "status": "active",
                          "title": "FILTISAC : autre publication", "all_targets": ["FTSC"]}])
    note = Note(title="FILTISAC CI : Rapport d'activités - 1er semestre 2026",
                text="Le résultat net ressort à -673 millions de FCFA au 30 juin 2026 contre 178 millions de FCFA au "
                     "30 juin 2025.", targets=["FTSC"], author="auto", source="brvm_issuer",
                url="https://www.brvm.org/sites/default/files/ftsc_s1.pdf", published_at="2026-10-30")
    a = an.analyze_note(note, history=hist)
    assert "R10" in a.risk_flags


def test_rn_degradation_rule():
    assert an.rn_degradation(-673.0, 178.0) == "passage d'un bénéfice à une perte"
    assert an.rn_degradation(-1821.0, -557.0) == "perte aggravée de 227 %"
    assert an.rn_degradation(130.0, 178.0) == "baisse de 27 %"
    assert an.rn_degradation(160.0, 178.0) is None  # −10 % : sous le seuil
    assert an.rn_degradation(-200.0, -251.0) is None  # perte réduite
    assert an.rn_degradation(-270.0, -251.0) is None  # perte aggravée de 8 % : sous le seuil
    assert an.rn_degradation(200.0, 178.0) is None and an.rn_degradation(None, 178.0) is None


# ---------------------------------------------------------------------------
# Constat « résultat des activités ordinaires » et « ETIT lu en dollars »
# ---------------------------------------------------------------------------

DOC_RAO = """SODECI
RAPPORT D'ACTIVITE DU 1ER SEMESTRE 2026

                                        (en millions de FCFA)
                                      30/06/2026     30/06/2025     Variation      %
Chiffre d'affaires                        60 000         58 824         1 176     2,0 %
Résultat des activités ordinaires          4 050          2 872         1 178    41,0 %
Résultat hors activités ordinaires           196             40           156
Résultat net                               2 952          1 500         1 452    96,8 %
"""


def test_ordinary_activities_result_is_not_renamed_pre_tax_result():
    doc = an.read_document(DOC_RAO, title="SODECI : Rapport d'activités - 1er semestre 2026", event_type="RES_S1")
    assert doc["figures"]["rai"]["growth"] == pytest.approx(0.41, abs=1e-3)
    note = Note(title="SODECI : Rapport d'activités - 1er semestre 2026", text=doc["excerpt"], targets=["SDCC"],
                author="auto", source="brvm_issuer", url="https://www.brvm.org/sites/default/files/sdcc_s1.pdf",
                published_at="2026-10-30", event_type="RES_S1")
    a = an.analyze_note(note, document={**doc, "marks": {"doc_status": "lu"}})
    assert a.extracted["rai_label"] == "résultat des activités ordinaires"
    assert "résultat des activités ordinaires 4,0" in a.reading and "résultat avant impôt" not in a.reading


def test_growth_written_in_dollars_is_rejected_for_a_fcfa_stock():
    text = ("Ecobank Transnational Incorporated\nRapport d'activités du 3e trimestre 2026\n\n"
            "Le chiffre d'affaires a également progressé de 12 % pour atteindre 2,0 milliards de dollars au 30 "
            "septembre 2026.\n")
    doc = an.read_document(text, title="ETI TG : Rapport d'activités - 3e trimestre 2026", event_type="ACT_Q3")
    assert "ca" not in doc["figures"]
    assert any(r["ind"] == "ca" and r["reason"] == an.FOREIGN_CURRENCY for r in doc["rejected"])
    # Une variation donnée avec un montant en FCFA reste retenue.
    ok = an.extract_figures("Le chiffre d'affaires progresse de 12 % à 1 200 milliards de FCFA.")
    assert ok["ca"]["growth"] == pytest.approx(0.12) and ok["ca"].get("currency") is None


# ---------------------------------------------------------------------------
# Constat « une seule note faible et négative fait passer le Composite à NEUTRE »
# ---------------------------------------------------------------------------


def test_combine_with_notes_is_additive_and_monotonic():
    assert ie.combine_with_notes(-0.53, None, 0.15) == -0.53
    assert ie.combine_with_notes(-0.53, 0.0, 0.15) == pytest.approx(-0.53)  # z nul : aucun déplacement
    assert ie.combine_with_notes(-0.53, -0.002, 0.15) < -0.53  # une note négative abaisse le score
    assert ie.combine_with_notes(-0.53, +0.2, 0.15) == pytest.approx(-0.50)
    zs = np.linspace(-3, 3, 25)
    vals = [ie.combine_with_notes(-0.53, float(z), 0.15) for z in zs]
    assert all(b > a for a, b in zip(vals, vals[1:]))
    assert ie.combine_with_notes(None, 0.4, 0.15) == pytest.approx(0.4)  # aucune composante de marché


def test_single_weak_negative_note_never_raises_an_index_score(tmp_path, panel):
    """Journal d'une seule note automatique, négative, de confiance 0,56 (cas NEI-CEDA de la recette) :
    le score de chaque indice baisse ou ne bouge pas, et la position ne change pas."""
    codes = ["IDX:BRVM-C", "IDX:BRVM-C-TR", "IDX:PRESTIGE", "IDX:PRINCIPAL"]
    base = ie.evaluate_indices(panel, asof=T_BOC, indices=codes)
    st = NoteStore(tmp_path)
    st.add(auto_note("SOGB CI : Rapport d'activités - 1er semestre 2026", ["SOGC"], -1.0, confidence=0.56), now=SUNDAY)
    ev = ie.evaluate_indices(panel, store=st, asof=T_BOC, indices=codes, notes_known_at=KNOWN)
    seen = 0
    for code in ev.index:
        r, b = ev.loc[code], base.loc[code]
        assert r["composite_ex_notes"] == pytest.approx(b["composite"])
        if pd.notna(r["z_notes"]):
            seen += 1
            assert r["z_notes"] < 0
            assert r["composite"] <= b["composite"]  # jamais relevé par une note négative
            assert r["composite"] == pytest.approx(b["composite"] + ie.COMPONENT_WEIGHTS["notes"] * r["z_notes"])
            assert abs(r["composite"] - b["composite"]) < 0.05
        assert r["stance"] == b["stance"]
    assert seen >= 2  # la note atteint le Composite et le compartiment de SOGC


def test_automatic_note_is_weighted_by_confidence_manual_note_is_not(tmp_path, panel):
    def z(store_dir, note):
        st = NoteStore(store_dir)
        st.add(note, now=SUNDAY)
        return ie.evaluate_indices(panel, store=st, asof=T_BOC, indices=["IDX:BRVM-C"],
                                   notes_known_at=KNOWN).loc["IDX:BRVM-C"]

    low = z(tmp_path / "a", auto_note("SONATEL : résultats", ["SNTS"], 0.6, confidence=0.5))
    high = z(tmp_path / "b", auto_note("SONATEL : résultats", ["SNTS"], 0.6, confidence=1.0))
    assert low["notes_score"] == pytest.approx(0.5 * high["notes_score"]) and high["notes_score"] > 0
    manual = z(tmp_path / "c", bearish_index_note())  # analyse : score −0,8, confiance 0,8
    assert manual["notes_score"] == pytest.approx(-0.8)


def test_index_note_is_shown_with_its_own_target_and_date(tmp_path, panel):
    st = NoteStore(tmp_path)
    st.add(bearish_index_note(), now=SUNDAY)
    ev = ie.evaluate_indices(panel, store=st, asof=T_BOC, indices=["IDX:BRVM-C", "IDX:PRESTIGE"], notes_known_at=KNOWN)
    p = ev.loc["IDX:PRESTIGE"]
    det = p["notes_detail"][0]
    assert det["source_targets"] == ["IDX:BRVM-C"] and det["propagation"] == pytest.approx(0.25)
    line = next(r for r in p["reasons"] if r.startswith("Notes qui portent la composante"))
    assert "(IDX:BRVM-C, propagée aux constituants × 0,25, note saisie le 22/11/2026, score −0,80" in line
    d = ie.index_dossier("IDX:PRESTIGE", panels=panel, store=st, asof=T_BOC, notes_known_at=KNOWN)
    rec = d["recent_notes"][0]
    assert rec["source_targets"] == ["IDX:BRVM-C"] and rec["propagation"] == pytest.approx(0.25)
    assert pd.Timestamp(rec["created_at"]).strftime("%Y-%m-%d") == "2026-11-22"


# ---------------------------------------------------------------------------
# Constat « une note manuelle saisie deux fois compte double »
# ---------------------------------------------------------------------------


def _manual(**kw) -> Note:
    base = dict(title="Sonatel : dividende relevé", text="Dividende relevé.", targets=["SNTS"], stance="haussier",
                conviction=2, author="analyste")
    base.update(kw)
    return Note(**base)


def test_store_finds_a_recent_identical_manual_note(tmp_path):
    st = NoteStore(tmp_path)
    first = st.add(_manual(created_at="2026-11-22T10:00:00Z"), now="2026-11-22T10:00:00Z")
    again = _manual(created_at="2026-11-22T10:05:00Z")  # même contenu, autre instant : identifiant différent
    assert again.note_id != first
    assert st.find_duplicate(again, now="2026-11-22T10:05:00Z") == first
    # casse, accents et espaces ignorés ; cibles dans un autre ordre
    same = _manual(title="  SONATEL :  dividende RELEVE ", created_at="2026-11-22T11:00:00Z")
    assert st.find_duplicate(same, now="2026-11-22T11:00:00Z") == first
    # contenu différent, note archivée, note ancienne ou note automatique : pas un doublon
    assert st.find_duplicate(_manual(conviction=4, created_at="2026-11-22T11:00:00Z"), now="2026-11-22T11:00:00Z") is None
    assert st.find_duplicate(_manual(text="Autre texte.", created_at="2026-11-22T11:00:00Z")) is None
    assert st.find_duplicate(again, now="2027-02-01T10:00:00Z") is None
    st.archive(first, now="2026-11-22T12:00:00Z")
    assert st.find_duplicate(again, now="2026-11-22T12:05:00Z") is None
    assert st.find_duplicate(auto_note("x", ["SNTS"], 0.1)) is None


# ---------------------------------------------------------------------------
# Constats de la collecte (research) : relance hors ligne, « Annule et remplace », dividende, émetteur
# ---------------------------------------------------------------------------


def test_journal_and_new_items_are_compared_on_the_same_document_date():
    """Un document écarté pendant la collecte ne devient pas une note à la première relance hors ligne."""
    from brvm_alpha.notes import research as r

    url = "https://www.brvm.org/sites/default/files/20230428_-_etats_financiers_ifrs_exercice_2022_-_sodeci.pdf"
    # Note au journal : publiée le 02/05/2023 (date du fichier, 28/04, plus une séance et un jour férié).
    frame = pd.DataFrame([{"note_id": "a" * 40, "title": "SODECI : Etats financiers IFRS Exercice 2022",
                           "targets": ["SDCC"], "event_type": "RES_ANNUAL", "url": url,
                           "published_at": pd.Timestamp("2023-05-02", tz="UTC")}])
    assert r._journal_doc_date(frame.iloc[0]) == pd.Timestamp("2023-04-28").date()
    item = {"symbol": "SDCC", "title": "SODECI : Etats financiers exercice 2022", "event_hint": None,
            "doc_date": pd.Timestamp("2023-03-31").date(), "list_type": "rapports_emetteur"}
    # 28 jours entre les deux DOCUMENTS (fenêtre de 30 jours des publications de résultats) : doublon, comme
    # pendant la collecte. Avant : 32 jours entre le document et la PUBLICATION de la note → note en plus.
    assert r._is_event_duplicate(item, r._event_index(frame)) is True
    # Sans adresse de fichier datée, la date de publication reste le repère.
    no_url = frame.assign(url=None)
    assert r._journal_doc_date(no_url.iloc[0]) == pd.Timestamp("2023-05-02").date()


def test_corrected_document_is_not_dated_before_its_own_file():
    """« Annule et remplace » : la note garde la date de SON fichier, pas celle de l'original."""
    import datetime as dt

    from brvm_alpha.notes import research as r

    seen = dt.datetime(2026, 11, 22, 13, 0, tzinfo=dt.timezone.utc)
    base = "https://www.brvm.org/sites/default/files/"
    kept = {"title": "FILTISAC CI : Rapport d'activités - 3e trimestre 2026 (Annule et remplace le précédent)",
            "symbol": "FTSC", "list_type": "rapports_emetteur", "source": "brvm_issuer", "extra": {},
            "doc_url": base + "20261105_-_rapport_dactivites_-_3e_trimestre_2026_-_filtisac_ci.pdf",
            "doc_date": dt.date(2026, 11, 5), "date_source": "fichier"}
    original = {"title": "FILTISAC CI : Rapport d'activités - 3e trimestre 2026", "symbol": "FTSC",
                "list_type": "rapports_emetteur", "source": "brvm_issuer", "extra": {},
                "doc_url": base + "20261030_-_rapport_dactivites_-_3e_trimestre_2026_-_filtisac_ci.pdf",
                "doc_date": dt.date(2026, 10, 30), "date_source": "fichier"}
    assert r.content_signature(kept["title"], "FTSC") == r.content_signature(original["title"], "FTSC")
    r._merge_publication(kept, original, seen)
    assert "published_override" not in kept["extra"]  # avant : la date de l'original (antérieure au fichier)
    assert kept["extra"]["earlier_twin"]["url"].endswith("20261030_-_rapport_dactivites_-_3e_trimestre_2026_-_filtisac_ci.pdf")
    published, _prec, _est = r.item_published_at(kept, seen)
    assert published.date() >= dt.date(2026, 11, 5)
    # Même document vu par deux listes (même fichier) : la publication la plus tôt reste retenue.
    twin = {**kept, "extra": {}, "list_type": "avis", "published_at": dt.datetime(2026, 11, 5, 16, 30, tzinfo=dt.timezone.utc)}
    other = {**kept, "extra": {}}
    r._merge_publication(other, twin, seen)
    assert other["extra"]["published_override"]["from"] == "avis"


def test_presumed_gross_dividend_is_reconciled_with_the_boc_net_amount():
    from brvm_alpha.notes import research as r

    divs = pd.DataFrame({"symbol": ["SDSC", "SGBC", "SPHC"], "ex_date": pd.to_datetime(["2026-10-26", "2026-08-21",
                                                                                         "2026-08-27"]),
                         "amount": [92.0, 2298.75, 430.32]})

    def item(sym, listed, ex):
        return {"symbol": sym, "extra": {"div_listed": listed, "div_gross": listed, "irvm_rate": 0.12,
                                         "div_net": round(listed * 0.88, 4), "div_basis": "brut présumé", "ex_date": ex}}

    sdsc, sgbc, sphc = item("SDSC", 92.0, "2026-10-26"), item("SGBC", 2606.0, "2026-08-21"), item("SPHC", 489.0, "2026-08-27")
    future = item("ORAC", 700.0, "2027-05-10")  # détachement pas encore au panel : la présomption reste
    assert r.reconcile_dividends_with_panel([sdsc, sgbc, sphc, future], divs) == 3
    # AGL CI : 92 FCFA affichés = 92 FCFA nets au BOC (l'estimation donnait 80,96, soit 12 % de moins).
    assert sdsc["extra"]["div_net"] == 92.0 and sdsc["extra"]["div_basis"] == "net (BOC)"
    assert "div_gross" not in sdsc["extra"] and "irvm_rate" not in sdsc["extra"]
    # Société Générale CI : net du BOC 2 298,75 (et non 2 293,28).
    assert sgbc["extra"]["div_net"] == 2298.75 and sgbc["extra"]["div_basis"] == "brut (net lu au BOC)"
    assert sphc["extra"]["div_net"] == 430.32  # estimation déjà juste : inchangée
    assert future["extra"]["div_basis"] == "brut présumé" and future["extra"]["div_net"] == 616.0
    assert r.reconcile_dividends_with_panel([item("SDSC", 92.0, "2026-10-26")], None) == 0


def test_filename_issuer_conflict_is_flagged():
    from brvm_alpha.notes import research as r

    base = "https://www.brvm.org/sites/default/files/"
    assert r.filename_issuer_symbol(base + "20231130_-_rapport_dactivites_-_3eme_trimestre_2023_-_ecobank_ci.pdf") == "ECOC"
    assert r.filename_issuer_symbol(base + "20250509_-_erratum_-_avis_de_convocation_-_solibra_ci_1.pdf") == "SLBC"
    assert r.filename_issuer_symbol(base + "20261023_-_communique_-_annulation_ago_-_eti_tg.pdf") == "ETIT"
    assert r.filename_issuer_symbol(base + "20230331_-_etats_financiers_exercice_2022.pdf") is None
    assert r.filename_issuer_symbol(base + "boc_20260916_2.pdf") is None and r.filename_issuer_symbol(None) is None
    # Page de l'émetteur ETI dont un fichier nomme Ecobank CI : étiquette « émetteur à vérifier ».
    page = ("<html><body><h1>ECOBANK TRANS. INCORP. TG</h1><div class='view-content'><table class='views-table'>"
            "<thead><tr><th class='views-field views-field-nothing'>Titre</th><th class='views-field "
            "views-field-field-fichier'>Fichier</th></tr></thead><tbody><tr>"
            "<td class='views-field views-field-nothing'>Ecobank Transnational Incorporated : Rapport d'activités - "
            "3ème trimestre 2023</td><td class='views-field views-field-field-fichier'><a href='/sites/default/files/"
            "20231130_-_rapport_dactivites_-_3eme_trimestre_2023_-_ecobank_ci.pdf'>PDF</a></td></tr></tbody></table>"
            "</div></body></html>")
    out = r.parse_issuer_reports(page, "https://www.brvm.org/fr/rapports-societe-cotes/ecobank-tg", symbol="ETIT")
    assert len(out["items"]) == 1
    it = out["items"][0]
    assert it["symbol"] == "ETIT" and it["extra"]["symbol_conflict"] == ["ETIT", "ECOC"]
    note = r.item_to_note(it, now=pd.Timestamp("2026-11-22 13:00", tz="UTC").to_pydatetime(), analyze=False)
    assert "emetteur_a_verifier" in note.tags and note.targets == ["ETIT"]


def test_html_parsing_falls_back_to_the_standard_parser_without_lxml(monkeypatch):
    import bs4

    from brvm_alpha.notes import research as r

    real = bs4.BeautifulSoup

    def no_lxml(markup, features=None, *a, **k):
        if features == "lxml":
            raise bs4.FeatureNotFound("Couldn't find a tree builder with the features you requested: lxml.")
        return real(markup, features, *a, **k)

    monkeypatch.setattr(bs4, "BeautifulSoup", no_lxml)
    soup = r.make_soup("<html><body><h1>SONATEL</h1><table><tr><td>x</td></tr></table></body></html>")
    assert soup.find("h1").get_text() == "SONATEL"
    from brvm_alpha.data import live

    monkeypatch.setattr(live, "BeautifulSoup", no_lxml)
    snap = live.parse_live_html("<html><body><p>aucun tableau</p></body></html>")
    assert snap is not None


def test_reread_writes_a_new_version_only_when_the_result_changes():
    from brvm_alpha.notes import research as r

    note = {"tags": ["auto", "doc_lu"], "text": "extrait", "event_type": "RES_S1"}
    old = {"score": 0.25, "tone": 0.5, "s_num": 0.1, "materiality": 0.8, "confidence": 0.835, "risk_flags": [],
           "event_type": "RES_S1", "targets": ["NSBC"], "primary_target": "NSBC", "reading": "lecture", "contradiction": False,
           "extracted": {"rn_growth": -0.11}, "components": {"weights": {"w_num": 0.53}}, "version": "v0"}
    same = {**old, "components": {"weights": {"w_num": 0.53}, "tone_contradicts_numbers": False}, "version": "v1"}
    base = {"tags": ["auto", "doc_lu"], "text": "extrait"}
    assert r._reading_changed(note, old, {**base, "analysis": same}) is False  # seuls des champs techniques changent
    assert r._reading_changed(note, old, {**base, "analysis": {**same, "score": -0.03}}) is True
    assert r._reading_changed(note, old, {**base, "analysis": {**same, "risk_flags": ["R10"]}}) is True
    assert r._reading_changed(note, old, {**base, "analysis": {**same, "extracted": {"rn_growth": -0.11, "rai_label": "x"}}}) is True
    assert r._reading_changed(note, old, {"tags": ["auto", "doc_sans_chiffre"], "text": "extrait", "analysis": same}) is True
    assert r._reading_changed(note, old, {"tags": base["tags"], "text": "autre extrait", "analysis": same}) is True


def test_narrowed_loss_read_in_figures_is_neutral_and_deeper_loss_stays_negative():
    # SUCRIVOIRE S1 2026 (journal réel) : perte de 4,8 Md contre 6,7 Md → ni −2 (« toujours déficitaire ») ni positif.
    a = an.analyze_text("Le résultat net ressort à -4 788 millions de FCFA au 30 juin 2026 contre -6 707 millions de "
                        "FCFA au 30 juin 2025.", title="SUCRIVOIRE CI : Rapport d'activités - 1er semestre 2026",
                        manual_targets=["SCRC"])
    fact = next(t for t in a.matched_terms if t["label"] == "perte nette réduite (toujours une perte)")
    assert fact["weight"] == 0.0 and a.tone == 0.0 and abs(a.score) < 0.05
    assert a.extracted.get("r10_candidate") is None
    b = an.analyze_text("Le résultat net ressort à -1 821 millions de FCFA au 30 juin 2026 contre -557 millions de "
                        "FCFA au 30 juin 2025.", title="SETAO CI : Rapport d'activités - 1er semestre 2026",
                        manual_targets=["STAC"])
    assert any(t["label"] == "résultat net toujours déficitaire" and t["weight"] == -2.0 for t in b.matched_terms)
    assert b.score < -0.5


def test_notes_lire_has_a_reread_option(tmp_path, capsys, monkeypatch):
    from brvm_alpha import cli

    seen = {}

    def fake_enrich(store, **kw):
        seen.update(kw)
        return {"n_candidates": 1, "n_read": 1, "n_enriched": 1, "n_scanned": 0, "n_failed": 0, "n_requests": 0,
                "n_written": 0, "details": []}

    monkeypatch.setattr(cli, "load_enrich_documents", lambda: fake_enrich)
    root = tmp_path / "notes"
    root.mkdir()
    assert cli.main(["notes", "lire", "--hors-ligne", "--relire", "--racine", str(root)]) == 0
    assert seen.get("reread") is True and seen.get("offline") is True
    assert "Relecture des documents déjà lus" in capsys.readouterr().out
    seen.clear()
    assert cli.main(["notes", "lire", "--hors-ligne", "--racine", str(root)]) == 0
    assert "reread" not in seen
    capsys.readouterr()

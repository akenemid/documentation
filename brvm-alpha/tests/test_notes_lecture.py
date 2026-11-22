"""Tests hors ligne de la lecture du CONTENU des publications (``research.enrich_documents``,
``analyze.read_document`` et lecture des tableaux de ``analyze.extract_figures``).

Aucun accès réseau : le transport HTTP est simulé (``FakeWeb`` de ``test_notes_research``) et
l'horloge aussi (les délais de politesse sont vérifiés sans attendre). Les textes viennent :

- d'extraits **réels** du cache de la collecte du 22/11/2026 (``tests/fixtures/notes/lecture_*.txt`` :
  communiqué BOA NIGER du 27/04/2026, communiqué Sonatel du 24/07/2026, alerte ERIUM du
  18/06/2026, communiqué FILTISAC du 07/07/2026), sans donnée personnelle ;
- de cas synthétiques (chiffres fictifs) qui reproduisent la mise en page de ``pdftotext -layout``.

Les PDF servis sont fabriqués à la main (texte en Courier, chasse fixe) et lus par le vrai
``extract_pdf_text`` ; sans ``pdftotext`` sur la machine, leur texte est relu directement.
"""

from __future__ import annotations

import datetime as dt
import re
import shutil
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from brvm_alpha.notes import analyze as an
from brvm_alpha.notes import research as r
from brvm_alpha.notes.model import Note
from brvm_alpha.notes.store import NoteStore
from test_notes_research import FakeClock, FakeWeb, blank_pdf, no_network  # noqa: F401 - fixture autouse importée

FIX = Path(__file__).parent / "fixtures" / "notes"
UTC = dt.timezone.utc
B = "https://www.brvm.org"
F = f"{B}/sites/default/files"
#: Instant de la collecte des notes (dimanche 22/11/2026, 03h40 UTC) puis de la lecture des documents.
NOW = dt.datetime(2026, 11, 22, 3, 40, tzinfo=UTC)
READ_AT = dt.datetime(2026, 11, 22, 12, 0, tzinfo=UTC)


def fixture_text(name: str) -> str:
    """Texte d'une fixture, sans les lignes de commentaire (« # … »), mise en page conservée."""
    lines = (FIX / name).read_text(encoding="utf-8").splitlines()
    return "\n".join(ln for ln in lines if not ln.startswith("#")) + "\n"


# ---------------------------------------------------------------------------
# Cas synthétiques (chiffres fictifs), mis en page comme « pdftotext -layout »
# ---------------------------------------------------------------------------

T3_TROIS_COLONNES = """\
                         RAPPORT D'ACTIVITE DU 3EME TRIMESTRE 2026

I. Tableau d'activité et de résultats

                                                                                        Variation
 Indicateurs en millions de FCFA     3ème trimestre 2026   3ème trimestre 2025   Année 2025      En valeur    En %
 Chiffre d'affaires                        152 340               138 215           187 450         14 125     10,2%
 Résultat d'exploitation                    21 870                18 990            25 310          2 880     15,2%
 Résultat des activités ordinaires          20 115                17 640            23 480          2 475     14,0%
 Résultat net                               15 020                13 410            17 905          1 610     12,0%

II. Commentaires
Le chiffre d'affaires au 30 septembre 2026 s'établit à 152 340 millions de FCFA, en hausse de 10,2 % par rapport à
la même période de 2025. Cette progression traduit la bonne tenue des volumes vendus sur le marché local.
"""

BANQUE_MILLIARDS = """\
 RAPPORT D'ACTIVITE AU 30 SEPTEMBRE 2026

 (en milliards de FCFA)            30/09/2025     30/09/2026     Variation
 Produit Net Bancaire                  82,4           91,3          +10,8%
 Résultat avant impôt                  30,1           36,9          +22,6%
 Résultat net                          25,6           31,2          +21,9%
"""

BENEFICE_VERS_PERTE = """\
 Rapport d'activité du 1er semestre 2026

 En millions de FCFA                 1er semestre 2026    1er semestre 2025    Variation
 Chiffre d'affaires                        41 200               52 300           -21,2%
 Résultat net                              (1 250)               2 480          -150,4%
"""

S1_COMMENTAIRE = """
 Commentaires de la Direction
 L'activité du premier semestre 2026 a été pénalisée par l'arrêt programmé de l'usine pendant six semaines et
 par la hausse du coût des matières premières importées. La société a engagé un plan de réduction des charges.
"""

PERTE_VERS_BENEFICE = """\
 Rapport d'activité du 1er semestre 2026

 En millions de FCFA                 1er semestre 2026    1er semestre 2025    Variation
 Chiffre d'affaires                        52 300               41 200           +26,9%
 Résultat net                               1 840              (3 200)             n.s.
"""

HORS_BORNES = """\
 Rapport d'activité du 1er semestre 2026

 En millions de FCFA                 1er semestre 2026    1er semestre 2025    Variation
 Résultat net                               4 500                  900          +400,0%
"""

VARIATION_INCOHERENTE = """\
 RAPPORT D'ACTIVITE DU 3EME TRIMESTRE 2026

 En millions de FCFA                 3ème trimestre 2026   3ème trimestre 2025   Variation
 Chiffre d'affaires                        152 340               138 215           +18,5%
 Résultat net                               15 020                13 410           +12,0%
"""

SANS_COLONNE_VARIATION = """\
 Situation au 30 juin 2026

 (en millions de FCFA)          30/06/2026      30/06/2025
 Produit Net Bancaire              45 310          41 020
 Résultat net                      12 400          10 850
"""

SANS_EN_TETE_TROIS_MONTANTS = """\
 Rapport d'activité du 3ème trimestre 2026 (en millions de FCFA)

 Résultat net       15 020      13 410      17 905      12,0%
"""

SANS_EN_TETE_DEUX_MONTANTS = """\
 Rapport d'activité du 3ème trimestre 2026 (en millions de FCFA)

 Résultat net       15 020      13 410      12,0%
"""

AVEC_BUDGET = """\
 Rapport d'activité du 3ème trimestre 2026

 En millions de FCFA            Réalisé 2026     Budget 2026     Ecart %
 Chiffre d'affaires                 52 300           50 000         +4,6%
"""

COLONNES_RATIO = """\
 Rapport d'activité au 30 septembre 2026

 En millions de FCFA        30/09/2026    % CA     30/09/2025    % CA
 Chiffre d'affaires            80 000    100,0%       72 000    100,0%
 Résultat net                   6 400      8,0%        5 400      7,5%
"""

TABLEAU_ANNEE_PRECEDENTE = """\
 RAPPORT D'ACTIVITE DU 3EME TRIMESTRE 2026

 En millions de FCFA                 30/09/2025     30/09/2024     Variation
 Chiffre d'affaires                    138 215        126 800         +9,0%
"""

SEMESTRE_SOUS_TITRE_TRIMESTRE = """\
 RAPPORT D'ACTIVITE DU 1ER SEMESTRE 2026

 En millions de FCFA                 30/06/2026     30/06/2025     Variation
 Chiffre d'affaires                    100 000         90 000        +11,1%
 Résultat net                           10 000          8 000        +25,0%
"""

SOCIAL_ET_CONSOLIDE = """\
 Résultats annuels de l'exercice 2025 (en millions de FCFA)

                                          2025          2024      Variation
 Résultat net social                     8 400         7 000        +20,0%
 Résultat net consolidé                 12 600        12 000         +5,0%
"""

DEUX_TABLEAUX_CONCURRENTS = """\
 Rapport d'activité du 3ème trimestre 2026 (en millions de FCFA)

 Trimestre isolé                     T3 2026        T3 2025      Variation
 Résultat net                          5 000          4 000        +25,0%

 Cumul                               30/09/2026     30/09/2025   Variation
 Résultat net                         15 020         13 410        +12,0%
"""


def figs_of(text: str, title: str = "SIGLE CI : Rapport d'activités - 3e trimestre 2026", event: str | None = "ACT_Q3"):
    return an.read_document(text, title, event)


# ---------------------------------------------------------------------------
# Lecture des tableaux : textes réels
# ---------------------------------------------------------------------------


def test_real_boa_niger_table_and_two_column_prose() -> None:
    text = fixture_text("lecture_boa_ng_resultats_2025.txt")
    doc = an.read_document(text, "BOA NG : Communiqué de presse", "OTHER")
    pnb, rn = doc["figures"]["pnb"], doc["figures"]["rn"]
    # Tableau « 2024 | 2025 | Variation | Tendance T1 - 2026 », en millions de F CFA.
    assert pnb["value"] == pytest.approx(21_125e6) and pnb["prev"] == pytest.approx(21_380e6)
    assert pnb["growth"] == pytest.approx(-0.012) and pnb["consistent"] is True and pnb["periods"] == ["2025", "2024"]
    assert rn["value"] == pytest.approx(409e6) and rn["prev"] == pytest.approx(5_002e6)
    assert rn["growth"] == pytest.approx(-0.918) and rn["unit"] == "millions de FCFA"
    # La ligne source est le texte exact du document (espaces réduits).
    assert rn["source"] == "Résultat Net  5 002  409  −91,8%  1 467 (+29%*)"
    assert any(re.sub(r"\s{2,}", "  ", line.strip()) == rn["source"] for line in text.splitlines())
    # Texte sur deux colonnes : « Le Produit Net Bancaire enregistre une baisse » (colonne de gauche) ne
    # doit pas recevoir les « 4,8 milliards » de provision de la colonne de droite.
    assert pnb["origin"] == "table" and not doc["rejected"]
    paragraphs = [p for _, p in an._read_layout(text)["paragraphs"]]
    assert any("baisse de 1,2% à 21,1 milliards FCFA" in p for p in paragraphs)
    assert len(doc["excerpt"]) <= 1500 and "Résultat Net  5 002  409" in doc["excerpt"]


def test_real_sonatel_label_on_its_own_line_and_split_unit_header() -> None:
    text = fixture_text("lecture_sonatel_s1_2026.txt")
    doc = an.read_document(text, "SONATEL SN - Communiqué de Presse", "OTHER")
    ca, rn = doc["figures"]["ca"], doc["figures"]["rn"]
    # « S1 2025 (Milliards / FCFA) | S1 2026 (Milliards / FCFA) | Variation » : N est à droite.
    assert ca["value"] == pytest.approx(1049.8e9) and ca["prev"] == pytest.approx(960.2e9)
    assert ca["growth"] == pytest.approx(0.093) and ca["periods"] == ["S1 2026", "S1 2025"]
    assert rn["value"] == pytest.approx(230.0e9) and rn["prev"] == pytest.approx(208.1e9)
    assert rn["growth"] == pytest.approx(0.105) and rn["unit"] == "milliards de FCFA"
    assert "960,2" in ca["source"] and ca["source"].startswith("Chiffre d’affaires")
    a = an.analyze_text(doc["excerpt"], "SONATEL SN - Communiqué de Presse", document=doc)
    assert a.event_type == "RES_S1" and a.extracted["fiscal_period"] == "2026S1"
    assert a.score > 0.2 and a.extracted["rn_source"] == "Résultat net  208,1  230,0  +10.5 %"


def test_real_erium_profit_warning_sentences() -> None:
    doc = an.read_document(fixture_text("lecture_erium_alerte_2026.txt"), "ERIUM CI : Communiqué - Profit Warning",
                           "PROFIT_WARNING")
    rn, ca = doc["figures"]["rn"], doc["figures"]["ca"]
    assert rn["value"] == pytest.approx(179e6) and rn["prev"] == pytest.approx(377e6)
    assert rn["growth"] == pytest.approx(-0.52) and rn["consistent"] is True  # 179 / 377 − 1 = −52,5 %
    assert ca["growth"] == pytest.approx(0.085) and ca.get("value") is None
    assert "179 millions FCFA, contre 377 millions FCFA" in rn["source"]
    assert doc["has_figures"] and doc["period"] is None  # une alerte n'a pas de période imposée


def test_real_filtisac_document_without_figures() -> None:
    doc = an.read_document(fixture_text("lecture_filtisac_continuite_2026.txt"), "FILTISAC CI : Communiqué", "OTHER")
    assert doc["figures"] == {} and not doc["has_figures"] and not doc["rejected"]
    assert 0 < len(doc["excerpt"]) <= 1500 and "CONTINUITE DE NOS ACTIVITES" in doc["excerpt"]


# ---------------------------------------------------------------------------
# Lecture des tableaux : cas synthétiques
# ---------------------------------------------------------------------------


def test_three_period_columns_millions() -> None:
    doc = figs_of(T3_TROIS_COLONNES)
    ca, rn, rai = (doc["figures"][k] for k in ("ca", "rn", "rai"))
    assert ca["value"] == pytest.approx(152_340e6) and ca["prev"] == pytest.approx(138_215e6)  # pas « Année 2025 »
    assert ca["growth"] == pytest.approx(0.102) and ca["growth_from"] == "pct" and ca["consistent"] is True
    assert ca["periods"] == ["3ème trimestre 2026", "3ème trimestre 2025"] and ca["unit"] == "millions de FCFA"
    assert rn["value"] == pytest.approx(15_020e6) and rn["growth"] == pytest.approx(0.12)
    assert rai["value"] == pytest.approx(20_115e6) and rai["growth"] == pytest.approx(0.14)
    assert doc["period"] == "2026Q3" and doc["period_ok"] is True and not doc["rejected"]
    assert rn["source"] == "Résultat net  15 020  13 410  17 905  1 610  12,0%"
    # L'extrait porte l'en-tête et les lignes du tableau, dans la limite de 1 500 caractères.
    assert len(doc["excerpt"]) <= 1500
    assert "3ème trimestre 2026  3ème trimestre 2025" in doc["excerpt"]
    assert "Résultat net  15 020  13 410" in doc["excerpt"]


def test_billions_table_with_previous_period_first() -> None:
    doc = figs_of(BANQUE_MILLIARDS, "BANQUE CI : Rapport d'activités - 3e trimestre 2026")
    pnb, rn, rai = (doc["figures"][k] for k in ("pnb", "rn", "rai"))
    assert pnb["value"] == pytest.approx(91.3e9) and pnb["prev"] == pytest.approx(82.4e9)
    assert pnb["growth"] == pytest.approx(0.108) and pnb["unit"] == "milliards de FCFA"
    assert rn["value"] == pytest.approx(31.2e9) and rn["growth"] == pytest.approx(0.219)
    assert rai["growth"] == pytest.approx(0.226) and rai["periods"] == ["30/09/2026", "30/09/2025"]
    # Le résultat avant impôt est lu et montré, mais n'entre pas dans le score (document 07 §3.4).
    a = an.analyze_text(doc["excerpt"], "BANQUE CI : Rapport d'activités - 3e trimestre 2026", document=doc)
    assert set(a.components["s_parts"]) == {"rn", "pnb"} and a.extracted["rai_growth"] == pytest.approx(0.226)
    assert "résultat avant impôt 36,9 Md FCFA contre 30,1 Md FCFA (+22,6 %) [non pondéré]" in a.reading


def test_profit_turning_into_loss_is_a_strong_negative() -> None:
    title = "SIGLE CI : Rapport d'activités - 1er semestre 2026"
    doc = figs_of(BENEFICE_VERS_PERTE, title, "RES_S1")
    rn = doc["figures"]["rn"]
    assert rn["value"] == pytest.approx(-1_250e6) and rn["prev"] == pytest.approx(2_480e6)
    assert rn["growth"] == pytest.approx(-1.504) and rn["consistent"] is True
    a = an.analyze_text(doc["excerpt"], title, document=doc)
    assert a.extracted["s_rn"] == -2.0 and a.score < -0.6
    assert "résultat net −1,2 Md FCFA contre 2,5 Md FCFA (−150,4 %)" in a.reading


def test_negative_base_gives_no_numeric_score() -> None:
    title = "SIGLE CI : Rapport d'activités - 1er semestre 2026"
    doc = figs_of(PERTE_VERS_BENEFICE, title, "RES_S1")
    rn = doc["figures"]["rn"]
    assert rn["value"] == pytest.approx(1_840e6) and rn["prev"] == pytest.approx(-3_200e6)
    assert rn["growth"] is None and rn["note"] == an.NOT_COMPARABLE
    a = an.analyze_text(doc["excerpt"], title, document=doc)
    assert "rn" not in a.components["s_parts"] and a.extracted["rn_note"] == "base non comparable"
    assert a.extracted["rn"] == pytest.approx(1_840e6) and a.extracted["rn_growth"] is None
    assert "base non comparable : pas de score numérique" in a.reading
    assert a.extracted["s_ca"] == pytest.approx(26.9 / 25)  # le chiffre d'affaires, lui, reste chiffré


def test_growth_beyond_300_percent_is_not_comparable() -> None:
    title = "SIGLE CI : Rapport d'activités - 1er semestre 2026"
    doc = figs_of(HORS_BORNES, title, "RES_S1")
    rn = doc["figures"]["rn"]
    assert rn["growth"] is None and rn["note"] == an.NOT_COMPARABLE and rn["growth_rejected"] == pytest.approx(4.0)
    a = an.analyze_text(doc["excerpt"], title, document=doc)
    assert a.components["s_parts"] == {} and a.s_num == 0 and a.confidence < 0.6  # ton seul, confiance basse


def test_written_variation_inconsistent_with_amounts_is_rejected() -> None:
    doc = figs_of(VARIATION_INCOHERENTE)
    assert "ca" not in doc["figures"] and doc["figures"]["rn"]["growth"] == pytest.approx(0.12)
    (rej,) = doc["rejected"]
    assert rej["ind"] == "ca" and rej["reason"] == an.INCONSISTENT and "152 340" in rej["source"]
    a = an.analyze_text(doc["excerpt"], "SIGLE CI : Rapport d'activités - 3e trimestre 2026", document=doc)
    assert a.extracted.get("ca") is None and a.extracted.get("ca_growth") is None
    assert set(a.components["s_parts"]) == {"rn"} and a.extracted["doc_rejected"][0]["ind"] == "ca"


def test_growth_recomputed_from_two_amounts_when_header_is_read() -> None:
    doc = figs_of(SANS_COLONNE_VARIATION, "BANQUE CI : Rapport d'activités - 1er semestre 2026", "RES_S1")
    pnb, rn = doc["figures"]["pnb"], doc["figures"]["rn"]
    assert pnb["growth"] == pytest.approx(45_310 / 41_020 - 1) and pnb["growth_from"] == "levels"
    assert rn["growth"] == pytest.approx(12_400 / 10_850 - 1) and rn["periods"] == ["30/06/2026", "30/06/2025"]


def test_unreadable_header_is_ambiguous_unless_row_is_fully_explained() -> None:
    # Trois montants et un pourcentage sans en-tête : lequel est N−1 ? Aucun chiffre.
    doc = figs_of(SANS_EN_TETE_TROIS_MONTANTS)
    assert doc["figures"] == {} and "en-tête du tableau illisible" in doc["rejected"][0]["reason"]
    # Deux montants et leur variation exacte, période du document lue : la ligne s'explique seule.
    doc = figs_of(SANS_EN_TETE_DEUX_MONTANTS)
    rn = doc["figures"]["rn"]
    assert rn["value"] == pytest.approx(15_020e6) and rn["prev"] == pytest.approx(13_410e6)
    assert rn["growth"] == pytest.approx(0.12) and rn.get("periods") is None and rn["header"] is False
    # Même ligne, mais aucune période lisible dans le document : ambigu, donc rien.
    bare = " Chiffres clés (en millions de FCFA)\n\n Résultat net       15 020      13 410      12,0%\n"
    doc = figs_of(bare)
    assert doc["figures"] == {} and doc["period_ok"] is None


def test_budget_columns_are_never_compared() -> None:
    doc = figs_of(AVEC_BUDGET)
    assert doc["figures"] == {} and "budget" in doc["rejected"][0]["reason"]


def test_ratio_columns_are_not_variations() -> None:
    doc = figs_of(COLONNES_RATIO)
    ca, rn = doc["figures"]["ca"], doc["figures"]["rn"]
    assert rn["growth"] == pytest.approx(6_400 / 5_400 - 1) and rn["growth_from"] == "levels"  # ni 8,0 % ni 7,5 %
    assert ca["growth"] == pytest.approx(80_000 / 72_000 - 1)


def test_period_must_match_the_note() -> None:
    # Colonnes 30/09/2025 et 30/09/2024 sous une note du 3e trimestre 2026 : rejet.
    doc = figs_of(TABLEAU_ANNEE_PRECEDENTE)
    assert doc["figures"] == {} and "période du tableau" in doc["rejected"][0]["reason"]
    # Document du 1er semestre rangé sous une note du 3e trimestre : aucun chiffre.
    doc = figs_of(SEMESTRE_SOUS_TITRE_TRIMESTRE)
    assert doc["figures"] == {} and doc["period_ok"] is False and not doc["has_figures"]
    assert all("période" in x["reason"] for x in doc["rejected"])
    # Le même document sous la bonne note est lu.
    doc = figs_of(SEMESTRE_SOUS_TITRE_TRIMESTRE, "SIGLE CI : Rapport d'activités - 1er semestre 2026", "RES_S1")
    assert doc["figures"]["rn"]["growth"] == pytest.approx(0.25) and doc["period_ok"] is True


def test_competing_rows_same_perimeter_required() -> None:
    doc = figs_of(SOCIAL_ET_CONSOLIDE, "SIGLE CI : Etats financiers - Exercice 2025", "RES_ANNUAL")
    rn = doc["figures"]["rn"]
    assert rn["value"] == pytest.approx(12_600e6) and rn["growth"] == pytest.approx(0.05) and rn["perimeter"] == "consolidé"
    # Trimestre isolé et cumul sans rien pour les départager : aucun chiffre.
    doc = figs_of(DEUX_TABLEAUX_CONCURRENTS)
    assert "rn" not in doc["figures"] and any("concurrentes" in x["reason"] for x in doc["rejected"])


def test_closing_dates_only_define_a_period() -> None:
    assert an.period_mentions("Fait à Abidjan, le 18 juin 2026") == set()
    assert an.period_mentions("Comptes arrêtés au 30 juin 2026 et au 31/12/2025") == {"2026S1", "2025A"}
    assert an.period_mentions("Rapport d'activité du 3ème trimestre de l'année 2026 - T1 2026") == {"2026Q3", "2026Q1"}
    assert an.expected_period("X CI : Rapport d'activités - 3e trimestre 2026", "ACT_Q3") == ("Q3", 2026)
    assert an.expected_period("X CI : Rapport d'activités - 2ème trimestre 2026", "RES_S1") == ("S1", 2026)
    assert an.expected_period("X CI : Communiqué", "OTHER") == (None, None)


def test_sentence_guardrails_apply_to_plain_text_too() -> None:
    # Variation écrite (+10 %) incohérente avec les montants (300 contre 200, soit +50 %) : chiffre écarté.
    a = an.analyze_text("Résultat net : 300 millions FCFA contre 200 millions FCFA en 2025, soit +10 %.", "SGBC : Communiqué")
    assert a.extracted.get("rn") is None and a.extracted.get("rn_growth") is None
    assert a.extracted["rn_note"] == an.INCONSISTENT and a.components["s_parts"] == {}
    assert any("incohérentes : chiffre écarté" in w for w in a.warnings)
    ok = an.analyze_text("Résultat net : 300 millions FCFA contre 200 millions FCFA en 2025, soit +50 %.", "SGBC : Communiqué")
    assert ok.extracted["rn_growth"] == pytest.approx(0.5) and a.confidence < ok.confidence
    # Un tableau collé dans une note libre est lu de la même façon.
    figs = an.extract_figures(BANQUE_MILLIARDS)
    assert figs["pnb"]["growth"] == pytest.approx(0.108) and figs["pnb"]["origin"] == "table"


# ---------------------------------------------------------------------------
# Régressions du contrôle manuel du 22/11/2026 : extraits réels des 70 documents lus
# ---------------------------------------------------------------------------


def real_section(name: str) -> str:
    """Section « === NOM === » de ``lecture_extraits_reels.txt`` (lignes « # » retirées)."""
    text = (FIX / "lecture_extraits_reels.txt").read_text(encoding="utf-8")
    body = text.split(f"=== {name} ===\n", 1)[1].split("\n=== ", 1)[0]
    return "\n".join(ln for ln in body.splitlines() if not ln.startswith("#")) + "\n"


S1 = "X CI : Rapport d'activités - 1er semestre 2026"
T3 = "X CI : Rapport d'activités - 3e trimestre 2026"


def test_regression_labels_placed_under_their_numbers() -> None:
    """NESTLE : « Résultat des Activités Ordinaires » est écrit sous ses nombres, « Résultat Net » aussi ;
    le premier passage donnait au premier les nombres du second (+0,4 % au lieu de +8,6 %)."""
    doc = an.read_document(real_section("NESTLE_T3_2026"), T3, "ACT_Q3")
    ca, rai, rn = (doc["figures"][k] for k in ("ca", "rai", "rn"))
    assert ca["value"] == pytest.approx(192_500_938e3) and ca["growth"] == pytest.approx(0.11)
    assert rai["value"] == pytest.approx(21_426_583e3) and rai["prev"] == pytest.approx(19_736_051e3)
    assert rai["growth"] == pytest.approx(0.086) and "Résultat des Activités Ordinaires" in rai["source"]
    assert rn["value"] == pytest.approx(11_986_513e3) and rn["growth"] == pytest.approx(0.004)
    assert rn["unit"].startswith("milliers de FCFA") and rn["periods"] == ["30.09.2026", "30.09.2025"]
    # Un libellé isolé entre deux lignes de nombres, sans rien pour trancher : ambigu, aucun chiffre.
    alone = "\n".join(real_section("NESTLE_T3_2026").splitlines()[:11]) + "\n"
    assert "rai" not in an.read_document(alone, T3, "ACT_Q3")["figures"]


def test_regression_detached_minus_sign_and_delta_amounts() -> None:
    """BERNABE : « 1 857 862 -   139 568 719 » (le second montant est négatif) ; « en hausse de
    +141 MFCFA » est un écart, pas le résultat net (premier passage : « RN = 141 M FCFA », faux)."""
    doc = an.read_document(real_section("BERNABE_S1_2026"), S1, "RES_S1")
    ca, rn, rai = (doc["figures"][k] for k in ("ca", "rn", "rai"))
    assert ca["value"] == pytest.approx(23_160_039_828) and ca["growth"] == pytest.approx(0.07) and ca["unit"] == "FCFA"
    assert rn["value"] == pytest.approx(1_857_862) and rn["prev"] == pytest.approx(-139_568_719)
    assert rn["growth"] is None and rn["note"] == an.NOT_COMPARABLE and rn["sign_note"]
    assert rai["prev"] == pytest.approx(-122_068_719) and "AVANT IMPOT" in rai["source"]
    a = an.analyze_text(doc["excerpt"], S1, document=doc)
    # Aucun score numérique sur le résultat net (base négative) : le retour aux bénéfices se lit dans les mots.
    assert any(t["indicator"] == "rn" and t["weight"] > 0 for t in a.matched_terms)
    assert "rn" not in a.components["s_parts"] and a.score > 0
    t3 = "\n".join(ln for ln in real_section("BERNABE_S1_2026").splitlines() if "Le résultat net en hausse" not in ln)
    doc3 = an.read_document(t3, S1, "RES_S1")
    a3 = an.analyze_text(doc3["excerpt"], S1, document=doc3)
    assert any(t["label"] in ("retour aux bénéfices", "hausse du résultat net") and t["weight"] > 0 for t in a3.matched_terms)
    figs = an.extract_figures("Le résultat net en hausse de +141 MFCFA s'explique par la hausse de la marge commerciale.")
    assert figs.get("rn", {}).get("value") is None


def test_regression_consolidated_table_preferred_over_parent_company() -> None:
    """FILTISAC : comptes sociaux (CA +23 %, RN −770 contre 105) puis consolidés (CA +15 %, « R. net
    part groupe » −673 contre 178) ; l'en-tête « Variation 30-06-2026 vs / 30-06-2025 » n'est pas une période."""
    doc = an.read_document(real_section("FILTISAC_S1_2026"), S1, "RES_S1")
    ca, rn, rai = (doc["figures"][k] for k in ("ca", "rn", "rai"))
    assert ca["value"] == pytest.approx(20_795e6) and ca["prev"] == pytest.approx(18_092e6)
    assert ca["growth"] == pytest.approx(0.15) and ca["perimeter"] == "consolidé"
    assert rn["value"] == pytest.approx(-673e6) and rn["prev"] == pytest.approx(178e6)
    assert rn["growth"] is None and rn["note"] == an.NOT_COMPARABLE and rn["growth_rejected"] == pytest.approx(-4.78)
    assert rai["value"] == pytest.approx(-579e6) and rn["source"] == "R. net part groupe  -673  178  -478 %  -851"
    # La variation écrite (−478 %) concorde avec « −673 » et « 178 » à l'arrondi des millions près.
    assert rn["consistent"] is True and rn["periods"] == ["30 Juin 2026", "30 Juin 2025"]
    a = an.analyze_text(doc["excerpt"], S1, document=doc)
    assert set(a.components["s_parts"]) == {"ca"} and a.score < 0  # bénéfice devenu perte : le ton l'emporte


def test_regression_periods_inside_variation_columns_and_loss_both_years() -> None:
    """SETAO : « Variation en valeur (Juin 2026 - Juin 2025) » n'est pas une colonne de montants."""
    doc = an.read_document(real_section("SETAO_S1_2026"), S1, "RES_S1")
    ca, rn = doc["figures"]["ca"], doc["figures"]["rn"]
    assert ca["value"] == pytest.approx(680_332_341) and ca["prev"] == pytest.approx(2_271_125_021)
    assert ca["growth"] == pytest.approx(-0.70) and ca["unit"] == "FCFA" and ca["periods"] == ["Juin 2026", "Juin 2025"]
    assert rn["value"] == pytest.approx(-1_821_139_763) and rn["growth"] is None and rn["note"] == an.NOT_COMPARABLE
    a = an.analyze_text(doc["excerpt"], S1, document=doc)
    assert any(t["label"] == "résultat net toujours déficitaire" for t in a.matched_terms) and a.score < -0.8


def test_regression_misaligned_header_is_rejected_and_loss_wording() -> None:
    """SETAO au 30/09 : colonnes décalées par rapport à l'en-tête, tableau écarté. La phrase « le résultat
    net est une perte qui s'élève à 346 386 813 F CFA, en baisse de 27 % » donnait +346 M et −27 %."""
    doc = an.read_document(real_section("SETAO_T3_2026"), T3, "ACT_Q3")
    ca, rn = doc["figures"]["ca"], doc["figures"]["rn"]
    assert ca["origin"] == "sentence" and ca["value"] == pytest.approx(3_960_047_624) and ca["growth"] == pytest.approx(0.15)
    assert rn["value"] == pytest.approx(-346_386_813) and rn["growth"] is None and rn["note"] == an.NOT_COMPARABLE
    assert {x["ind"] for x in doc["rejected"]} >= {"ca", "rn"}
    # Le chiffre d'affaires progresse (+15 %) mais la société est en perte : le score ne doit pas être positif.
    a = an.analyze_text(doc["excerpt"], T3, document=doc)
    assert set(a.components["s_parts"]) == {"ca"} and a.score < 0
    assert any(t["label"] == "résultat net négatif (perte)" and t["weight"] == -2.0 for t in a.matched_terms)


def test_regression_split_header_unit_inferred_and_section_heading() -> None:
    """SUCRIVOIRE : « 1er semestre » / « 2026 (1) » sur deux lignes, montants en FCFA sans unité écrite ;
    le titre « 2. Volumes et chiffre d'affaires » ne reçoit pas le « +0,9 % » des volumes."""
    doc = an.read_document(real_section("SUCRIVOIRE_S1_2026"), S1, "RES_S1")
    ca, rn = doc["figures"]["ca"], doc["figures"]["rn"]
    assert ca["value"] == pytest.approx(42_256_666_676) and ca["prev"] == pytest.approx(42_868_302_911)
    assert ca["growth"] == pytest.approx(-0.014268, abs=1e-5) and ca["growth_from"] == "levels"
    assert ca["unit"].startswith("FCFA") and "text_growth" not in ca
    assert rn["value"] == pytest.approx(-4_787_976_545) and rn["prev"] == pytest.approx(-6_707_306_463) and rn["growth"] is None


def test_regression_conflicting_units_settled_by_the_commentary() -> None:
    """ORANGE CI : « (En MXOF) » dans l'en-tête et « Montants en milliards de FCFA » sous le tableau ;
    le commentaire (« 1 012 milliards FCFA ») tranche (premier passage : 1 012 M FCFA, mille fois trop peu)."""
    doc = an.read_document(real_section("ORANGE_T3_2026"), T3, "ACT_Q3")
    ca, rn = doc["figures"]["ca"], doc["figures"]["rn"]
    assert ca["value"] == pytest.approx(1012e9) and ca["prev"] == pytest.approx(876e9) and ca["growth"] == pytest.approx(0.155)
    assert rn["value"] == pytest.approx(141e9) and rn["growth"] == pytest.approx(0.183)
    assert "confirmée par le commentaire" in ca["unit"]
    # Sans le commentaire, les unités contradictoires ne sont pas départagées : montants non convertis.
    table_only = "\n".join(real_section("ORANGE_T3_2026").splitlines()[:11]) + "\n"
    alone = an.read_document(table_only, T3, "ACT_Q3")["figures"]["ca"]
    assert alone["value"] is None and alone["growth"] == pytest.approx(0.155) and "contradictoires" in alone["unit_note"]


def test_regression_quarter_on_quarter_is_not_year_on_year() -> None:
    """LNB : « +15 % par rapport au trimestre précédent » n'est pas la variation retenue."""
    doc = an.read_document(real_section("LNB_T3_2026"), T3, "ACT_Q3")
    ca, rn = doc["figures"]["ca"], doc["figures"]["rn"]
    assert ca["value"] == pytest.approx(77_950e6) and ca["prev"] == pytest.approx(72_479e6) and ca["growth"] == pytest.approx(0.075)
    assert rn["value"] == pytest.approx(1_778e6) and rn["growth"] == pytest.approx(0.72) and rn["consistent"] is True


def test_regression_period_word_above_the_year() -> None:
    doc = an.read_document(real_section("SODECI_S1_2026"), S1, "RES_S1")
    ca, rn, rai = (doc["figures"][k] for k in ("ca", "rn", "rai"))
    assert ca["value"] == pytest.approx(83_974e6) and ca["prev"] == pytest.approx(82_300e6) and ca["growth"] == pytest.approx(0.02)
    assert rn["value"] == pytest.approx(2_667e6) and rn["growth"] == pytest.approx(0.968)  # pas « Exercice 2025 » (4 663)
    assert rai["growth"] == pytest.approx(0.41) and not doc["rejected"]


def test_regression_shifted_header_columns_fall_back_to_sentences() -> None:
    doc = an.read_document(real_section("BICI_S1_2026"), S1, "RES_S1")
    pnb, rn = doc["figures"]["pnb"], doc["figures"]["rn"]
    assert pnb["origin"] == "sentence" and pnb["value"] == pytest.approx(42_637e6) and pnb["growth"] == pytest.approx(0.148)
    assert rn["value"] == pytest.approx(19_948e6) and rn["prev"] == pytest.approx(16_253e6) and rn["growth"] == pytest.approx(0.227)
    assert all("en-tête" in x["reason"] or "alignées" in x["reason"] for x in doc["rejected"])


def test_regression_account_code_before_the_label() -> None:
    doc = an.read_document(real_section("SIB_S1_2026"), S1, "RES_S1")
    pnb, rai, rn = (doc["figures"][k] for k in ("pnb", "rai", "rn"))
    assert pnb["value"] == pytest.approx(56_592e6) and pnb["prev"] == pytest.approx(54_302e6) and pnb["growth"] == pytest.approx(0.04)
    assert rai["value"] == pytest.approx(36_150e6) and rn["value"] == pytest.approx(32_140e6) and rn["growth"] == pytest.approx(0.09)


def test_regression_ratio_year_and_excluded_subject_in_sentences() -> None:
    # « … la progression continue du PNB assurent un coefficient d'exploitation remarquable à 36,7 % » : un ratio.
    assert "pnb" not in an.read_document(real_section("SGCI_S1_PHRASE"), S1, "RES_S1")["figures"]
    # « Le résultat net ressort à 80,4 milliards FCFA, en légère baisse par rapport à 2025 » : 2025 est une année.
    rn = an.read_document(real_section("SGCI_T3_PHRASE"), "X CI : Communiqué de presse", "OTHER")["figures"]["rn"]
    assert rn["value"] == pytest.approx(80.4e9) and rn.get("prev") is None and rn.get("growth") is None
    # Le même extrait sous une note du 3e trimestre : aucune période n'y est lisible, donc aucun chiffre.
    undated = an.read_document(real_section("SGCI_T3_PHRASE"), T3, "ACT_Q3")
    assert undated["figures"] == {} and undated["rejected"][0]["reason"] == "période du document non lisible"
    # NSIA : cases de chiffres clés côte à côte, « capitaux propres hors résultat de l'exercice … +11 % ».
    doc = an.read_document(real_section("NSIA_S1_2026"), S1, "RES_S1")
    pnb, rn = doc["figures"]["pnb"], doc["figures"]["rn"]
    assert pnb["value"] == pytest.approx(53.7e9) and pnb["growth"] == pytest.approx(0.06)
    assert rn["value"] == pytest.approx(14.5e9) and rn["prev"] == pytest.approx(16.3e9) and rn["growth"] == pytest.approx(-0.11)
    assert "text_growth" not in rn and not doc["rejected"]


def test_regression_audit_boilerplate_and_completed_capital_increase_raise_no_flag() -> None:
    """Un rapport des commissaires sans réserve déclenchait R3 (« … sauf si le Conseil a l'intention de mettre
    la société en liquidation ») ; une augmentation de capital achevée, racontée après coup, déclenchait R5."""
    title = "AFRICA GLOBAL LOGISTICS CI : Rapport des Commissaires Aux Comptes sur les états financiers - Exercice 2025"
    doc = an.read_document(real_section("AUDIT_CLAUSE_TYPE"), title, "RES_ANNUAL")
    a = an.analyze_text(doc["excerpt"], title, document=doc, event_hint="RES_ANNUAL")
    assert a.risk_flags == [] and a.score == 0 and a.extracted["ca"] == pytest.approx(92_004e6)
    assert any("clause type" in " ".join(t["modifiers"]) for t in a.matched_terms)
    # Une vraie incertitude sur la continuité d'exploitation reste signalée.
    real = an.analyze_text("Cette situation fait peser une incertitude significative sur la continuité d'exploitation.",
                           "X CI : Rapport des Commissaires Aux Comptes")
    assert "R3" in real.risk_flags
    doc = an.read_document(real_section("SAFCA_T3_AUGMENTATION"), "SAFCA CI : Rapport d'activités - 3e trimestre 2026", "ACT_Q3")
    a = an.analyze_text(doc["excerpt"], "SAFCA CI : Rapport d'activités - 3e trimestre 2026", document=doc, event_hint="ACT_Q3")
    assert "R5" not in a.risk_flags and a.tone >= 0
    notice = an.analyze_text("", "SAFCA CI : Augmentation de capital par apport en numéraire avec DPS")
    assert "R5" in notice.risk_flags  # l'avis de l'opération, lui, garde son filtre


def test_regression_scanner_ocr_text_layer_keeps_only_cross_checked_figures(tmp_path: Path) -> None:
    """NEI-CEDA : texte issu de l'OCR d'un scanner (« t t74 537 800 », « (-) 864 millions »)."""
    text = real_section("NEICEDA_S1_OCR")
    plain = an.read_document(text, S1, "RES_S1")
    assert plain["figures"]["rn"]["value"] == pytest.approx(-864e6)  # « (-) 864 millions » : négatif
    doc = an.read_document(text, S1, "RES_S1", ocr_layer=True)
    assert "rn" not in doc["figures"] and doc["ocr_layer"] is True
    assert any(x["ind"] == "rn" and "OCR" in x["reason"] for x in doc["rejected"])
    # Le chiffre d'affaires est recoupé par l'écart écrit (« soit une baisse de 916 millions ») : il reste.
    ca = doc["figures"]["ca"]
    assert ca["consistent"] is True and ca["value"] == pytest.approx(259e6) and ca["prev"] == pytest.approx(1_175e6)
    assert ca["growth"] == pytest.approx(259 / 1175 - 1)
    # Un PDF fabriqué (police non incorporée, aucune image) n'est pas une couche OCR.
    pdf = tmp_path / "t.pdf"
    pdf.write_bytes(text_pdf(T3_TROIS_COLONNES))
    assert r.pdf_text_layer_is_ocr(pdf) in (False, None)


# ---------------------------------------------------------------------------
# enrich_documents : journal, réseau simulé, PDF fabriqués
# ---------------------------------------------------------------------------


def text_pdf(text: str) -> bytes:
    """PDF d'une page, texte en Courier 7 points (chasse fixe : les colonnes sont conservées)."""

    def esc(s: str) -> bytes:
        b = s.replace("−", "-").encode("cp1252", errors="replace")
        return b.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")

    body = b"BT /F1 7 Tf 9 TL 20 575 Td\n" + b"".join(b"(" + esc(ln) + b") Tj T*\n" for ln in text.splitlines()) + b"ET"
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length " + str(len(body)).encode() + b" >>\nstream\n" + body + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


@pytest.fixture(autouse=True)
def layout_without_pdftotext(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sans ``pdftotext``, le texte des PDF fabriqués est relu dans leur flux (mise en page conservée)."""
    if shutil.which("pdftotext"):
        return
    real = r.extract_pdf_text

    def extract(path: Any, min_chars_per_page: int = r.OCR_MIN_CHARS_PER_PAGE) -> dict[str, Any]:
        data = Path(path).read_bytes()
        lines = re.findall(rb"^\((.*)\) Tj T\*$", data, re.M)
        if b"/BaseFont /Courier" not in data or not lines:
            return real(path, min_chars_per_page)
        text = "\n".join(ln.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\").decode("cp1252")
                         for ln in lines) + "\n"
        chars = len(re.sub(r"\s+", "", text))
        return {"text": text, "n_pages": 1, "chars_per_page": float(chars), "ocr_needed": chars < min_chars_per_page,
                "method": "pdftotext"}

    monkeypatch.setattr(r, "extract_pdf_text", extract)


ROBOTS = (200, (FIX / "robots_brvm.txt").read_bytes(), {"Content-Type": "text/plain"})
PDF_HDR = {"Content-Type": "application/pdf"}

U_T3 = f"{F}/20261030_-_rapport_dactivites_-_3e_trimestre_2026_-_alpha_ci.pdf"
U_S1 = f"{F}/20261030_-_rapport_dactivites_-_1er_semestre_2026_-_alpha_ci.pdf"
U_SCAN = f"{F}/20261029_-_rapport_dactivites_-_3e_trimestre_2026_-_beta_ci.pdf"
U_BAD = f"{F}/20261028_-_rapport_dactivites_-_3e_trimestre_2026_-_gamma_ci.pdf"
U_TXT = f"{F}/20260707_-_communique_-_filtisac_ci.pdf"
U_PW = f"{F}/20261110_-_communique_-_profit_warning_-_erium_ci.pdf"
U_RATING = f"{F}/20261112_-_notation_financiere_-_cie_ci.pdf"
U_404 = f"{F}/20261027_-_rapport_dactivites_-_3e_trimestre_2026_-_delta_ci.pdf"


def pages(**overrides: Any) -> dict[str, Any]:
    out: dict[str, Any] = {
        f"{B}/robots.txt": ROBOTS,
        U_T3: (200, text_pdf(T3_TROIS_COLONNES), PDF_HDR),
        U_S1: (200, text_pdf(BENEFICE_VERS_PERTE + S1_COMMENTAIRE), PDF_HDR),
        U_SCAN: (200, blank_pdf(), PDF_HDR),
        U_BAD: (200, b"%PDF-1.4\nceci n'est pas un PDF lisible\n", PDF_HDR),
        U_TXT: (200, text_pdf(fixture_text("lecture_filtisac_continuite_2026.txt")), PDF_HDR),
        U_PW: (200, text_pdf(fixture_text("lecture_erium_alerte_2026.txt")), PDF_HDR),
    }
    out.update(overrides)
    return out


def make_session(tmp_path: Path, web_pages: dict[str, Any] | None = None, **kw: Any):
    clock = FakeClock()
    web = FakeWeb(pages() if web_pages is None else web_pages, clock)
    kw.setdefault("delay_s", 10.0)
    sess = r.PoliteSession(transport=web, clock=clock, sleep=clock.sleep, cache_dir=tmp_path / "notes" / "cache",
                           log_path=tmp_path / "notes" / "fetch_log.jsonl", now=lambda: READ_AT, **kw)
    return sess, web, clock


def add_note(store: NoteStore, symbol: str, title: str, url: str, event_type: str, published: str = "2026-11-02",
             tags: tuple[str, ...] = ("auto", "liste:rapports_emetteur", "date_estimee"), source: str = "brvm_issuer",
             text: str = "Document de la page « rapports » de l'émetteur (site officiel).") -> str:
    note = Note(title=title, text=text, targets=[symbol], author="auto", source=source, url=url, event_type=event_type,
                published_at=published, created_at=NOW, tags=list(tags))
    note.analysis = an.analyze_note(note).to_dict()
    return store.add(note, now=NOW)


@pytest.fixture()
def journal(tmp_path: Path) -> tuple[NoteStore, dict[str, str]]:
    """Journal de sept notes « titre seul » (score 0,00 pour les rapports), comme après la collecte."""
    store = NoteStore(tmp_path / "notes")
    ids = {
        "t3": add_note(store, "SNTS", "SONATEL SN : Rapport d'activités - 3e trimestre 2026", U_T3, "ACT_Q3"),
        "s1": add_note(store, "SNTS", "SONATEL SN : Rapport d'activités - 1er semestre 2026", U_S1, "RES_S1"),
        "scan": add_note(store, "ORAC", "ORANGE CI : Rapport d'activités - 3e trimestre 2026", U_SCAN, "ACT_Q3",
                         published="2026-10-29"),
        "bad": add_note(store, "SGBC", "SOCIETE GENERALE CI : Rapport d'activités - 3e trimestre 2026", U_BAD, "ACT_Q3",
                        published="2026-10-28"),
        "txt": add_note(store, "FTSC", "FILTISAC CI : Communiqué", U_TXT, "OTHER", published="2026-10-08",
                        tags=("auto", "liste:communiques"), source="brvm_list",
                        text="Liste « Communiqués » de www.brvm.org."),
        "pw": add_note(store, "SIVC", "ERIUM CI : Communiqué - Profit Warning", U_PW, "PROFIT_WARNING",
                       published="2026-11-10", tags=("auto", "liste:communiques"), source="brvm_list",
                       text="Liste « Communiqués » de www.brvm.org."),
        # Hors périmètre de la lecture : liste structurée, BOC, note trop ancienne.
        "div": add_note(store, "SNTS", "SONATEL SN : Paiement de dividendes - exercice 2025",
                        f"{F}/20261009_-_avis_-_paiement_de_dividendes_-_sonatel_sn.pdf", "DIV_NOTICE",
                        tags=("auto", "liste:dividendes"), source="brvm_list"),
        "boc": add_note(store, "SHEC", "Rapport d'activités - 3e trimestre 2026 - VIVO ENERGY CI",
                        f"{F}/boc_20261117_2.pdf", "ACT_Q3", tags=("auto", "liste:boc_communiques"), source="boc"),
        "old": add_note(store, "PALC", "PALM CI : Rapport d'activités - 1er trimestre 2026",
                        f"{F}/20260428_-_rapport_dactivites_-_1er_trimestre_2026_-_palm_ci.pdf", "ACT_Q1",
                        published="2026-04-29"),
    }
    return store, ids


def lines_of(store: NoteStore) -> int:
    return len(store.path.read_text(encoding="utf-8").splitlines())


def by_status(out: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {d["note_id"]: d for d in out["details"]}


def test_selection_priority_breadth_first_and_scope(journal) -> None:
    store, ids = journal
    sel = r.select_documents(store, now=READ_AT)
    # Alerte sur résultats, puis résultats semestriels, puis rapports trimestriels (les plus récents
    # d'abord), puis communiqués ; le 2e document de SONATEL passe après le 1er de chaque émetteur.
    assert [s["note_id"] for s in sel] == [ids[k] for k in ("pw", "s1", "scan", "bad", "txt", "t3")]
    assert [s["round"] for s in sel] == [0, 0, 0, 0, 0, 1]
    assert all(r.is_brvm_document_url(s["url"]) for s in sel)
    assert not r.is_brvm_document_url(f"{F}/boc_20261117_2.pdf") and not r.is_brvm_document_url("https://exemple.test/a.pdf")
    only = r.select_documents(store, now=READ_AT, targets=["SNTS"])
    assert [s["note_id"] for s in only] == [ids["s1"], ids["t3"]]
    # Une notation reste utile 120 séances, un rapport 70.
    later = dt.datetime(2027, 3, 22, 12, 0, tzinfo=UTC)
    assert r.select_documents(store, now=later) == []


def test_enrich_writes_new_versions_with_marks_and_sources(journal, tmp_path: Path) -> None:
    store, ids = journal
    sess, web, _ = make_session(tmp_path)
    before = lines_of(store)
    out = r.enrich_documents(store, session=sess, max_docs=20, now=READ_AT)
    assert (out["n_candidates"], out["n_selected"], out["stopped"]) == (6, 6, None)
    assert (out["n_read"], out["n_enriched"], out["n_no_figure"], out["n_scanned"], out["n_failed"]) == (4, 3, 1, 1, 1)
    assert out["n_requests"] == 7 and out["n_written"] == 6 and lines_of(store) == before + 6  # robots.txt + 6 PDF
    det = by_status(out)
    assert {k: det[ids[k]]["status"] for k in ("t3", "s1", "scan", "bad", "txt", "pw")} == {
        "t3": "enrichie", "s1": "enrichie", "scan": "scan", "bad": "illisible", "txt": "sans_chiffre", "pw": "enrichie"}
    for d in out["details"]:
        assert {"note_id", "symbol", "title", "url", "status", "score_before", "score_after", "extracted"} <= set(d)
    # Politesse : au moins 10 s entre deux requêtes vers www.brvm.org.
    times = [t for (_u, _h, t) in web.calls]
    assert all(b - a >= 10.0 for a, b in zip(times, times[1:]))

    t3 = store.get(ids["t3"])
    v1 = store.get(ids["t3"], version=1)
    assert t3.version == 2 and t3.title == v1.title and t3.url == v1.url and t3.created_at == v1.created_at
    assert t3.tags == ["auto", "liste:rapports_emetteur", "date_estimee", "doc_lu"]
    assert len(t3.text) <= 1500 and "Résultat net  15 020  13 410" in t3.text
    ex = t3.analysis["extracted"]
    assert ex["doc_status"] == "enrichie" and ex["doc_pages"] == 1 and ex["doc_method"] in ("pdftotext", "pdfplumber")
    assert re.fullmatch(r"[0-9a-f]{64}", ex["doc_sha256"]) and ex["doc_chars"] > 500
    assert ex["ca"] == pytest.approx(152_340e6) and ex["ca_growth"] == pytest.approx(0.102)
    assert ex["rn_growth"] == pytest.approx(0.12) and ex["fiscal_period"] == "2026Q3"
    assert ex["rn_source"].startswith("Résultat net  15 020  13 410")  # ligne exacte du document
    assert det[ids["t3"]]["score_before"] == 0.0 and det[ids["t3"]]["score_after"] == t3.analysis["score"] > 0.2
    assert "Chiffres lus dans le document" in t3.analysis["reading"]

    s1 = store.get(ids["s1"])
    assert s1.analysis["extracted"]["rn_growth"] == pytest.approx(-1.504) and s1.analysis["score"] < -0.6

    scan = store.get(ids["scan"])
    assert scan.version == 2 and "doc_scan" in scan.tags and scan.text == store.get(ids["scan"], version=1).text
    assert scan.analysis["extracted"]["doc_status"] == "scan" and scan.analysis["score"] == 0.0
    assert "Document scanné (image sans texte)" in scan.analysis["reading"]

    bad = store.get(ids["bad"])
    assert "doc_illisible" in bad.tags and bad.analysis["extracted"]["doc_status"] == "illisible"
    assert det[ids["bad"]]["reason"]

    txt = store.get(ids["txt"])
    assert "doc_sans_chiffre" in txt.tags and "CONTINUITE DE NOS ACTIVITES" in txt.text and len(txt.text) <= 1500
    assert txt.analysis["extracted"]["doc_status"] == "sans_chiffre" and txt.analysis["extracted"].get("rn") is None

    pw = store.get(ids["pw"])
    assert pw.event_type == "PROFIT_WARNING" and "R9" in pw.analysis["risk_flags"]
    assert pw.analysis["extracted"]["rn_growth"] == pytest.approx(-0.52)
    assert "179 millions FCFA, contre 377 millions FCFA" in pw.analysis["extracted"]["rn_source"]
    # Les notes hors périmètre (dividende structuré, BOC, note ancienne) ne sont pas touchées.
    assert all(store.get(ids[k]).version == 1 for k in ("div", "boc", "old"))


def test_second_pass_reads_nothing(journal, tmp_path: Path) -> None:
    store, _ = journal
    sess, web, _ = make_session(tmp_path)
    r.enrich_documents(store, session=sess, now=READ_AT)
    n_lines, n_calls = lines_of(store), len(web.calls)
    again = r.enrich_documents(store, session=sess, now=READ_AT + dt.timedelta(hours=1))
    assert (again["n_candidates"], again["n_selected"], again["n_requests"], again["details"]) == (0, 0, 0, [])
    assert lines_of(store) == n_lines and len(web.calls) == n_calls
    # Relecture demandée, même code : le cache est relu, rien ne change, aucune version n'est écrite.
    re_read = r.enrich_documents(store, session=sess, now=READ_AT + dt.timedelta(hours=2), reread=True)
    assert re_read["n_selected"] == 6 and re_read["n_written"] == 0 and re_read["n_requests"] == 0
    assert lines_of(store) == n_lines and len(web.calls) == n_calls


def test_past_strict_reads_still_see_the_previous_version(journal, tmp_path: Path) -> None:
    from brvm_alpha.notes import signals

    store, ids = journal
    sess, _, _ = make_session(tmp_path)
    r.enrich_documents(store, session=sess, now=READ_AT)
    past = READ_AT - dt.timedelta(hours=1)  # après la collecte (03h40), avant la lecture (12h00)
    before = store.asof(past, strict=True).set_index("note_id").loc[ids["t3"]]
    assert before["version"] == 1 and before["score"] == 0.0 and "doc_lu" not in before["tags"]
    assert before["text"].startswith("Document de la page « rapports »")
    assert "doc_sha256" not in before["analysis"]["extracted"]
    after = store.asof(READ_AT + dt.timedelta(minutes=1), strict=True).set_index("note_id").loc[ids["t3"]]
    assert after["version"] == 2 and after["score"] > 0.2 and "doc_lu" in after["tags"]
    # Journal en ajout seul : les deux versions restent lisibles, recorded_at = instant de la lecture.
    v1, v2 = store.versions(ids["t3"])
    assert v1.recorded_at == pd.Timestamp(NOW) and v2.recorded_at == pd.Timestamp(READ_AT)
    assert v1.analysis["score"] == 0.0 and v2.analysis["score"] > 0.2
    # Vue stricte des signaux à un instant passé : encore l'ancienne version (aucune anticipation).
    strict = signals.notes_asof(store, past, strict=True)
    if len(strict) and ids["t3"] in set(strict["note_id"]):
        assert strict.set_index("note_id").loc[ids["t3"], "version"] == 1
    frame = signals.all_versions(store) if hasattr(signals, "all_versions") else store.frame(all_versions=True)
    assert sorted(frame[frame["note_id"] == ids["t3"]]["version"]) == [1, 2]


def test_quota_stops_cleanly(journal, tmp_path: Path) -> None:
    store, ids = journal
    sess, web, _ = make_session(tmp_path)
    out = r.enrich_documents(store, session=sess, max_requests=3, now=READ_AT)  # robots.txt + 2 documents
    assert out["stopped"] == "quota de 3 requêtes atteint" and out["n_requests"] == 3
    assert [d["note_id"] for d in out["details"]] == [ids["pw"], ids["s1"]] and out["n_written"] == 2
    assert store.get(ids["t3"]).version == 1 and len(web.calls) == 3
    # Le quota de la session elle-même arrête aussi proprement, sans exception.
    store2 = NoteStore(tmp_path / "autre")
    add_note(store2, "SNTS", "SONATEL SN : Rapport d'activités - 3e trimestre 2026", U_T3, "ACT_Q3")
    add_note(store2, "ORAC", "ORANGE CI : Rapport d'activités - 3e trimestre 2026", U_SCAN, "ACT_Q3")
    sess2, _, _ = make_session(tmp_path / "s2", max_requests=2)
    out2 = r.enrich_documents(store2, session=sess2, now=READ_AT)
    assert "quota" in out2["stopped"] and len(out2["details"]) == 1 and out2["n_requests"] == 2
    # L'appel suivant reprend où le premier s'est arrêté.
    sess3, _, _ = make_session(tmp_path)
    rest = r.enrich_documents(store, session=sess3, now=READ_AT)
    assert rest["stopped"] is None and rest["n_selected"] == 4 and store.get(ids["t3"]).version == 2


@pytest.mark.parametrize("status", [403, 429])
def test_403_or_429_stops_definitively(journal, tmp_path: Path, status: int) -> None:
    store, ids = journal
    sess, web, _ = make_session(tmp_path, pages(**{U_S1: (status, b"refus", {"Content-Type": "text/html"})}))
    out = r.enrich_documents(store, session=sess, now=READ_AT)
    assert f"HTTP {status}" in out["stopped"] and sess.stopped
    det = by_status(out)
    assert det[ids["pw"]]["status"] == "enrichie" and det[ids["s1"]]["status"] == "erreur"
    assert len(out["details"]) == 2 and out["n_failed"] == 1  # rien après le refus
    assert web.urls()[-1] == U_S1 and store.get(ids["s1"]).version == 1 and store.get(ids["t3"]).version == 1
    # Le site est inscrit comme bloqué : une session ultérieure n'envoie plus aucune requête.
    assert "www.brvm.org" in r.blocked_hosts(tmp_path / "notes" / "cache")
    sess2, web2, _ = make_session(tmp_path)
    out2 = r.enrich_documents(store, session=sess2, now=READ_AT)
    assert out2["stopped"] and out2["n_requests"] == 0 and web2.calls == [] and out2["n_written"] == 0


def test_offline_reads_the_cache_only(journal, tmp_path: Path) -> None:
    store, ids = journal
    sess, web, _ = make_session(tmp_path, pages(), max_requests=3)
    r.enrich_documents(store, session=sess, dry_run=True, max_docs=2, now=READ_AT)  # 2 PDF en cache, rien d'écrit
    assert lines_of(store) == 9 and store.get(ids["pw"]).version == 1
    off, web_off, _ = make_session(tmp_path, {}, offline=True)
    out = r.enrich_documents(store, session=off, now=READ_AT)
    assert web_off.calls == [] and out["n_requests"] == 0 and out["offline"] is True
    assert out["n_selected"] == 2 and out["n_skipped"] == 4 and out["stopped"] is None
    assert {d["note_id"] for d in out["details"]} == {ids["pw"], ids["s1"]}
    assert store.get(ids["s1"]).version == 2 and store.get(ids["t3"]).version == 1
    # Sans session fournie : offline=True suffit, le cache du journal est utilisé.
    out2 = r.enrich_documents(tmp_path / "notes", offline=True, now=READ_AT)
    assert out2["n_selected"] == 0 and out2["n_skipped"] == 4 and out2["n_requests"] == 0


def test_isolated_error_writes_nothing_and_does_not_stop(journal, tmp_path: Path) -> None:
    store, ids = journal
    extra = add_note(store, "BOAC", "BOA CI : Rapport d'activités - 3e trimestre 2026", U_404, "ACT_Q3",
                     published="2026-11-03")
    sess, _, _ = make_session(tmp_path)  # U_404 n'est pas servi : HTTP 404
    out = r.enrich_documents(store, session=sess, now=READ_AT)
    det = by_status(out)
    assert det[extra]["status"] == "erreur" and det[extra]["reason"] == "HTTP 404" and not det[extra]["written"]
    assert store.get(extra).version == 1 and out["stopped"] is None and out["n_selected"] == 7
    assert out["n_failed"] == 2 and store.get(ids["t3"]).version == 2  # les autres documents sont lus
    # Le document en erreur reste à lire (aucune marque) : il sera retenté.
    assert [s["note_id"] for s in r.select_documents(store, now=READ_AT)] == [extra]


def test_dry_run_and_reread_after_a_correction(journal, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, ids = journal
    sess, web, _ = make_session(tmp_path)
    dry = r.enrich_documents(store, session=sess, dry_run=True, now=READ_AT)
    assert dry["dry_run"] and dry["n_enriched"] == 3 and dry["n_written"] == 0 and lines_of(store) == 9
    assert by_status(dry)[ids["t3"]]["score_after"] > 0.2 and store.get(ids["t3"]).version == 1
    # Première écriture avec une lecture « fautive » (simulée), puis correction et relecture hors ligne.
    real = an.read_document

    def faulty(text: str, title: str = "", event_type: str | None = None, max_chars: int = 1500, **kw: Any) -> dict[str, Any]:
        doc = real(text, title, event_type, max_chars, **kw)
        if "rn" in doc["figures"] and "3e trimestre" in title:
            doc["figures"]["rn"]["growth"] = 0.99  # chiffre faux
        return doc

    monkeypatch.setattr(an, "read_document", faulty)
    r.enrich_documents(store, session=sess, now=READ_AT)
    assert store.get(ids["t3"]).analysis["extracted"]["rn_growth"] == pytest.approx(0.99)
    monkeypatch.setattr(an, "read_document", real)
    n_calls = len(web.calls)
    off, _, _ = make_session(tmp_path, {}, offline=True)
    fixed = r.enrich_documents(store, session=off, reread=True, now=READ_AT + dt.timedelta(hours=1))
    assert fixed["n_written"] == 1 and len(web.calls) == n_calls  # seule la note fausse est réécrite
    v1, v2, v3 = store.versions(ids["t3"])
    assert v2.analysis["extracted"]["rn_growth"] == pytest.approx(0.99)  # la version fausse reste dans le journal
    assert v3.analysis["extracted"]["rn_growth"] == pytest.approx(0.12) and v3.version == 3
    assert store.get(ids["s1"]).version == 2


def test_reanalysis_keeps_the_document_reading(journal, tmp_path: Path) -> None:
    store, ids = journal
    sess, _, _ = make_session(tmp_path)
    r.enrich_documents(store, session=sess, now=READ_AT)
    before = store.get(ids["t3"]).analysis
    # Une mise à jour d'étiquette relance l'analyse (store.update) : les chiffres du document restent.
    new = store.update(ids["t3"], now=READ_AT + dt.timedelta(hours=1), tags=store.get(ids["t3"]).tags + ["relu"])
    ex = new.analysis["extracted"]
    assert new.version == 3 and ex["doc_status"] == "enrichie" and ex["doc_sha256"] == before["extracted"]["doc_sha256"]
    assert ex["rn_growth"] == pytest.approx(0.12) and ex["rn_source"] == before["extracted"]["rn_source"]
    assert new.analysis["score"] == pytest.approx(before["score"])
    assert r.select_documents(store, now=READ_AT) == []  # toujours « déjà lue »


def test_generic_communique_takes_the_type_read_in_the_document(tmp_path: Path) -> None:
    store = NoteStore(tmp_path / "notes")
    url = f"{F}/20260724_-_communique_de_presse_-_sonatel_sn_0.pdf"
    nid = add_note(store, "SNTS", "SONATEL SN - Communiqué de Presse", url, "OTHER", published="2026-10-20",
                   tags=("auto", "liste:communiques"), source="brvm_list", text="Liste « Communiqués » de www.brvm.org.")
    web_pages = {f"{B}/robots.txt": ROBOTS, url: (200, text_pdf(fixture_text("lecture_sonatel_s1_2026.txt")), PDF_HDR)}
    sess, _, _ = make_session(tmp_path, web_pages)
    out = r.enrich_documents(store, session=sess, now=READ_AT)
    note = store.get(nid)
    ex = note.analysis["extracted"]
    assert out["n_enriched"] == 1 and note.event_type == "RES_S1" and ex["fiscal_period"] == "2026S1"
    assert ex["ca"] == pytest.approx(1049.8e9) and ex["ca_prev"] == pytest.approx(960.2e9)
    assert ex["rn_growth"] == pytest.approx(0.105) and out["details"][0]["score_after"] > 0.2

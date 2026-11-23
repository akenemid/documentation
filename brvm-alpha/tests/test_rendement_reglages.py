"""Réglages, phrases fixes, lexique imposé et arrondi de l'écran (cahier ``docs/RENDEMENT_NET.md``, §1, §1.1, §1.2,
§4.4). Hors ligne ; aucune donnée réelle lue."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from brvm_alpha.portfolio import recommend as R
from brvm_alpha.rendement import reglages as RG

PAQUET = Path(RG.__file__).resolve().parent


# ---------------------------------------------------------------------------
# Réglages
# ---------------------------------------------------------------------------


def test_fichier_de_reglages_lu_et_conforme_aux_defauts():
    assert RG.CHEMIN_REGLAGES.exists()
    r = RG.charger()
    assert r["dates"] == {"debut_suivi": "2026-12-01", "premiere_decision_argent_reel": "2027-06-01",
                          "affirmation_performance": "2029-12-01"}
    # Chaque clé des valeurs par défaut du cahier est présente dans le fichier, avec la même valeur.
    import yaml

    brut = yaml.safe_load(RG.CHEMIN_REGLAGES.read_text(encoding="utf-8"))

    def plat(d, pre=""):
        for k, v in d.items():
            if isinstance(v, dict):
                yield from plat(v, pre + k + ".")
            else:
                yield pre + k, v

    for cle, v in plat(RG.DEFAUTS):
        assert RG.lire(brut, cle, "ABSENT") != "ABSENT", cle
        lu = RG.lire(r, cle)
        assert lu == v, (cle, lu, v)
    assert r["perte"]["choc_2018_ref_publie"] == 0.2932 and r["risque"]["graines"] == 20
    assert r["feux"]["fenetre_trou_seances"] == 126 and r["risque"]["blocs_semaines"] == [8, 26, 52]


def test_reglages_absents_ou_illisibles(tmp_path):
    assert RG.charger(tmp_path / "absent.yaml") == RG.DEFAUTS
    mauvais = tmp_path / "mauvais.yaml"
    mauvais.write_text("dates: [1, 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mauvais.yaml"):
        RG.charger(mauvais)
    assert len(RG.empreinte()) == 64


def test_le_yaml_de_strategie_ne_contient_aucun_parametre_du_module():
    texte = (RG.CHEMIN_REGLAGES.parent / "strategy_v1.yaml").read_text(encoding="utf-8")
    for mot in ("choc_2018_ref_publie", "perte_paliers", "irvm_verifies", "seuil_argent_qui_dort"):
        assert mot not in texte


# ---------------------------------------------------------------------------
# Phrases fixes
# ---------------------------------------------------------------------------


def test_phrases_fixes_reprises_telles_quelles():
    assert RG.BANNER == R.BANNER == "Performance passée ≠ garantie. Aucun gain n'est garanti."
    assert RG.PH_DESCRIPTIF == "Descriptif, pas un test."
    assert RG.PH_INTERETS == "Les intérêts de la réserve ne sont jamais déduits de la perte estimée."
    assert RG.PH_NE_PAS_TRANSMETTRE == "Étude : ne transmettez pas ces ordres à votre courtier."
    assert "5,6 points de moins par an que le marché" in RG.PH_ETUDE and RG.PH_ETUDE.startswith("Étude seulement")
    assert "46,7 %" in RG.PH_RISQUE and "n'est pas une limite" in RG.PH_RISQUE
    assert len(RG.PHRASES_FIXES) == 16


@pytest.mark.parametrize("jour,attendu", [
    ("2026-11-24", "jamais avant le 01/06/2027 (6 mois de suivi sur papier à partir du 01/12/2026)."),
    ("2026-12-02", "jamais avant le 01/06/2027 (6 mois de suivi sur papier depuis le 01/12/2026)."),
    ("2027-06-02", "écrite et signée (suivi sur papier depuis le 01/12/2026)."),
])
def test_phrase_seance_selon_la_date(jour, attendu):
    ph = RG.phrase_seance(jour)
    assert ph.startswith("Prochaine séance : aucun achat. Aucune méthode n'est validée : avec les règles actuelles, "
                         "la plate-forme ne recommandera pas d'argent réel.")
    assert ph.endswith(attendu)
    assert "lundi" not in ph.lower() and "au plus tôt" not in ph
    if jour >= "2027-06-01":
        assert "01/06/2027" not in ph  # la date n'est plus citée comme une date future
    assert RG.mots_interdits(ph) == []


def test_phrase_seance_dates_lues_dans_les_reglages():
    r = RG.charger()
    r["dates"]["debut_suivi"] = "2027-01-04"
    r["dates"]["premiere_decision_argent_reel"] = "2027-07-04"
    assert "jamais avant le 04/07/2027 (6 mois de suivi sur papier à partir du 04/01/2027)" in RG.phrase_seance("2026-12-15", r)


# ---------------------------------------------------------------------------
# Arrondi de l'écran (règle 10)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("x,attendu", [
    (-501_430, "−510\u202f000"), (-10_489, "−11\u202f000"), (118_001, "+110\u202f000"), (400, "entre 0 et +1\u202f000"),
    (-400, "−1\u202f000"), (0, "0"), (-100_000, "−100\u202f000"), (99_999, "+99\u202f000"), (100_000, "+100\u202f000"),
    (-2_598_431, "−2\u202f600\u202f000"), (664_187, "+660\u202f000"),
])
def test_arrondi_ecran(x, attendu):
    assert RG.arrondi_ecran(x) == attendu


def test_arrondi_ecran_frais_et_valeurs():
    assert RG.arrondi_ecran(-284_714, suffixe="de frais") == "290\u202f000 FCFA de frais"
    assert RG.arrondi_ecran(None) == "non calculé" and RG.arrondi_ecran(float("nan")) == "non calculé"
    # Un montant non nul n'est jamais affiché 0 ; une perte grossit, un gain se réduit.
    for x in (-1, -999, -5_000, -123_456, 1, 999, 7_777, 123_456):
        t = RG.arrondi_ecran(x)
        assert t != "0"
        if x < 0:
            assert RG.arrondi_valeur(x) <= x
        elif RG.arrondi_valeur(x):
            assert RG.arrondi_valeur(x) <= x
    assert RG.fcfa(93_094.5) == "93\u202f095 FCFA"  # détail : round_fcfa, demi vers le haut


# ---------------------------------------------------------------------------
# Lexique imposé (§1.1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("texte", [
    "Sûreté, frais et impôt non vérifiés.", "Certaines lignes peuvent ne pas être servies.",
    "Revenez au plus tôt.", "Ce que prend votre courtier (SGI).", "BRVM Alpha ne garantit rien : aucun gain n'est garanti.",
    "Ce ne sont pas des limites ni un plafond.", "Montant en actions : 3 000 000 FCFA sur 12 mois.",
    "Le passé rejoué flatte : une année ordinaire du passé.",
    "Ce montant n'est pas un plafond.",
])
def test_lexique_permet(texte):
    assert RG.mots_interdits(texte) == []


@pytest.mark.parametrize("texte,mot", [
    ("La médiane vaut 11,8 %.", "médiane"), ("Le P10 est de −9,9 %.", "P10"), ("Le stress ST2.", "stress"),
    ("Une perte maximale de 1 000 000 FCFA.", "perte maximale"), ("Un gain sûr.", "sûr"), ("Un montant certain.", "certain"),
    ("Votre poche d'actions.", "poche"), ("Le drawdown de 2018.", "drawdown"), ("La SGI facture.", "SGI (seul)"),
    ("Le reliquat d'arrondi.", "reliquat"), ("Le suivi S2 commence.", "S2"), ("La référence REF.", "REF"),
    ("Vous perdez au plus 500 000 FCFA.", "au plus"), ("Le bootstrap rejoue.", "bootstrap"),
    ("Ces frais évités rapporte.", "rapporte"), ("Un capital protégé.", "protégé"), ("L'IRVM est retenu.", "IRVM"),
])
def test_lexique_refuse(texte, mot):
    assert mot in RG.mots_interdits(texte)


def test_lexique_risque_et_phrases_fixes_blanches():
    assert RG.mots_interdits("Vous êtes sous la perte acceptée.", en_plus=RG.INTERDITS_RISQUE) == ["sous la perte acceptée"]
    for ph in RG.PHRASES_FIXES.values():
        assert RG.mots_interdits(ph) == [], ph
    assert RG.compter_mots("Un point d'intérêt vaut 100 000 FCFA par an.") == 8


# ---------------------------------------------------------------------------
# Gardes du paquet : aucun réseau, aucune commande validate ou backtest, aucun nom de modèle
# ---------------------------------------------------------------------------


def _sources():
    return sorted(PAQUET.glob("*.py"))


def test_paquet_sans_reseau_ni_validation():
    interdits = {"urllib", "requests", "socket", "http", "httpx", "aiohttp"}
    for f in _sources():
        arbre = ast.parse(f.read_text(encoding="utf-8"))
        for n in ast.walk(arbre):
            if isinstance(n, ast.Import):
                assert not {a.name.split(".")[0] for a in n.names} & interdits, f
            elif isinstance(n, ast.ImportFrom) and n.module:
                assert n.module.split(".")[0] not in interdits, f
                assert "validation.runner" not in n.module and "backtest.engine" not in n.module, f
        texte = f.read_text(encoding="utf-8")
        assert not re.search(r"run_validation|execute_run|Backtester\(", texte), f
        assert ("cl" + "aude") not in texte.lower(), f  # aucun nom d'outil de rédaction dans le code


def test_aucune_ecriture_hors_du_profil():
    """Seule ``grille.enregistrer`` écrit (dans ``<données>/profil/``, hors dépôt) : aucun fichier du paquet n'écrit
    dans ``reports/`` (S1 publié, registre des essais) ni dans ``configs/``."""
    for f in _sources():
        texte = f.read_text(encoding="utf-8")
        assert ".to_parquet(" not in texte and ".to_csv(" not in texte, f
        if f.name != "grille.py":
            assert "write_text(" not in texte and "write_bytes(" not in texte and "open(" not in texte, f

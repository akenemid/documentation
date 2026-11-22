"""F6 — Lectures du risque (cahier ``docs/RENDEMENT_NET.md``, §F6). Recette sur l'ordre figé du 20/11/2026 et sur
les indices TR figés (fenêtre de l'ordre) ; règle de renormalisation vérifiée sur un panel de synthèse.

Statistiques descriptives d'un seul passé : aucune règle n'est simulée."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import rendement_jeux as J
from brvm_alpha.portfolio import recommend as R
from brvm_alpha.rendement import reglages as RG
from brvm_alpha.rendement import rendu as RD
from brvm_alpha.rendement import risque as RQ


@pytest.fixture(scope="module")
def o10():
    return J.ordre("10M")


@pytest.fixture(scope="module")
def lec(o10):
    return RQ.lectures(o10, J.panels_tr())


@pytest.fixture(scope="module")
def per(o10):
    return RQ.periodes_reelles(o10, J.panels_tr())


def _l(lec, fam, bloc):
    return next(x for x in lec["lectures"] if x["famille"] == fam and x["bloc"] == bloc)


def test_lecture_1_graine_0_identique_a_la_distribution_de_l_ordre(o10, lec):
    g0 = _l(lec, "passe_rejoue", 8)["graine_0"]
    d = o10["distribution"]
    assert g0["p_perte"] == d["p_perte"]
    assert abs(g0["mediane"] - d["mediane"]) < 1e-6 and abs(g0["p10"] - d["p10"]) < 1e-6
    assert lec["n_semaines"] == d["n_semaines"] == 492 and lec["frais_deduits"] == d["frais_deduits"]
    assert len(lec["graines"]) == 20


TABLE = [  # famille, bloc, perte (g0 ; médiane), ordinaire (g0 ; médiane), une sur dix (g0 ; médiane), une sur vingt
    ("passe_rejoue", 8, (0.256, 0.255), (0.118, 0.118), (-0.099, -0.099), (-0.150, -0.154)),
    ("passe_rejoue", 26, (0.300, 0.306), (0.130, 0.126), (-0.148, -0.148), (-0.221, -0.218)),
    ("passe_rejoue", 52, (0.318, 0.328), (0.160, 0.137), (-0.164, -0.166), (-0.246, -0.249)),
    ("marche_charge", 8, (0.341, 0.346), (0.066, 0.064), (-0.131, -0.131), (-0.175, -0.179)),
    ("marche_charge", 26, (0.376, 0.382), (0.074, 0.069), (-0.171, -0.173), (-0.229, -0.229)),
    ("marche_charge", 52, (0.381, 0.396), (0.091, 0.073), (-0.190, -0.193), (-0.244, -0.245)),
]


@pytest.mark.parametrize("fam,bloc,perte,ordi,dix,vingt", TABLE)
def test_recette_des_lectures(lec, fam, bloc, perte, ordi, dix, vingt):
    x = _l(lec, fam, bloc)
    for cle, (a, b) in (("p_perte", perte), ("mediane", ordi), ("p10", dix), ("p5", vingt)):
        assert abs(x["graine_0"][cle] - a) <= 0.001 + 1e-9, (cle, x["graine_0"][cle], a)
        assert abs(x["mediane_graines"][cle] - b) <= 0.001 + 1e-9, (cle, x["mediane_graines"][cle], b)
    lo, hi = x["min_max_graines"]["p_perte"]
    assert lo <= x["mediane_graines"]["p_perte"] <= hi
    if fam == "passe_rejoue":
        pire = {8: -0.391, 26: -0.422, 52: -0.441}[bloc]
        assert abs(x["graine_0"]["pire"] - pire) <= 0.001
    if (fam, bloc) == ("marche_charge", 52):
        assert abs(lo - 0.381) <= 0.001 and abs(hi - 0.409) <= 0.001  # écart dû au seul tirage : 2,8 points


def test_periodes_reelles(per):
    h = per["horizons"]["12"]
    assert h["n"] == 107 and abs(h["n_perte"] - 37) <= 1 and abs(h["p10"] + 0.1945) <= 0.001
    assert abs(h["pire"] + 0.267) < 0.001 and h["pire_depart"] == "2018-03"
    assert h["par_annee"]["2017"] == 12 and h["par_annee"]["2018"] == 12 and h["par_annee"]["2019"] == 10
    assert h["par_annee"]["2020"] == 1 and abs(h["par_annee"].get("2022", 0) - 2) <= 1
    for H, n, pire in (("24", 95, -0.3665), ("36", 83, -0.4311)):
        x = per["horizons"][H]
        assert x["n"] == n and abs(x["pire"] - pire) < 0.001
        assert "part_perte" not in x and "n_perte" not in x and x["phrase"] == RQ.PHRASE_CHEVAUCHEMENT
    assert per["phrases"] == [RG.PH_PASSE, RG.PH_DESCRIPTIF]


def test_synthese(lec, per):
    s = RQ.synthese(lec, per)
    # Le cahier écrit « environ 26 % » : arrondi en deux temps (25,48 % → 25,5 % → 26 %). La règle du §F6 (bornes
    # arrondies au point entier) donne 25 % : c'est la valeur gardée.
    assert s["frequence_min"] == 25 and s["frequence_max"] == 40
    assert s["une_sur_dix_haut"] == -10 and s["une_sur_dix_bas"] == -19
    assert s["phrase"] == ("Selon la façon de compter et le tirage, environ 25 % à 40 % des périodes de 12 mois ont fini en "
                           "perte, et une année sur dix a fini sous −10 % à −19 %.")


def test_concentration(o10):
    c = RQ.concentration(o10, 1_000_000)
    assert abs(c["poids_deux_premieres"] - 0.435) < 0.001 and round(c["lignes_effectives"], 1) == 7.9
    sn = c["lignes"][0]
    assert sn["symbole"] == "SNTS" and sn["perte_choc"] == 762_348 and abs(sn["part_de_X"] - 0.762348) < 1e-9
    assert [x["symbole"] for x in c["lignes"][:2]] == ["SNTS", "ORAC"]
    assert all(x["poids"] > 0.05 for x in c["lignes"][2:])
    assert abs(sum(x["poids"] for x in c["lignes"][:2]) - c["poids_deux_premieres"]) < 1e-12


def test_renormalisation_ligne_cotee_en_cours_de_route():
    idx = pd.bdate_range("2023-01-02", periods=600)
    a = pd.Series(100.0 * np.cumprod(np.full(600, 1.001)), index=idx)
    b = pd.Series(np.nan, index=idx)
    b.iloc[300:] = 50.0 * np.cumprod(np.full(300, 0.999))
    tr = pd.DataFrame({"AAA": a, "BBB": b})
    niv = RQ.niveau_quotidien(tr, {"AAA": 0.5, "BBB": 0.5}, idx[0], idx[-1])
    r = niv.pct_change().dropna()
    # Avant la cotation de BBB (et le jour de sa première cote) : tout le poids sur AAA (pas 0 % pour BBB).
    assert np.allclose(r.iloc[:300].to_numpy(), 0.001)
    # À partir du premier rendement de BBB (lendemain de sa première cote) : moyenne des deux lignes.
    assert np.allclose(r.iloc[300:].to_numpy(), 0.5 * 0.001 + 0.5 * -0.001)
    # Un jour sans cours après cotation compte 0 %.
    tr2 = tr.copy()
    tr2.iloc[400, 1] = np.nan
    r2 = RQ.niveau_quotidien(tr2, {"AAA": 0.5, "BBB": 0.5}, idx[0], idx[-1]).pct_change().dropna()
    assert abs(r2.iloc[399] - 0.5 * 0.001) < 1e-12


def test_lectures_sur_panel_de_synthese_et_jeu_court(tmp_path):
    P = J.panel_synthese(n_jours=700)  # environ 32 mois : assez pour des périodes de 12 mois
    O = J.ordre_synthese(P, 5_000_000, tmp_path)
    lec = RQ.lectures(O, P, graines=3)
    g0 = next(x for x in lec["lectures"] if x["famille"] == "passe_rejoue" and x["bloc"] == 8)["graine_0"]
    # La distribution de l'ordre a été tirée avec 300 tirages : même calcul, même graine.
    lec300 = RQ.lectures(O, P, graines=[0], n_boot=300, blocs=[8])
    g300 = lec300["lectures"][0]["graine_0"]
    assert g300["p_perte"] == O.distribution["p_perte"] and abs(g300["mediane"] - O.distribution["mediane"]) < 1e-9
    assert set(g0) >= {"p_perte", "mediane", "p10", "p5", "pire"}
    per = RQ.periodes_reelles(O, P)
    assert per["disponible"] and per["horizons"]["12"]["n"] > 0 and per["horizons"]["24"]["n"] > 0
    court = {"tr_index": P["tr_index"].iloc[-200:], "market_tr": P["market_tr"].iloc[-200:]}
    assert not RQ.periodes_reelles(O, court)["disponible"]


def test_phrases_et_libelle_dans_les_formes(lec, per, o10):
    rn = {"risque": {"lectures": lec["lectures"], "periodes_reelles": per, "synthese": RQ.synthese(lec, per),
                     "libelle_p_battre_tr": RQ.LIBELLE_P_BATTRE_TR}}
    blocs = RD.blocs_distribution(rn)
    md, html = RD.fragment(blocs, "md"), RD.fragment(blocs, "html")
    for t in (md, html.replace("&#x27;", "'")):
        assert RG.PH_PASSE in t and RG.PH_DESCRIPTIF in t and RG.PH_FLATTE in t
        assert "P(battre le TR)" not in t and "Fréquence passée au-dessus du marché" in t
    assert "p_battre_tr" in o10["distribution"]
    assert "<script" not in html and "http" not in html


def test_fenetre_de_l_ordre_et_jamais_au_dela(o10):
    a, b = RQ.fenetre(o10)
    assert a == pd.Timestamp("2017-01-02") and b == pd.Timestamp("2026-11-20")
    wk = RQ.hebdo(o10, J.panels_tr())
    assert wk.index.max() <= b and (wk.index - pd.Timedelta(days=4)).min() >= a
    assert R.BLOCK_WEEKS == 8

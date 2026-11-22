"""F3 — Du brut au net (cahier ``docs/RENDEMENT_NET.md``, §F3). Recette sur les ordres figés du 20/11/2026
(1 M, 10 M, 50 M ; tarif supposé central) et identités sur le panel de synthèse."""

from __future__ import annotations

import copy

import pytest

import rendement_jeux as J
from brvm_alpha.rendement import bilan as B
from brvm_alpha.rendement import grille as G
from brvm_alpha.rendement import reglages as RG

RECETTE = {
    # capital : frais et impôt an1, suivantes, dividendes moins frais an1, suivantes, parts, −20 %, remise à niveau, AR
    "1M": (120_531, 107_041, -77_198, -63_708, 0.978, 0.978, -84_890, (3_252, 12_300), 26_980,
           {"grille": 110_344, "execution": 2_714, "taux_impot_non_verifie": 623, "dividendes_estimes": 4_252}),
    "10M": (340_241, 179_653, 151_274, 311_862, 0.915, 0.898, 64_076, (34_745, 123_000), 321_176,
            {"grille": 215_226, "execution": 40_536, "taux_impot_non_verifie": 7_081, "dividendes_estimes": 48_446}),
    "50M": (1_390_456, 503_083, 1_096_406, 1_983_779, 0.895, 0.868, 655_249, (189_831, 615_000), 1_774_746,
            {"grille": 682_702, "execution": 280_269, "taux_impot_non_verifie": 35_807, "dividendes_estimes": 245_270}),
}


@pytest.mark.parametrize("cap", sorted(RECETTE))
def test_recette_du_tableau_de_controle(cap):
    f1, f2, r1, r2, ps, psf, r20, rn, ar, levee = RECETTE[cap]
    b = B.bilan_fuites(J.ordre(cap))
    t = b["totaux"]
    assert (t["fuites_an1"], t["fuites_suivantes"], t["reste_an1"], t["reste_suivant"]) == (f1, f2, r1, r2)
    assert abs(t["part_supposee"] - ps) < 0.001 and abs(t["part_supposee_frais"] - psf) < 0.001
    assert next(x["reste_an1"] for x in b["dividendes_en_baisse"] if x["chute"] == 0.20) == r20
    assert abs(b["remise_a_niveau"]["bas"] - rn[0]) <= 1 and abs(b["remise_a_niveau"]["haut"] - rn[1]) <= 1
    assert b["aller_retour"]["cout"] == ar
    assert t["levee_par"] == levee
    assert sum(levee.values()) == t["supposee_fcfa"]  # la somme des quatre cases redonne la part supposée au franc


def test_valeurs_10M_detail():
    o = J.ordre("10M")
    b = B.bilan_fuites(o)
    t = b["totaux"]
    assert (t["supposee_fcfa"], t["supposee_frais_fcfa"], t["frais_an1"]) == (311_289, 255_762, 284_714)
    assert t["par_action"] == {"aucune": 84_479, "négociable": 101_330, "selon le courtier": 100_000,
                               "à vérifier": 13_896, "exécution": 40_536}
    assert next(x["reste_an1"] for x in b["dividendes_en_baisse"] if x["chute"] == 0.075) == 118_575
    assert abs(b["aller_retour"]["pct_investi"] - 0.0333) < 0.0001
    rouges = [x["symbole"] for x in b["lignes_petites"] if x["niveau"] == "rouge"]
    oranges = {x["symbole"] for x in b["lignes_petites"] if x["niveau"] == "orange"}
    assert rouges == ["NTLC"] and oranges == {"BICB", "NSBC", "BOABF", "BOAS", "CIEC", "SPHC", "ONTBF", "TTLC"}
    ntlc = next(x for x in b["lignes_petites"] if x["symbole"] == "NTLC")
    assert (ntlc["frais_annuels"], ntlc["dividende_net"]) == (5_416, 4_805)
    b1 = B.bilan_fuites(J.ordre("1M"))
    assert sum(x["niveau"] == "rouge" for x in b1["lignes_petites"]) == 18
    assert {x["symbole"] for x in b1["lignes_petites"] if x["niveau"] == "orange"} == {"SNTS", "ORAC"}
    assert not any(x["niveau"] for x in B.bilan_fuites(J.ordre("50M"))["lignes_petites"])


@pytest.mark.parametrize("cap", ["1M", "10M", "50M"])
def test_identite_somme_des_lignes(cap):
    o = J.ordre(cap)
    b = B.bilan_fuites(o)
    t = b["totaux"]
    assert t["controle_ecart"] == 0 and t["controle_couts_total"] == 0
    E = sum(x["montant"] for x in b["lignes"] if x["code"].startswith("E"))
    A = sum(x["montant"] for x in b["lignes"] if x["code"].startswith("A"))
    T = next(x["montant"] for x in b["lignes"] if x["code"] == "T")
    assert E == o["couts"]["total"] and T + E + A == t["fuites_an1"]
    assert t["dividendes_nets"] == o["revenus"]["net"]
    for x in b["lignes"]:  # chaque ligne a un statut et une action possible
        assert x["statut"] in (RG.FAIT, RG.ESTIMATION, RG.HYPOTHESE) and x["action"]
        assert x["mot_statut"] in ("compté", "estimé", "supposé")


def test_identite_sur_le_panel_de_synthese(tmp_path):
    P = J.panel_synthese()
    O = J.ordre_synthese(P, 5_000_000, tmp_path)
    b = B.bilan_fuites(O)
    t = b["totaux"]
    assert t["controle_ecart"] == 0 and t["controle_couts_total"] == 0
    assert t["entree"] == O.couts["total"] and t["dividendes_nets"] == O.revenus["net"]


def test_dividendes_nuls_et_portefeuille_detenu_sans_ordre():
    o = copy.deepcopy(J.ordre("10M"))
    o["revenus"] = {**o["revenus"], "brut": 0, "irvm": 0, "net": 0}
    o["dividendes"] = []
    b = B.bilan_fuites(o)
    assert b["totaux"]["pct_brut_an1"] is None and all(x["pct_brut"] is None for x in b["lignes"])
    assert b["totaux"]["ratio_annuels_dividendes"] is None
    d = B.bilan_fuites(J.ordre("detenu_624840"))
    assert d["totaux"]["entree"] == 0 and d["aller_retour"]["cout"] == 0


def test_leviers_tableaux_separes_et_valeurs():
    o = J.ordre("10M")
    lv = B.leviers(o, arrondi={"francs_ajoutes": 65_485},
                   lectures={"ordinaire_prudente": 0.066, "ordinaire_flatteuse": 0.118, "une_sur_dix_flatteuse": -0.099,
                             "une_sur_dix_prudente": -0.131, "une_sur_dix_periodes": -0.1945},
                   reinvestir={"remis_au_travail_moyen": 127_497})
    A = {x["geste"]: x for x in lv["frais_evites"]}
    assert A["Courtier sans tenue de compte par ligne"]["par_an"] == 100_000
    assert A["Droits de garde à 0,10 % au lieu de 0,25 %"]["par_an"] == 14_475
    c = A["Courtage à 0,50 % au lieu de 0,80 %"]
    assert c["une_fois"] == 34_158 and c["equivalent_annuel"] == 11_386
    ens = next(x for x in lv["frais_evites"] if x["geste"].startswith("Ensemble"))
    assert (ens["premiere_annee"], ens["par_an"], ens["une_fois"]) == (73_224, 96_000, -22_776)
    borne = next(x for x in lv["frais_evites"] if x.get("borne_non_attestee"))
    assert (borne["premiere_annee"], borne["par_an"]) == (130_158, 96_000)
    assert lv["phrase_frais_evites"] == RG.PH_ECONOMIE and lv["phrase_argent_place"] == RG.PH_PLACE
    # La taxe sur le courtage n'apparaît jamais dans le tableau A ; les lignes du tableau B n'y apparaissent jamais.
    assert not any("taxe" in x["geste"].lower() for x in lv["frais_evites"])
    noms_b = {x["changement"] for x in lv["argent_place"]}
    assert noms_b and not noms_b & {x["geste"] for x in lv["frais_evites"]}
    for x in lv["frais_evites"]:
        assert RG.mots_interdits(" ".join(str(v) for v in x.values())) == []
    ar = next(x for x in lv["argent_place"] if x["changement"].startswith("Arrondi"))
    assert ar["francs"] == 65_485 and abs(ar["dividendes"] - 2_960) <= 5
    rv = next(x for x in lv["argent_place"] if x["changement"].startswith("Réinvestissement"))
    assert rv["francs"] == 127_497 and abs(rv["dividendes"] - 5_760) <= 5
    inc = {x["inconnue"]: x for x in lv["inconnues"]}
    assert inc["Taxe sur le courtage"]["si_10pct"] == -6_175 and inc["Minimum par ordre"]["surcout"] == 13_841
    assert inc["Taxe sur les frais annuels"]["surcout_annuel"] == 22_343


def test_grille_sans_frais_par_ligne_et_sans_objet():
    o = J.ordre("10M")
    fgi = G.exemples()["sans_frais_par_ligne"]
    r = G.comparer(o, {"fgi": fgi})[0]
    assert (r["premiere_annee"], r["frais_annuels"], r["ecart_premiere_annee"], r["ecart_annuel"]) == (211_490, 28_126, -73_224, -96_000)
    lv = B.leviers(o, G.defaut().avec(tenue_par_ligne=0))
    premier = lv["frais_evites"][0]
    assert premier["sans_objet"] and premier["condition"].startswith("sans objet")


def test_grille_ecrite_rend_les_postes_faits():
    o = J.ordre("10M")
    g = G.defaut()
    for k in G.PRINCIPAUX + ("courtage_min_par_ordre",):
        g.champs[k].statut = G.ECRITE
    b = B.bilan_fuites(o, g)
    st = {x["code"]: x["statut"] for x in b["lignes"]}
    assert st["E1"] == st["E2"] == st["A1"] == st["A2"] == st["A3"] == RG.FAIT
    assert st["E5"] == st["E6"] == RG.ESTIMATION
    lev = b["totaux"]["levee_par"]
    assert lev["grille"] == 0 and lev["execution"] == 40_536
    assert b["totaux"]["supposee_fcfa"] == 311_289 - 215_226


def test_vente_aller_retour_et_amortissement():
    o = J.ordre("partiel")
    ar = B.aller_retour(o)
    assert ar["cout"] == 2 * o["couts"]["total"] and set(ar["par_an"]) == {"1", "3", "5"}
    a = B.amortissement({"dividendes": 435_988, "frais_annuels": 124_126, "frais_achat": 160_588})
    assert round(a["mois_frais_achat"], 1) == 6.2 and round(a["mois_achat_revente"], 1) == 12.4
    assert B.amortissement({"dividendes": 38_458, "frais_annuels": 102_166, "frais_achat": 13_490})["jamais"]


@pytest.mark.parametrize("cap", ["1M", "10M", "50M"])
def test_grille_par_defaut_donnee_identique_au_tarif_de_l_ordre(cap):
    o = J.ordre(cap)
    a, b = B.bilan_fuites(o), B.bilan_fuites(o, G.defaut())
    assert [x["montant"] for x in a["lignes"]] == [x["montant"] for x in b["lignes"]]
    assert a["totaux"]["fuites_an1"] == b["totaux"]["fuites_an1"] and b["totaux"]["controle_couts_total"] == 0


def test_grille_sans_frais_par_ligne_recalcule_le_bilan():
    t = B.bilan_fuites(J.ordre("10M"), G.exemples()["sans_frais_par_ligne"])["totaux"]
    assert (t["frais_an1"], t["annuels"], t["entree"]) == (211_490, 28_126, 183_364)
    assert abs(t["ratio_annuels_dividendes"] - 0.065) < 0.001


@pytest.mark.parametrize("cap,ratio", [("1M", 2.657), ("10M", 0.285), ("50M", 0.101)])
def test_frais_annuels_sur_dividendes_nets(cap, ratio):
    assert abs(B.bilan_fuites(J.ordre(cap))["totaux"]["ratio_annuels_dividendes"] - ratio) < 0.001


def test_amortissement_des_poches():
    from brvm_alpha.rendement import perte as P

    o = J.ordre("10M")
    p3 = P.poche(o, 3_000_000)
    a3 = B.amortissement({"dividendes": p3["dividendes"], "frais_annuels": p3["frais_annuels"], "frais_achat": p3["frais_achat"]})
    assert round(a3["mois_frais_achat"], 1) == 28.3 and round(a3["mois_achat_revente"], 1) == 56.5
    p34 = P.poche(o, 3_400_000, grille=G.exemples()["sans_frais_par_ligne"])
    a34 = B.amortissement({"dividendes": p34["dividendes"], "frais_annuels": p34["frais_annuels"],
                           "frais_achat": p34["frais_achat"]})
    assert round(a34["mois_frais_achat"], 1) == 5.3 and round(a34["mois_achat_revente"], 1) == 10.7

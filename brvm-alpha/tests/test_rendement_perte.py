"""F4 — Ce que j'accepte de risquer → montant en actions ; F5 — la réserve (cahier ``docs/RENDEMENT_NET.md``, §F4,
§F5). Recette sur les ordres figés du 20/11/2026 ; vérification par l'ordre complet sur le panel de synthèse.

Le choc de 2018 est **mesuré** sur les fichiers S1 publiés (lecture seule de ``reports/validation_S1``) et sur des
cours de 2018 figés : 0,293209, retenu arrondi à 4 décimales comme dans le cahier (0,2932) : les montants « haut » et
P_vérifiée du cahier sont retrouvés au franc."""

from __future__ import annotations

import copy
import hashlib
import math

import pytest

import rendement_jeux as J
from brvm_alpha import rendement
from brvm_alpha.rendement import grille as G
from brvm_alpha.rendement import perte as P
from brvm_alpha.rendement import plan as PL
from brvm_alpha.rendement import reglages as RG
from brvm_alpha.rendement import risque as RQ


@pytest.fixture(scope="module")
def o10():
    return J.ordre("10M")


@pytest.fixture(scope="module")
def choc(o10):
    return P.chocs(o10, P.choc_ref_publie(J.VALIDATION_S1, J.panels_s1_2018()))


@pytest.fixture(scope="module")
def lecteur():
    o = J.ordre("10M")
    return RQ.LecteurPoche(RQ.hebdo(o, J.panels_tr()))


@pytest.fixture(scope="module")
def table(o10, choc, lecteur):
    return P.table_de_choix(o10, choc=choc, lecteur=lecteur)


def _empreintes(dossier):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dossier.glob("*.parquet"))}


def test_choc_ref_publie_mesure_sur_les_fichiers_publies(tmp_path):
    avant = _empreintes(J.VALIDATION_S1)
    c = P.choc_ref_publie(J.VALIDATION_S1, J.panels_s1_2018())
    assert _empreintes(J.VALIDATION_S1) == avant  # aucune écriture
    assert c["source"] == "mesuré" and abs(c["valeur"] - 0.2932) <= 0.0005
    assert c["valeur"] == 0.2932 and abs(c["valeur_mesuree"] - 0.293209) < 5e-7  # arrondi à 4 décimales, comme le cahier
    assert abs(c["vl_2018"] + 0.2574) < 0.0005 and abs(c["part_investie_2018"] - 0.825) < 0.001
    assert abs(c["frais_2018"] - 61_077) < 1
    vide = P.choc_ref_publie(tmp_path, J.panels_s1_2018())
    assert vide["source"] == "repli" and vide["valeur"] == 0.2932 and vide["mention"].startswith("choc de repli")
    assert P.choc_ref_publie(J.VALIDATION_S1, None)["source"] == "repli"


def test_chocs_par_franc_investi(choc):
    assert abs(choc["beta"] - 0.23975) < 1e-5 and abs(choc["en_cours_d_annee"] - 0.31521) < 1e-5
    assert abs(choc["2017_2020"] - 0.44607) < 1e-5 and choc["retenu"] == choc["ref_publie"]
    sans = copy.deepcopy(J.ordre("10M"))
    sans["stress"] = []
    c2 = P.chocs(sans, 0.2932)
    assert c2["beta"] is None and c2["2017_2020"] is None and c2["retenu"] == 0.2932


def test_poche_de_K_egale_l_ordre_de_K(o10):
    pp = P.poche(o10, 10_000_000)
    assert (pp["investi"], pp["frais_achat"], pp["garde"], pp["tenue"], pp["pire_cas"]) == (9_650_560, 160_588, 24_126,
                                                                                             100_000, 9_866_731)
    assert pp["dividendes"] == o10["revenus"]["net"] == 435_988 and pp["lignes"] == 20


@pytest.mark.parametrize("A", [1_400_000, 3_000_000, 6_300_000])
def test_poches_egales_aux_ordres_exacts(o10, A):
    pp = P.poche(o10, A)
    O = J.ordre(str(A))
    c = O["couts"]
    assert {s: q for s, q in pp["quantites"].items() if q > 0} == {l["symbole"]: l["cibles"] for l in O["lignes"] if l["cibles"] > 0}
    assert (pp["investi"], pp["frais_achat"], pp["pire_cas"]) == (c["investi_apres"], c["total"], c["achats_pire_cas"])
    assert (pp["garde"], pp["tenue"], pp["dividendes"]) == (c["garde_annuelle"], c["tenue_compte_annuelle"], O["revenus"]["net"])


@pytest.mark.parametrize("A", [1_500_000, 3_500_000, 7_000_000])
def test_poches_egales_aux_ordres_exacts_resume(o10, A):
    pp = P.poche(o10, A)
    r = J.resume_poches()[str(A)]
    assert {s: q for s, q in pp["quantites"].items() if q > 0} == r["cibles"]
    assert (pp["investi"], pp["frais_achat"], pp["pire_cas"], pp["dividendes"]) == (
        r["investi_apres"], r["total"], r["achats_pire_cas"], r["dividendes_nets"])


RECETTE = [  # X, A*, réserve, investi, frais an1 (achat + annuels), 2018 bas, haut, pire moment, 2017-2020, rapport,
             # dividendes moins frais (an1 ; ensuite), ordinaire (prudente ; flatteuse)
    (500_000, 1_400_000, 8_600_000, 1_204_610, (18_715, 103_012), 410_532, 474_919, 501_430, 659_065, 1.39,
     (-67_825, -49_110), (-10_489, 46_172)),
    (1_000_000, 3_000_000, 7_000_000, 2_807_310, (44_684, 107_018), 824_753, 974_805, 1_036_590, 1_403_953, 1.44,
     (-25_707, 18_977), (118_001, 263_350)),
    (2_000_000, 6_300_000, 3_700_000, 6_009_445, (97_839, 115_024), 1_653_624, 1_974_832, 2_107_091, 2_893_483, 1.47,
     (59_016, 156_855), (374_746, 690_914)),
    (None, 10_000_000, 0, 9_650_560, (160_588, 124_126), 2_598_431, 3_114_258, 3_326_652, 4_589_518, 1.47,
     (151_274, 311_862), (664_187, 1_179_300)),
]


@pytest.mark.parametrize("i", range(4))
def test_recette_table_de_choix(table, i):
    X, A, res, inv, (e, a), bas, haut, pm, lg, rap, (r1, r2), (op, of) = RECETTE[i]
    r = table[i]
    assert r["perte_toleree"] == X and r["en_actions"] == A and r["reserve"] == res and r["investi"] == inv
    assert (r["frais_achat"], r["frais_annuels"], r["frais_an1"]) == (e, a, e + a)
    assert abs(r["annee_2018"][0] - bas) <= 1_000 and abs(r["annee_2018"][1] - haut) <= 1_000
    assert abs(r["pire_moment_2018"] - pm) <= 1_000 and abs(r["baisse_2017_2020"] - lg) <= 1_000
    assert round(r["rapport_2017_2020_sur_2018"], 2) == rap
    assert (r["reste_an1"], r["reste_suivant"]) == (r1, r2)
    assert abs(r["annee_ordinaire"]["prudente"] - op) <= 1_000 and abs(r["annee_ordinaire"]["flatteuse"] - of) <= 1_000
    if X is not None:
        assert r["depasse"] == {"pire_moment": True, "2017_2020": True}
        # Contrôle de la règle : P(A*) ≤ X et P(A* + pas) > X.
        assert r["P"] <= X < r["P_pas_suivant"]
    assert (r["mention"] == "frais > dividendes") == (i == 0)


def test_bornes_haut_du_cahier_au_franc(table):
    # Tables du §F4 calculées avec s_ref = 0,2932 : « haut » et P(A* + pas) au franc près (arrondi de round_fcfa).
    for r, haut in zip(table, (474_919, 974_805, 1_974_832, 3_114_258)):
        assert abs(r["annee_2018"][1] - haut) <= 1, (r["perte_toleree"], r["annee_2018"][1])
    for r, nxt in zip(table, (512_908, 1_010_753, 2_004_461)):
        assert abs(r["P_pas_suivant"] - nxt) <= 1


def test_controles_complementaires(table, o10, choc):
    assert abs(table[0]["P_pas_suivant"] - 512_908) <= 1_000 and abs(table[1]["P_pas_suivant"] - 1_010_753) <= 1_000
    assert abs(table[1]["prix_prudence"] - 546_187) <= 1_000  # lecture prudente seulement
    tout_fl = table[3]["annee_ordinaire"]["flatteuse"] - table[1]["annee_ordinaire"]["flatteuse"]
    assert abs(tout_fl - 915_950) <= 1_000 and abs(table[1]["prix_prudence"] - tout_fl) > 100_000
    assert table[1]["un_titre_en_moins"] == 227_856 and table[3]["un_titre_en_moins"] == 762_348
    assert abs(table[0]["frequence_perte"]["flatteuse"] - 0.416) < 0.001 and abs(table[0]["frequence_perte"]["prudente"] - 0.518) < 0.001
    pp = P.poche(o10, 2_600_000)
    assert (pp["dividendes"], pp["frais_annuels"]) == (108_522, 106_030)
    # Anciennes poches (choc 0,278) évaluées avec le choc mesuré : elles dépassent le montant accepté.
    for A, x in ((1_500_000, 512_908), (3_200_000, 1_041_526), (6_600_000, 2_059_495)):
        p = P.poche(o10, A)
        assert abs(choc["retenu"] * p["investi"] + p["frais_an1"] - x) <= 1_000


@pytest.mark.parametrize("s_ref,attendu", [(0.290, (1_400_000, 3_000_000, 6_400_000)), (0.304, (1_400_000, 2_900_000, 6_100_000)),
                                           (0.278, (1_500_000, 3_200_000, 6_600_000))])
def test_sensibilite_au_choc(o10, choc, s_ref, attendu):
    ch = {**choc, "ref_publie": s_ref, "retenu": max(s_ref, choc["beta"])}
    cache: dict = {}
    got = tuple(P.montant_actions(o10, X, choc=ch, _cache=cache)["A"] for X in (500_000, 1_000_000, 2_000_000))
    assert got == attendu


def test_monotonie_et_independance_du_taux(o10, choc):
    cache: dict = {}
    prec = 0
    for X in range(100_000, 3_000_001, 100_000):
        a = P.montant_actions(o10, X, choc=choc, _cache=cache)["A"]
        assert a >= prec
        prec = a
    for r in (None, 0.0, 0.03, 0.15):
        res = P.reserve(10_000_000, 3_000_000, r)
        assert res["deduit_de_la_perte"] is False
    with pytest.raises(ValueError, match="hors de la plage"):
        P.reserve(10_000_000, 3_000_000, 0.16)


def test_reserve_valeurs_et_statuts():
    r = P.reserve(10_000_000, 3_000_000, 0.03)
    assert (r["montant"], r["valeur_d_un_point"], r["interets"]) == (7_000_000, 70_000, 210_000)
    assert r["mot_statut"] == "supposé" and RG.PH_RESERVE in r["phrases"] and RG.PH_INTERETS in r["phrases"]
    r2 = P.reserve(10_000_000, 0, None)
    assert r2["valeur_d_un_point"] == 100_000 and r2["interets"] == 0 and r2["mention"] == "taux inconnu : compté à 0 %"
    assert RG.PH_INTERETS in r2["phrases"] and RG.PH_RESERVE not in r2["phrases"]
    r3 = P.reserve(10_000_000, 3_000_000, 0.03, "relevé")
    assert RG.PH_RESERVE not in r3["phrases"] and RG.PH_INTERETS in r3["phrases"]
    assert P.reserve(10_000_000, 10_000_000, 0.03)["masque"]


def test_taux_de_reserve_ne_change_ni_A_ni_la_perte():
    o = J.ordre("10M")
    base = None
    for r in (None, 0.0, 0.03, 0.15):
        rn = rendement.construire(o, panels=J.panels_reels(), validation_dir=J.VALIDATION_S1, perte_toleree=1_000_000,
                                  taux_reserve=r, aujourd_hui=J.AUJOURD_HUI, graines=2)
        cle = (rn["perte"]["choix"]["en_actions"], rn["perte"]["choix"]["P"], [x["en_actions"] for x in rn["perte"]["table"]],
               [x.get("P") for x in rn["perte"]["table"]])
        base = base or cle
        assert cle == base
        if r:
            assert rn["reserve"]["interets"] == round(r * 7_000_000)


def test_grille_sans_frais_par_ligne(o10, choc):
    fgi = G.exemples()["sans_frais_par_ligne"]
    cache: dict = {}
    got = [P.montant_actions(o10, X, grille=fgi, choc=choc, _cache=cache)["A"] for X in (500_000, 1_000_000, 2_000_000)]
    assert got == [1_700_000, 3_400_000, 6_600_000]
    pp = cache[3_400_000]
    assert pp["frais_an1"] == 69_611 and pp["dividendes"] - pp["frais_an1"] == 72_345
    assert pp["dividendes"] - pp["frais_annuels"] == 130_064


def test_verification_par_ordre_exact_du_20_11(o10, choc, lecteur):
    appels = []

    def verifier(A):
        appels.append(A)
        return J.ordre(str(int(A)))

    r = P.ligne_choisie(o10, 1_000_000, choc=choc, lecteur=lecteur, verifier=verifier)
    assert appels == [3_000_000] and r["verifie_par_ordre"] and r["appels"] == 1
    assert r["investi"] == 2_807_310 and r["frais_an1"] == 151_702 and r["dividendes"] == 125_995
    assert abs(r["stress_2018_plus_frais"] - 827_267) <= 1 and abs(r["P_verifiee"] - 974_805) <= 1
    assert abs(r["pire_moment_2018"] - 1_039_895) <= 1 and abs(r["baisse_2017_2020"] - 1_408_629) <= 1
    assert r["P_verifiee"] <= 1_000_000 and r["depasse"] == {"pire_moment": True, "2017_2020": True}


def test_verification_arretee_apres_dix_ordres(o10, choc):
    appels = []

    def trop_cher(A):
        appels.append(A)
        O = copy.deepcopy(J.ordre("3000000"))
        O["couts"]["total"] = 5_000_000  # perte estimée toujours au-dessus de X
        return O

    v = P.verifier_par_ordre(3_000_000, 1_000_000, choc, trop_cher)
    assert len(appels) == 10 and v["A"] == 0 and not v["verifie_par_ordre"]
    assert v["message"] == "vérification arrêtée après 10 ordres : montant en actions à confirmer"
    assert "garanti" not in v["message"]


VALEURS_X = [100_000, 700_000, 1_000_000, 1_300_000, 2_000_000, 3_000_000]


@pytest.fixture(scope="module")
def synthese(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("perte")
    Ps = J.panel_synthese()
    return Ps, tmp, J.ordre_synthese(Ps, 5_000_000, tmp, explanations=True)


def test_estimation_2018_sous_le_montant_choisi(synthese):
    Ps, tmp, O = synthese
    d = O.to_dict()
    ch = P.chocs(d, P.choc_ref_publie(tmp / "vide", Ps))
    compteur = {"appels": 0, "construire": 0}
    vrai_construire = rendement.construire

    def verifier(A):
        compteur["appels"] += 1
        # Un appel imbriqué de construire est refusé par la garde contre la récursion.
        imbrique = vrai_construire(d)
        compteur["construire"] += int("erreur" not in imbrique)
        return J.ordre_synthese(Ps, A, tmp, explanations=False)

    verifies = 0
    for X in VALEURS_X:
        avant = compteur["appels"]
        rn = rendement.construire(d, panels=Ps, validation_dir=tmp / "vide", perte_toleree=X, verifier=verifier,
                                  aujourd_hui=J.AUJOURD_HUI, graines=1)
        c = rn["perte"]["choix"]
        assert compteur["appels"] - avant <= 10
        if c["en_actions"] > 0:
            assert c["verifie_par_ordre"] and c["P_verifiee"] <= X
            verifies += 1
        else:
            assert c.get("message")
            assert "garanti" not in c["message"]
    assert verifies >= 3 and compteur["appels"] >= verifies
    assert compteur["construire"] == 0  # la boucle ne rappelle jamais construire
    assert ch["ref_publie_source"] == "repli"

    # Vérificateur plus risqué que la formule : le stress ST2 de chaque ordre complet vaut 60 % de l'investi. Pour
    # chaque X : soit un montant vérifié sous X, soit A* = 0 avec le message d'arrêt — jamais le montant de la formule.
    def risque(A):
        Od = J.ordre_synthese(Ps, A, tmp, explanations=False).to_dict()
        for x in Od.get("stress") or []:
            if x.get("code") == "ST2" and x.get("variante") == "TR":
                x["perte_fcfa"] = -0.60 * float(Od["couts"]["investi_apres"])
        return Od

    arretes = 0
    for X in (700_000, 1_300_000):
        rn = rendement.construire(d, panels=Ps, validation_dir=tmp / "vide", perte_toleree=X, verifier=risque,
                                  aujourd_hui=J.AUJOURD_HUI, graines=1)
        c = rn["perte"]["choix"]
        assert c["appels"] <= 10
        if c["verifie_par_ordre"]:
            assert c["en_actions"] > 0 and c["P_verifiee"] <= X
        else:
            arretes += 1
            assert c["en_actions"] == 0 and rn["reserve"]["montant"] == int(d["capital"])
            assert c["annee_2018"] == [None, None] and c.get("investi") is None and c["message"]
            assert "garanti" not in c["message"]
    assert arretes >= 1


def test_textes_de_la_table_et_vocabulaire(table, o10, choc):
    rn = {"perte": {"table": table, "chocs": choc, "choix": None}, "contexte": {"capital": 10_000_000}}
    plan = PL.construire_plan(rn, aujourd_hui=J.AUJOURD_HUI)
    bloc = [l for l in plan["lignes"] if l["bloc"] == "risque"]
    sous = [l for l in bloc if l["type"] == "sous_ligne"]
    assert len(sous) == 4
    for l, r in zip(sous, table):
        assert "pire moment de 2018 : −" in l["texte"] and "si 2017-2020 revenait : −" in l["texte"]
        dep = r["depasse"]["pire_moment"] or r["depasse"]["2017_2020"]
        assert ("dépasse" in l["texte"]) == dep
    texte = " ".join(l["texte"] + " " + " ".join(l.get("cellules") or []) for l in bloc)
    assert "une fois et demie" not in texte
    sans_fixes = texte
    for ph in RG.PHRASES_FIXES.values():
        sans_fixes = sans_fixes.replace(ph, " ")
    interdits = RG.mots_interdits(sans_fixes, en_plus=RG.INTERDITS_RISQUE)
    assert not set(interdits) & {"plafond", "perte maximale", "au plus", "sous la perte acceptée"}
    assert "flatteuse" not in PL.rendre_plan(plan, "texte") and "flatteuse" not in PL.rendre_plan(plan, "html")


def test_sans_perte_toleree_l_ordre_est_inchange(synthese):
    Ps, tmp, O = synthese
    avant = O.to_dict()
    lignes = O.lignes.copy()
    rn = rendement.construire(O, panels=Ps, validation_dir=tmp / "vide", aujourd_hui=J.AUJOURD_HUI, graines=1)
    assert rn["perte"]["choix"] is None and len(rn["perte"]["table"]) == 4
    assert O.to_dict() == avant and O.lignes.equals(lignes)


def test_aucune_poche_possible(o10, choc):
    m = P.montant_actions(o10, 50_000, choc=choc)
    assert m["A"] == 0 and m["message"].startswith("À ce tarif, le plus petit montant en actions à 20 lignes")
    tout = P.ligne_choisie(o10, 5_000_000, choc=choc)
    assert tout["en_actions"] == 10_000_000 and tout["rappel"] == RG.PH_RISQUE
    assert math.isclose(tout["P"], choc["retenu"] * 9_650_560 + 284_714)


def test_ordre_de_verification_avec_ventes_et_titres_detenus(o10, choc):
    # §F4, cas limite 4 : titres détenus pour plus que A* : l'écart est affiché, aucune vente n'est proposée.
    o = J.ordre("detenu_624840")
    avec_vente = copy.deepcopy(J.ordre("3000000"))
    avec_vente["lignes"][0] = dict(avec_vente["lignes"][0], sens="vente", quantite=5)
    r = P.ligne_choisie(o, 1_000_000, choc=choc, verifier=lambda A: avec_vente)
    assert r["verifie_par_ordre"] and r.get("_ordre") is None  # l'ordre avec ventes n'est pas rendu comme ordre de la poche
    assert r["ventes_refusees"] == [avec_vente["lignes"][0]["symbole"]] and "aucune vente n'est proposée" in r["mention_ventes"]
    assert r["detenu"]["valeur"] == 9_650_560 and r["detenu"]["ecart"] == 9_650_560 - r["en_actions"]
    assert r["detenu"]["texte"].startswith("Titres déjà détenus pour 9\u202f650\u202f560 FCFA")
    memo: dict = {}
    rn = rendement.construire(o, panels=J.panels_reels(), validation_dir=J.VALIDATION_S1, perte_toleree=1_000_000,
                              verifier=lambda A: avec_vente, memo=memo, aujourd_hui=J.AUJOURD_HUI, graines=1)
    assert "ordre_poche" not in memo
    t = " ".join(PL.rendre_plan(rn["plan"], "texte").split()).replace("\u202f", " ").replace("\u00a0", " ")
    assert "Titres déjà détenus pour 9 650 560 FCFA" in t and "aucune vente n'est proposée" in t

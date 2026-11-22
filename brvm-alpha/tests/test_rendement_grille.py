"""F2 — La grille du courtier (cahier ``docs/RENDEMENT_NET.md``, §F2). Le dossier de profil est toujours un dossier
temporaire : aucun test ne lit ``<données>/profil/``. Recette sur l'ordre figé du 20/11/2026 (10 M)."""

from __future__ import annotations

import warnings

import numpy as np
import pytest

import rendement_jeux as J
from brvm_alpha import settings
from brvm_alpha.portfolio import recommend as R
from brvm_alpha.rendement import grille as G

CENTRAL = settings.cost_scenario("central")


def test_ecriture_relecture_memes_valeurs_et_statuts(tmp_path):
    g = G.defaut().avec(courtage=0.0075, tenue_par_ligne=0, forfait_compte=4000)
    g.nom = "Ma grille"
    g.champs["courtage"].statut, g.champs["courtage"].source, g.champs["courtage"].date = G.ECRITE, "grille 2026", "2026-11-23"
    p = G.enregistrer(g, tmp_path)
    assert p == tmp_path / "grille_sgi.yaml"
    h = G.charger(tmp_path)
    assert h.to_dict() == g.to_dict()
    assert h.champs["courtage"].statut == G.ECRITE and h.champs["garde"].statut == G.SUPPOSE


def test_fichier_absent_ou_illisible(tmp_path):
    assert G.charger(tmp_path).to_dict() == G.defaut().to_dict()
    (tmp_path / "grille_sgi.yaml").write_text("champs: [", encoding="utf-8")
    with pytest.raises(ValueError, match="grille_sgi.yaml"):
        G.charger(tmp_path)


def test_valeur_refusee_et_valeur_avertie(tmp_path):
    with pytest.raises(ValueError, match="courtage : 4 % est hors de la plage acceptée \\(0 à 3 %\\)"):
        G.enregistrer(G.defaut().avec(courtage=0.04), tmp_path)
    assert not (tmp_path / "grille_sgi.yaml").exists()
    with pytest.warns(G.GrilleHorsFourchette, match="courtage : 0,3 %"):
        G.enregistrer(G.defaut().avec(courtage=0.003), tmp_path)
    assert G.charger(tmp_path).valeur("courtage") == 0.003


def test_grille_par_defaut_identique_au_tarif_central():
    cm, forfait = G.vers_cost_model(G.defaut(), CENTRAL)
    assert forfait == 0.0
    for champ in ("sgi_commission", "vat_on_commission", "min_ticket_fcfa", "annual_custody", "account_fee_per_line_fcfa",
                  "brvm_fee", "dcbr_fee", "impact_coef", "half_spread_mult"):
        assert getattr(cm, champ) == getattr(CENTRAL, champ), champ
    o = J.ordre("10M")
    r = G.comparer(o, {"defaut": G.defaut()})[0]
    assert (r["frais_achat"], r["frais_annuels"], r["premiere_annee"]) == (160_588, 124_126, 284_714)
    assert r["ecart_premiere_annee"] == 0 and r["provision_pire_cas"] == 9_866_731


@pytest.mark.parametrize("minimum", [0.0, 1000.0, 2500.0])
def test_egalite_au_franc_avec_fee_breakdown(minimum):
    rng = np.random.default_rng(11)
    for _ in range(200):
        g = G.defaut().avec(courtage=float(rng.uniform(0, 0.03)), taxe_courtage=float(rng.uniform(0, 0.25)),
                            courtage_min_par_ordre=minimum)
        cm, _f = G.vers_cost_model(g, CENTRAL)
        a = float(rng.uniform(1, 5_000_000))
        assert G.frais_explicites(a, g)["explicites"] == R.fee_breakdown(a, cm)["explicites"]


def test_recette_des_quatre_grilles_et_des_inconnues():
    o = J.ordre("10M")
    res = {r["cle"]: r for r in G.comparer(o, G.exemples())}
    assert (res["central"]["premiere_annee"], res["central"]["frais_annuels"]) == (284_714, 124_126)
    assert (res["sans_frais_par_ligne"]["premiere_annee"], res["sans_frais_par_ligne"]["frais_annuels"]) == (211_490, 28_126)
    assert (res["sans_frais_par_ligne"]["ecart_premiere_annee"], res["sans_frais_par_ligne"]["ecart_annuel"]) == (-73_224, -96_000)
    assert (res["bas_de_fourchette"]["premiere_annee"], res["bas_de_fourchette"]["frais_annuels"]) == (224_692, 109_651)
    assert (res["bas_de_fourchette"]["ecart_premiere_annee"], res["bas_de_fourchette"]["ecart_annuel"]) == (-60_022, -14_475)
    assert (res["borne_non_attestee"]["premiere_annee"], res["borne_non_attestee"]["ecart_premiere_annee"]) == (154_556, -130_158)
    d = G.defaut()
    cas = {"m2500": d.avec(courtage_min_par_ordre=2500), "m1000": d.avec(courtage_min_par_ordre=1000),
           "t10": d.avec(taxe_courtage=0.10), "ta18": d.avec(taxe_frais_annuels=0.18)}
    r = {x["cle"]: x for x in G.comparer(o, cas)}
    assert r["m2500"]["ecart_achat"] == 13_841 and r["m1000"]["ecart_achat"] == 172
    assert r["t10"]["ecart_achat"] == -6_175 and r["ta18"]["ecart_annuel"] == 22_343
    assert r["m2500"]["sens_ecart"] == "surcoût"
    r1 = G.comparer(J.ordre("1M"), {"m": d.avec(courtage_min_par_ordre=2500)})[0]
    assert r1["ecart_achat"] == 50_822


def test_statut_global():
    g = G.defaut()
    assert G.statut_global(g) == G.SUPPOSE and G.statut_global(None) == G.SUPPOSE
    for k in G.PRINCIPAUX:
        g.champs[k].statut = G.AVIS
    assert G.statut_global(g) == G.AVIS
    g.champs["garde"].statut = G.ECRITE
    assert G.statut_global(g) == G.ECRITE
    g.champs["forfait_compte"].statut = G.SUPPOSE
    assert G.statut_global(g) == G.SUPPOSE


def test_forfait_rendu_a_part_et_frais_hors_modele():
    g = G.defaut().avec(forfait_compte=4000, taxe_frais_annuels=0.18, garde_minimum=30_000, encaissement_taux=0.01,
                        encaissement_fixe=500)
    cm, forfait = G.vers_cost_model(g, CENTRAL)
    assert forfait == 4000.0
    o = J.ordre("10M")
    hm = G.frais_hors_modele(g, o["couts"], o["revenus"], o["dividendes"])
    # taxe = 18 % × (24 126 + 100 000 + 4 000) ; complément de garde = 30 000 − 24 126 ;
    # encaissement = 1 % × 435 988 + 500 × 20 paiements.
    assert hm["taxe_annuelle"] == R.round_fcfa(0.18 * 128_126) == 23_063
    assert hm["garde_complement"] == 5_874 and hm["encaissement"] == 4_360 + 10_000


def test_personne_morale_avertie_et_questions():
    g = G.defaut()
    g.investisseur = "personne morale"
    assert any("personne morale" in a for a in G.controler(g)["avertissements"])
    q = G.questions()
    assert len(q) == 8 and q[0].startswith("1. Quel est mon taux de courtage") and "plus-values" in q[7]


def test_profil_jamais_lu_par_defaut_dans_les_tests(tmp_path, monkeypatch):
    # Le dossier de profil est un paramètre : la grille d'un dossier vide est la grille par défaut.
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert G.charger(tmp_path / "profil").nom == G.defaut().nom


def test_option_grille_resolue(tmp_path):
    assert G.resoudre(None) is None and G.resoudre("central") is None
    assert G.resoudre("ma_sgi", tmp_path) is None and not G.enregistree(tmp_path)
    g = G.defaut().avec(courtage=0.006)
    G.enregistrer(g, tmp_path)
    assert G.enregistree(tmp_path) and G.resoudre("ma_sgi", tmp_path).valeur("courtage") == 0.006
    assert G.resoudre(str(tmp_path / "grille_sgi.yaml")).valeur("courtage") == 0.006
    assert G.resoudre(g) is g
    with pytest.raises(ValueError, match="illisible"):
        G.resoudre(str(tmp_path / "absent.yaml"))

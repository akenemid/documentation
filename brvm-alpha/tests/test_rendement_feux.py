"""F11 — Trois feux, vie d'une alerte, prix des décisions (cahier ``docs/RENDEMENT_NET.md``, §F11), logique du paquet
``rendement`` (le journal du suivi lui fournit ses semaines). Seuils lus dans les réglages ; aucune fonction ne
produit d'ordre."""

from __future__ import annotations

import copy

import pytest

import rendement_jeux as J
from brvm_alpha.config import CostModel
from brvm_alpha.portfolio import recommend as R
from brvm_alpha.rendement import alertes as AL
from brvm_alpha.rendement import reglages as RG


def _semaine(**kw):
    s = {"date": "2027-03-12", "valeur": 3_000_000, "argent_engage": 3_000_000, "papier": True, "bulletins_manquants": 0,
         "retard_journal_jours": 2, "argent_qui_dort": 150_000, "argent_qui_dort_prevu": 150_000, "liquidites": 200_000,
         "prochain_prelevement": 30_000}
    s.update(kw)
    return s


@pytest.mark.parametrize("perte,etat", [(499_000, "vert"), (500_000, "orange"), (999_999, "orange"), (1_000_000, "rouge"),
                                        (1_600_000, "rouge")])
def test_seuils_exacts_du_feu_perte(perte, etat):
    s = _semaine(valeur=3_000_000 - perte)
    f = AL.feux(s, {"perte_toleree": 1_000_000})
    assert f["perte"]["etat"] == etat
    assert f["perte"]["perte_en_cours"] == perte
    if etat != "vert":
        assert "Une année comme 2018 dépasse ce montant en cours d'année." in f["perte"]["phrase"]
    assert f["perte"]["palier"] == (0 if perte < 500_000 else 1 if perte < 1_000_000 else 2 if perte < 1_500_000 else 3)
    assert ("Ce que vous acceptez de risquer est-il toujours le bon montant ?" in f["perte"]["questions"]) == (etat == "rouge")


def test_feu_perte_sans_choix_et_sans_remise_a_zero():
    s = _semaine(valeur=2_699_000, argent_engage=3_000_000, argent_engage_actions=3_000_000)
    assert AL.feux(s)["perte"]["etat"] == "orange"  # 301 000 ≥ 10 % de 3 000 000
    assert AL.feux(_semaine(valeur=2_390_000))["perte"]["etat"] == "rouge"
    assert AL.feux(_semaine(valeur=2_710_000))["perte"]["etat"] == "vert"


def test_feu_fuites_papier_et_regle_declaree():
    f = AL.feux(_semaine())
    assert f["fuites"]["etat"] == "vert"
    assert any("sans objet (papier)" in c for c in f["fuites"]["conditions"])  # (a) n'est pas « verte »
    # Portefeuille qui suit la règle testée : dividendes reçus de mai à septembre, attendus par la règle → vert.
    for mois in ("2027-05-31", "2027-07-30", "2027-09-30"):
        s = _semaine(date=mois, argent_qui_dort=480_000, argent_qui_dort_prevu=480_000, seances_argent_qui_dort_au_dela=0)
        assert AL.feux(s)["fuites"]["etat"] == "vert"
    s = _semaine(argent_qui_dort=400_000, argent_qui_dort_prevu=150_000, seances_argent_qui_dort_au_dela=21)
    assert AL.feux(s)["fuites"]["etat"] == "orange"
    s = _semaine(argent_qui_dort=400_000, argent_qui_dort_prevu=150_000, seances_argent_qui_dort_au_dela=20)
    assert AL.feux(s)["fuites"]["etat"] == "vert"
    assert AL.feux(_semaine(ordres_expires=1))["fuites"]["etat"] == "orange"
    assert AL.feux(_semaine(dividendes_non_credites=["SNTS"]))["fuites"]["etat"] == "orange"
    assert AL.feux(_semaine(liquidites=10_000, prochain_prelevement=30_000))["fuites"]["etat"] == "rouge"
    assert AL.feux(_semaine(w1_critique=True))["fuites"]["etat"] == "rouge"
    reel = _semaine(papier=False, avis=[{"frais_lus": 23_000, "frais_prevus": 21_000}])
    assert AL.feux(reel)["fuites"]["etat"] == "orange"
    reel = _semaine(papier=False, avis=[{"frais_lus": 21_900, "frais_prevus": 21_000}])
    assert AL.feux(reel)["fuites"]["etat"] == "vert"


def test_feu_donnees():
    assert AL.feux(_semaine(bulletins_manquants=1))["donnees"]["etat"] == "orange"
    assert AL.feux(_semaine(bulletins_manquants=3))["donnees"]["etat"] == "rouge"
    assert "aucun ordre de vente ne doit partir" in AL.feux(_semaine(bulletins_manquants=3))["donnees"]["phrase"]
    assert AL.feux(_semaine(retard_journal_jours=10))["donnees"]["etat"] == "orange"
    assert AL.feux(_semaine(retard_journal_jours=9))["donnees"]["etat"] == "vert"
    assert AL.feux(_semaine(passe_a_change=True))["donnees"]["etat"] == "rouge"
    assert AL.feux(_semaine(), declaration={"chaine_ok": False})["donnees"]["etat"] == "rouge"
    assert AL.feux(_semaine(ordre_contredit_decision=True))["donnees"]["etat"] == "rouge"


def test_sans_journal_et_textes_fixes():
    f = AL.feux(None)
    assert not f["suivi_commence"] and f["perte"]["etat"] == "—" and f["perte"]["phrase"] == "le suivi n'a pas commencé"
    assert f["phrase"] == RG.PH_REVUE and f["avertissement"].startswith("Seuils choisis après lecture de la période 2022-2026")


def test_vie_d_une_alerte_palier_et_rearmement():
    al: list = []
    a = AL.ouvrir(al, "perte", 1, "2027-03-12", feu="perte")
    assert a["etat"] == "ouverte" and AL.ouvrir(al, "perte", 1, "2027-03-13", feu="perte") is a
    AL.marquer_revue(a, "2027-03-12", "garder", ["le marché"])
    s = _semaine(valeur=2_400_000)
    f = AL.feux(s, {"perte_toleree": 1_000_000}, alertes_ouvertes=al)
    assert f["perte"]["affichage"] == "ORANGE — revue faite le 12/03"
    assert AL.ouvrir(al, "perte", 1, "2027-03-20", feu="perte") is None  # ne se rouvre pas au même palier
    AL.clore(a, "2027-03-20")
    assert AL.ouvrir(al, "perte", 1, "2027-04-01", feu="perte") is None
    b = AL.ouvrir(al, "perte", 2, "2027-04-02", feu="perte", niveau="rouge")
    assert b is not None and b is not a and b["palier"] == 2
    f = AL.feux(_semaine(date="2027-04-20", valeur=1_900_000), {"perte_toleree": 1_000_000}, alertes_ouvertes=al)
    assert f["perte"]["etat"] == "rouge" and f["perte"]["rappel"].startswith("Rappel : alerte rouge sans revue")
    with pytest.raises(ValueError):
        AL.marquer_revue(b, "2027-04-21", "vendre tout")


def test_lignes_a_revoir_et_detachement():
    etat = {"valeur": 3_000_000, "lignes": [
        {"symbole": "AAA", "baisse_depuis_achat": 0.36, "perte_ligne": 50_000, "frais_annuels": 5_000, "dividende_attendu": 9_000},
        {"symbole": "BBB", "baisse_depuis_achat": 0.0, "perte_ligne": 0, "frais_annuels": 5_400, "dividende_attendu": 4_800},
        {"symbole": "CCC", "baisse_depuis_achat": 0.04, "perte_ligne": 120_000, "frais_annuels": 1_000, "dividende_attendu": 9_000},
        {"symbole": "DDD", "baisse_depuis_achat": 0.0, "perte_ligne": 0, "ecart_marche_63": -0.26},
    ]}
    rv = {x["symbole"]: x for x in AL.lignes_a_revoir(etat, {"perte_toleree": 1_000_000})}
    assert rv["AAA"]["palier_baisse"] == 2 and not rv["AAA"]["a_vendre"]
    assert any(m.startswith("L4") for m in rv["BBB"]["motifs"]) and any(m.startswith("L2") for m in rv["CCC"]["motifs"])
    assert any(m.startswith("L3") for m in rv["DDD"]["motifs"])
    # Un jour de détachement : cours dividendes compris, aucune baisse « depuis l'achat » → L1 ne s'ouvre pas.
    det = {"valeur": 3_000_000, "lignes": [{"symbole": "SNTS", "baisse_depuis_achat": 0.0, "perte_ligne": 0}]}
    assert AL.lignes_a_revoir(det) == []


def test_prix_des_decisions_aller_retour_egal_deux_fois_l_achat():
    etat = {"lignes": [{"symbole": "SNTS", "titres": 629, "cours": 4040.0, "prix_de_revient": 4100.0, "dividende_attendu": 150_000,
                        "demi_spread_pct": 0.00106, "mdv63": 852_282_472.5}]}
    cm = CostModel()
    p = AL.prix_des_decisions(etat, "SNTS", cm)
    achat = R.order_costs(629, 4040.0, cm, side="achat", half_spread=0.00106, mdv63=852_282_472.5)["total"]
    assert p["reduire_ou_vendre"]["aller_retour"] == 2 * achat == 2 * p["reduire_ou_vendre"]["frais_achat_equivalent"]
    assert p["garder"]["frais"] == 0 and p["ne_plus_acheter"]["frais"] == 0
    assert p["reduire_ou_vendre"]["resultat_realise"] == round(629 * (4040 - 4100))
    assert p["phrase"] == RG.PH_REVUE


def test_aucun_feu_ne_cree_d_ordre():
    o = J.ordre("10M")
    avant = copy.deepcopy(o)
    al: list = []
    AL.ouvrir(al, "perte", 2, "2027-04-02", feu="perte", niveau="rouge")
    AL.feux(_semaine(valeur=1_000_000), {"perte_toleree": 1_000_000}, alertes_ouvertes=al)
    AL.lignes_a_revoir({"valeur": 1, "lignes": []})
    assert o == avant
    assert all(not hasattr(AL, nom) for nom in ("vendre", "ordre_de_vente", "stop"))

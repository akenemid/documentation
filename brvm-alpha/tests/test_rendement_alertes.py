"""F8 — Avertissements de fuite dans l'ordre (cahier ``docs/RENDEMENT_NET.md``, §F8). Recette sur les ordres figés
du 20/11/2026 ; W7 sur des tables de séances de synthèse. Aucune alerte ne crée d'ordre."""

from __future__ import annotations

import copy

import pandas as pd

import rendement_jeux as J
from brvm_alpha.rendement import alertes as AL
from brvm_alpha.rendement import grille as G
from brvm_alpha.rendement import reglages as RG


def _codes(al):
    return {(a["code"], a["niveau"]) for a in al}


def _un(al, code):
    return next(a for a in al if a["code"] == code)


def test_trois_niveaux_de_W1():
    a1 = AL.alertes_fuite(J.ordre("1M"))
    w1 = _un(a1, "W1")
    assert w1["niveau"] == "critique" and abs(w1["valeurs"]["ratio"] - 2.657) < 0.001 and w1["prefixe"] == "FUITE"
    assert w1["texte"] == ("Les frais annuels (102\u202f166 FCFA) dépassent les dividendes nets attendus (38\u202f458 FCFA). À "
                           "cours inchangés, ce portefeuille perd 63\u202f708 FCFA par an.")
    a10 = AL.alertes_fuite(J.ordre("10M"))
    w = _un(a10, "W1")
    assert w["niveau"] == "orange" and abs(w["valeurs"]["ratio"] - 0.285) < 0.001
    assert w["texte"] == ("Les frais annuels du courtier (124\u202f126 FCFA) prennent 28 % des dividendes nets attendus "
                          "(435\u202f988 FCFA) [supposé].")
    assert not any(a["code"] == "W1" for a in AL.alertes_fuite(J.ordre("50M")))
    fgi = G.exemples()["sans_frais_par_ligne"]
    assert not any(a["code"] == "W1" for a in AL.alertes_fuite(J.ordre("10M"), grille=fgi))


def test_seuils_lus_dans_les_reglages():
    r = RG.charger()
    r["frais"]["seuils_frais_annuels_sur_dividendes"] = [0.30, 0.5, 1.0]
    assert not any(a["code"] == "W1" for a in AL.alertes_fuite(J.ordre("10M"), reglages=r))


def test_W2_et_W3():
    a = AL.alertes_fuite(J.ordre("10M"))
    w2 = _un(a, "W2")
    assert w2["niveau"] == "information" and w2["prefixe"] is None
    assert "90 % des frais de la 1re année sont supposés ou estimés (255\u202f762 sur 284\u202f714 FCFA)" in w2["texte"]
    assert _un(a, "W3")["valeurs"]["lignes"] == ["NTLC"]
    assert len(_un(AL.alertes_fuite(J.ordre("1M")), "W3")["valeurs"]["lignes"]) == 18


def test_W4_information_quand_la_regle_testee_garde_l_argent():
    a = AL.alertes_fuite(J.ordre("detenu_624840"), panels={"dividends_table": J.dividendes_2026()})
    w4 = _un(a, "W4")
    assert w4["niveau"] == "information" and w4["prefixe"] is None and "FUITE" not in w4["texte"]
    assert "prévu par la règle testée" in w4["texte"] and "dividendes gardés" in w4["cause"]


def test_W4_fuite_apres_service_partiel():
    orig = {l["symbole"]: l["cibles"] for l in J.ordre("10M")["lignes"] if l["cibles"] > 0}
    a = AL.alertes_fuite(J.ordre("partiel"), memoire={"quantites_origine": orig})
    w4 = _un(a, "W4")
    assert w4["niveau"] == "orange" and w4["prefixe"] == "FUITE" and w4["cause"] == "ordres non servis"
    assert w4["valeurs"]["D_hors_regle"] == 476_412  # 469 430 d'ordres non servis + 6 982 de cause inconnue


def test_W5_et_W6():
    w5 = _un(AL.alertes_fuite(J.ordre("50M")), "W5")
    assert w5["prefixe"] == "À VÉRIFIER" and "11\u202f697 FCFA" in w5["texte"] and "0,2 point" in w5["texte"]
    assert not any(a["code"] == "W5" for a in AL.alertes_fuite(J.ordre("10M")))
    g = G.defaut().avec(courtage_min_par_ordre=2500)
    w6 = _un(AL.alertes_fuite(J.ordre("10M"), grille=g), "W6")
    assert w6["prefixe"] == "FUITE" and w6["valeurs"]["surcout"] == 13_841
    assert not any(a["code"] == "W6" for a in AL.alertes_fuite(J.ordre("10M")))


def _ordre_vente_ineligible():
    o = copy.deepcopy(J.ordre("detenu_624840"))
    l = next(x for x in o["lignes"] if x["symbole"] == "NTLC")
    l.update({"sens": "vente", "quantite": 13, "cibles": 0, "note": "sortie forcée : inéligible (U2)", "tranches": [13],
              "prix_limite": l["limite_vente"]})
    return o


def _seances(n=300, trou=None):
    d = pd.bdate_range(end="2026-11-20", periods=n)
    s = pd.DataFrame({"date": d, "available": True})
    if trou is not None:
        s.loc[s.index[trou:trou + 3], "available"] = False
    return s


def test_W7_lit_la_table_des_seances():
    o = _ordre_vente_ineligible()
    assert AL.ventes_ineligibles(o) == ["NTLC"]
    rouge = _un(AL.alertes_fuite(o, sessions=_seances(trou=250)), "W7")
    assert rouge["niveau"] == "rouge" and rouge["prefixe"] == "À VÉRIFIER" and rouge["valeurs"]["n"] == 3
    assert rouge["texte"].startswith("Ne vendez pas à cause d'un trou de données : 3 bulletins manquent entre le ")
    assert not any(a["code"] == "W7" for a in AL.alertes_fuite(o, sessions=_seances(trou=50)))  # 200 séances avant
    # Panel à jour sans trou mais en retard : W7 muet (le retard est déjà signalé « ORDRES PÉRIMÉS »).
    o2 = copy.deepcopy(o)
    o2["execution"]["perime"], o2["execution"]["seances_manquantes"] = True, ["2026-11-23", "2026-11-24", "2026-11-25"]
    assert not any(a["code"] == "W7" for a in AL.alertes_fuite(o2, sessions=_seances()))
    sans = _un(AL.alertes_fuite(o), "W7")
    assert "bulletins manquants non vérifiables" in sans["texte"]


def test_W8_W9():
    o = J.ordre("detenu_624840")
    a = AL.alertes_fuite(o, cash_fourni=False)
    assert ("W8", "information") in _codes(a) and ("W9", "orange") in _codes(a)
    assert _un(a, "W9")["prefixe"] == "À VÉRIFIER"
    assert not any(x["code"] == "W9" for x in AL.alertes_fuite(o, cash_fourni=True))
    assert not any(x["code"] == "W8" for x in AL.alertes_fuite(o, memoire={"annee": 2026, "date": "2026-01-30"}))
    assert not any(x["code"] in ("W8", "W9") for x in AL.alertes_fuite(J.ordre("10M"), cash_fourni=False))


def test_placement_trois_au_plus_par_priorite():
    o = _ordre_vente_ineligible()
    al = AL.alertes_fuite(o, sessions=_seances(trou=250), cash_fourni=False, grille=G.defaut().avec(courtage_min_par_ordre=2500))
    al += AL.alertes_fuite(J.ordre("1M"))
    av = AL.avertissements(al)
    assert len(av) == 3
    assert av[0].startswith("À VÉRIFIER : Ne vendez pas") and av[1].startswith("À VÉRIFIER : Liquidités prises égales")
    assert av[2].startswith("FUITE : Les frais annuels (102")
    assert not any("Tarif non vérifié" in x or "Hors remise à niveau" in x for x in av)  # informations jamais placées
    existants = ["PANEL EN RETARD de 1 séance(s) : …", "autre avertissement"]
    assert (existants + av)[0].startswith("PANEL EN RETARD")
    assert AL.avertissements(AL.alertes_fuite(J.ordre("10M"))) == [
        "FUITE : Les frais annuels du courtier (124\u202f126 FCFA) prennent 28 % des dividendes nets attendus "
        "(435\u202f988 FCFA) [supposé]."]


def test_aucune_alerte_ne_modifie_l_ordre():
    o = J.ordre("partiel")
    avant = copy.deepcopy(o)
    AL.alertes_fuite(o, cash_fourni=False, sessions=_seances(trou=250))
    assert o == avant


def test_textes_sans_mot_interdit_de_l_ecran():
    for cap in ("1M", "10M", "50M"):
        for a in AL.alertes_fuite(J.ordre(cap)):
            interdits = set(RG.mots_interdits(a["texte"])) - {"au plus"}
            assert not interdits, (a["code"], interdits)


def test_W7_un_seul_bulletin_manquant_accord_au_singulier():
    o = _ordre_vente_ineligible()
    s = _seances()
    s.loc[s.index[-20], "available"] = False
    w = _un(AL.alertes_fuite(o, sessions=s), "W7")
    jour = pd.Timestamp(s.iloc[-20]["date"])
    assert w["valeurs"]["n"] == 1 and w["niveau"] == "rouge"
    assert w["texte"].startswith(f"Ne vendez pas à cause d'un trou de données : 1 bulletin manque le {jour:%d/%m}. ")
    assert "1 bulletins" not in w["texte"] and "manquent" not in w["texte"]


def test_W4_fuite_pour_l_argent_d_origine_inconnue():
    o = copy.deepcopy(J.ordre("detenu_624840"))
    for k in ("liquidites_initiales", "valeur_portefeuille"):
        o[k] += 300_000
    o["couts"]["liquidites_apres"] += 300_000
    w = _un(AL.alertes_fuite(o, panels={"dividends_table": J.dividendes_2026()}), "W4")
    assert w["niveau"] == "orange" and w["prefixe"] == "FUITE" and w["cause"] == "inconnue"
    assert w["valeurs"]["D"] == 713_332 and w["valeurs"]["D_hors_regle"] >= 100_000

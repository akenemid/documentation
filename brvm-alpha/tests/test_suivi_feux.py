"""F11 — Trois feux lus sur le journal du suivi (cahier ``docs/RENDEMENT_NET.md``, §F11). La logique des feux est
testée dans ``tests/test_rendement_feux.py`` ; ici, le journal la nourrit. Aucun feu ne crée d'ordre ni de vente.
"""

from __future__ import annotations

import pandas as pd
import pytest

import suivi_jeux as J
from brvm_alpha.rendement import alertes as AL
from brvm_alpha.suivi import bulletin as BU
from brvm_alpha.suivi import carnet as CN
from brvm_alpha.suivi import etat as ET

JOURS = pd.bdate_range("2027-04-26", "2027-10-01")


def _portefeuille(tmp_path, prix=None, dividendes=None):
    prix = prix or {"AAA": [100.0] * len(JOURS)}
    p = J.panel_simple(JOURS, prix, dividendes=dividendes)
    c = CN.ouvrir("PLAN", tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[0], "montant": 1_000_000})
    o = c.ajouter({"type": "ordre", "date": JOURS[0], "symbole": "AAA", "sens": "achat", "titres": 9000, "limite": 101,
                   "cours_reference": 100, "motif": "remise_a_niveau"})
    c.ajouter({"type": "execution", "date": JOURS[1], "symbole": "AAA", "sens": "achat", "titres": 9000, "prix": 100,
               "frais": {"courtage": 7200}, "ordre": o["n"], "source": "papier"})
    return c, p


def test_regle_testee_dividendes_de_mai_a_septembre_feu_fuites_vert(tmp_path):
    jours_div = [JOURS[20], JOURS[45], JOURS[70], JOURS[100]]
    c, p = _portefeuille(tmp_path)
    for i, d in enumerate(jours_div):
        c.ajouter({"type": "dividende", "date": d, "symbole": "AAA", "titres": 9000, "net_par_titre": 5 + i,
                   "montant": 9000 * (5 + i)})
    ls = BU.lignes_semaines(c.operations(), p, debut=JOURS[0])
    BU.ecrire_semaines("PLAN", ls, tmp_path)
    assert ls[-1]["argent_qui_dort"] > 100_000  # les dividendes attendent la remise à niveau de janvier
    b = BU.depuis_journal("PLAN", tmp_path, aujourd_hui=JOURS[-1])
    assert b["feux"]["fuites"]["etat"] == "vert"
    assert any("sans objet (papier)" in x for x in b["feux"]["fuites"]["conditions"])
    assert b["feux"]["donnees"]["etat"] == "vert" and b["feux"]["perte"]["etat"] == "vert"


def test_argent_qui_dort_hors_regle_plus_de_20_seances_feu_orange(tmp_path):
    c, p = _portefeuille(tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[2], "montant": 400_000})
    ls = BU.lignes_semaines(c.operations(), p, debut=JOURS[0], prevu=lambda t, l: l["argent_qui_dort"] - 250_000)
    s = BU.semaine_pour_feux(ls[:4])
    assert s["seances_argent_qui_dort_au_dela"] == 20 and AL.feux(s)["fuites"]["etat"] == "vert"
    s = BU.semaine_pour_feux(ls[:6])
    assert s["seances_argent_qui_dort_au_dela"] > 20 and AL.feux(s)["fuites"]["etat"] == "orange"


def test_feu_perte_depuis_l_argent_engage_sans_remise_a_zero(tmp_path):
    prix = {"AAA": [100.0] * 30 + [94.0] * 40 + [88.0] * (len(JOURS) - 70)}
    c, p = _portefeuille(tmp_path, prix)
    ls = BU.lignes_semaines(c.operations(), p, debut=JOURS[0])
    plan = {"perte_toleree": 100_000}
    etats = [AL.feux(BU.semaine_pour_feux(ls[: i + 1]), plan)["perte"]["etat"] for i in range(len(ls))]
    assert etats[3] == "vert" and "orange" in etats and etats[-1] == "rouge"
    # sans montant choisi : 10 % puis 20 % de l'argent en actions
    assert AL.feux(BU.semaine_pour_feux(ls))["perte"]["etat"] == "orange"


def test_feu_donnees_retard_bulletins_chaine(tmp_path):
    c, p = _portefeuille(tmp_path)
    ls = BU.lignes_semaines(c.operations(), p, debut=JOURS[0])
    BU.ecrire_semaines("PLAN", ls[:3], tmp_path)
    vend = pd.Timestamp(ls[2]["vendredi"])
    assert BU.depuis_journal("PLAN", tmp_path, aujourd_hui=vend + pd.Timedelta(days=9))["feux"]["donnees"]["etat"] == "vert"
    assert BU.depuis_journal("PLAN", tmp_path, aujourd_hui=vend + pd.Timedelta(days=10))["feux"]["donnees"]["etat"] == \
        "orange"
    s = BU.semaine_pour_feux([dict(ls[2], bulletins_manquants=3)], aujourd_hui=vend)
    f = AL.feux(s)["donnees"]
    assert f["etat"] == "rouge" and "aucun ordre de vente ne doit partir" in f["phrase"]
    assert AL.feux(BU.semaine_pour_feux(ls[:3], chaine_ok=False, aujourd_hui=vend))["donnees"]["etat"] == "rouge"
    assert AL.feux(BU.semaine_pour_feux(ls[:3], aujourd_hui=vend), declaration={"chaine_ok": False})["donnees"]["etat"] == \
        "rouge"


def test_aucun_feu_ne_cree_d_ordre(tmp_path):
    c, p = _portefeuille(tmp_path, {"AAA": [100.0] * 30 + [60.0] * (len(JOURS) - 30)})
    avant = c.fichier.read_bytes()
    ls = BU.lignes_semaines(c.operations(), p, debut=JOURS[0])
    BU.ecrire_semaines("PLAN", ls, tmp_path)
    b = BU.depuis_journal("PLAN", tmp_path, plan={"perte_toleree": 50_000}, aujourd_hui=JOURS[-1])
    assert b["feux"]["perte"]["etat"] == "rouge"
    assert c.fichier.read_bytes() == avant  # aucun mouvement ajouté au carnet
    assert "ordre" not in b["feux"] and "Un feu ouvre une revue, jamais une vente." in BU.rendre(b)


def test_lignes_a_revoir_et_prix_des_decisions_depuis_l_etat(tmp_path):
    ex = JOURS[40]
    prix = {"AAA": [100.0] * 30 + [74.0] * 10 + [70.0] * (len(JOURS) - 40)}  # détachement de 4 FCFA le jour ex
    div = [{"symbol": "AAA", "ex_date": ex, "amount": 4.0, "payment_date": JOURS[45], "date": JOURS[0]}]
    c, p = _portefeuille(tmp_path, prix, div)
    det = pd.DataFrame([{"symbole": "AAA", "date_detachement": ex, "date_paiement": JOURS[45], "montant": 36_000.0}])
    e0 = ET.etat(c, p, JOURS[39], detaches=det)
    e1 = ET.etat(c, p, ex, detaches=det)
    l0, l1 = e0["lignes"][0], e1["lignes"][0]
    assert l1["baisse_depuis_achat"] == pytest.approx(l0["baisse_depuis_achat"])  # un détachement n'allume rien
    rv = AL.lignes_a_revoir(e1, {"perte_toleree": 1_000_000})
    assert rv and rv[0]["symbole"] == "AAA" and rv[0]["motifs"][0].startswith("L1") and rv[0]["a_vendre"] is False
    prix_d = AL.prix_des_decisions(e1, "AAA")
    r = prix_d["reduire_ou_vendre"]
    assert prix_d["garder"]["frais"] == 0 and r["aller_retour"] == 2 * r["frais_achat_equivalent"] > 0

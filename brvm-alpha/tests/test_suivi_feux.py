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


def _projection_regle(cash_apres, titres, cours, dividendes, debut):
    """Projection de F7 (d) de la règle déclarée (dividendes gardés jusqu'à janvier), sans frais fixes pour coller au
    carnet de ces jeux d'essai (qui n'en saisit pas)."""
    from brvm_alpha.config import CostModel
    from brvm_alpha.rendement import liquidites as LQ

    o = {"asof": str(debut.date()), "execution": {"premiere_seance": str(debut.date())},
         "lignes": [{"symbole": "AAA", "cibles": titres, "cours_reference": cours, "poids_cible": 0.9, "limite_achat": cours}],
         "dividendes": [{"symbole": "AAA", "date_paiement_prevue": str(d.date()), "dividende_net_prevu_par_titre": n,
                         "montant_net": n * titres} for d, n in dividendes],
         "couts": {"liquidites_apres": cash_apres, "forfait_compte_annuel": 0.0}}
    return LQ.projection(o, costs=CostModel(annual_custody=0.0, account_fee_per_line_fcfa=0.0), serie=True)


def test_regle_testee_dividendes_de_mai_a_septembre_feu_fuites_vert(tmp_path):
    jours_div = [JOURS[20], JOURS[45], JOURS[70], JOURS[100]]
    c, p = _portefeuille(tmp_path)
    for i, d in enumerate(jours_div):
        c.ajouter({"type": "dividende", "date": d, "symbole": "AAA", "titres": 9000, "net_par_titre": 5 + i,
                   "montant": 9000 * (5 + i)})
    # La condition (b) compare à ce que la règle déclarée prévoit : la projection de F7 (d), même date.
    proj = _projection_regle(1_000_000 - 9000 * 100 - 7200, 9000, 100.0, [(d, 5 + i) for i, d in enumerate(jours_div)],
                             JOURS[1])
    ls = BU.lignes_semaines(c.operations(), p, debut=JOURS[0], prevu=BU.prevu_depuis_projection(proj))
    BU.ecrire_semaines("PLAN", ls, tmp_path)
    assert ls[-1]["argent_qui_dort"] > 100_000  # les dividendes attendent la remise à niveau de janvier
    assert abs(ls[-1]["argent_qui_dort"] - ls[-1]["argent_qui_dort_prevu"]) < 1  # c'est ce que la règle prévoit
    b = BU.depuis_journal("PLAN", tmp_path, aujourd_hui=JOURS[-1])
    assert b["feux"]["fuites"]["etat"] == "vert" and b["feux"]["fuites"]["b_calcule"]
    assert b["feux"]["fuites"]["phrase"] == "aucune fuite au-delà de ce que la règle prévoit"
    assert any("sans objet (papier)" in x for x in b["feux"]["fuites"]["conditions"])
    assert b["feux"]["donnees"]["etat"] == "vert" and b["feux"]["perte"]["etat"] == "vert"


def test_argent_qui_dort_hors_de_la_regle_declaree_feu_orange_apres_20_seances(tmp_path):
    # MOI : 886 466 FCFA apportés en plus, jamais placés, pendant 12 semaines ; la règle déclarée ne les prévoit pas.
    c, p = _portefeuille(tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[2], "montant": 886_466})
    proj = _projection_regle(1_000_000 - 9000 * 100 - 7200, 9000, 100.0, [], JOURS[1])
    ls = BU.lignes_semaines(c.operations(), p, debut=JOURS[0], prevu=BU.prevu_depuis_projection(proj))[:13]
    assert ls[-1]["argent_qui_dort"] - ls[-1]["argent_qui_dort_prevu"] > 860_000
    etats = [AL.feux(BU.semaine_pour_feux(ls[: i + 1]))["fuites"]["etat"] for i in range(len(ls))]
    seances = [BU.semaine_pour_feux(ls[: i + 1])["seances_argent_qui_dort_au_dela"] for i in range(len(ls))]
    k = next(i for i, x in enumerate(seances) if x > 20)
    assert set(etats[:k]) == {"vert"} and set(etats[k:]) == {"orange"}
    f = AL.feux(BU.semaine_pour_feux(ls))["fuites"]
    assert "(b) argent qui dort" in f["phrase"] and "aucune fuite" not in f["phrase"]


def test_sans_la_regle_declaree_la_condition_b_n_est_pas_calculee(tmp_path):
    # Le même portefeuille, sans projection : l'argent qui dort n'est jamais comparé à lui-même.
    c, p = _portefeuille(tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[2], "montant": 886_466})
    ls = BU.lignes_semaines(c.operations(), p, debut=JOURS[0])[:13]
    assert ls[-1]["argent_qui_dort_prevu"] is None
    BU.ecrire_semaines("MOI", ls, tmp_path)
    assert BU.semaines_du_journal("MOI", tmp_path)[-1]["argent_qui_dort_prevu"] is None
    b = BU.depuis_journal("MOI", tmp_path, aujourd_hui=ls[-1]["vendredi"])
    f = b["feux"]["fuites"]
    assert f["etat"] == "vert" and not f["b_calcule"]
    assert "(b) argent qui dort au-delà de la règle déclarée : non calculé" in f["phrase"]
    assert "aucune fuite au-delà de ce que la règle prévoit" not in f["phrase"]


def test_dividende_non_credite_prochain_prelevement_et_w1_critique(tmp_path):
    c, p = _portefeuille(tmp_path)
    ls = BU.lignes_semaines(c.operations(), p, debut=JOURS[0])
    det = pd.DataFrame([{"symbole": "AAA", "date_detachement": JOURS[10], "date_paiement": JOURS[12], "montant": 45_000.0}])
    jour = JOURS[12] + pd.Timedelta(days=31)
    s = BU.semaine_pour_feux(ls, detaches=det, operations=c.operations(), aujourd_hui=jour)
    assert s["dividendes_non_credites"] == [{"symbole": "AAA", "date_paiement": str(JOURS[12].date()), "montant": 45_000.0}]
    assert AL.feux(s)["fuites"]["etat"] == "orange" and "(d) dividende non crédité" in AL.feux(s)["fuites"]["phrase"]
    assert BU.semaine_pour_feux(ls, detaches=det, operations=c.operations(),
                                aujourd_hui=JOURS[12] + pd.Timedelta(days=29))["dividendes_non_credites"] == []
    c.ajouter({"type": "dividende", "date": JOURS[13], "symbole": "AAA", "titres": 9000, "net_par_titre": 5, "montant": 45_000})
    assert BU.semaine_pour_feux(ls, detaches=det, operations=c.operations(), aujourd_hui=jour)["dividendes_non_credites"] == []
    # Rouge : liquidités sous le prochain prélèvement, ou frais annuels au-dessus des dividendes attendus (rendez-vous).
    rdv = {"prelevement": {"date": "2027-12-31", "montant": 10_000_000}, "frais_annuels": 50_000, "dividendes_12_mois": 40_000}
    s2 = BU.semaine_pour_feux(ls, rendez_vous=rdv)
    assert s2["prochain_prelevement"] == 10_000_000 and s2["w1_critique"]
    f = AL.feux(s2)["fuites"]
    assert f["etat"] == "rouge" and "ne couvrent pas le prochain prélèvement" in f["phrase"]
    BU.ecrire_semaines("PLAN", ls, tmp_path)
    b = BU.depuis_journal("PLAN", tmp_path, rendez_vous=rdv, aujourd_hui=JOURS[-1])
    assert b["feux"]["fuites"]["etat"] == "rouge"


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

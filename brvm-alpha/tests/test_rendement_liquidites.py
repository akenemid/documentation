"""F7 — Argent qui dort, provision d'entrée, « passer l'ordre » ; F13c — arrondi « plus forts restes » (information,
éteint par défaut). Cahier ``docs/RENDEMENT_NET.md``, §F7, §F13c. Recette sur les ordres figés du 20/11/2026."""

from __future__ import annotations

import copy
import datetime as dt

import pandas as pd
import pytest

import rendement_jeux as J
from brvm_alpha.rendement import grille as G
from brvm_alpha.rendement import liquidites as LQ

RECETTE = {"1M": (120_250, 113_740, 885_665, 114_335, 112_267, 61_025, (51_083, 76_625)),
           "10M": (188_852, 149_440, 9_866_731, 133_269, 110_269, 65_485, (62_063, 93_095)),
           "50M": (310_387, 197_760, 49_895_388, 104_612, -11_697, 0, (111_003, 166_505))}


@pytest.mark.parametrize("cap", sorted(RECETTE))
def test_recette(cap):
    apres, reliquat, prov, marge, marge2, arr, (r2, r3) = RECETTE[cap]
    o = J.ordre(cap)
    d = LQ.decomposition(o)
    assert d["liquidites_apres"] == apres and d["reliquat_arrondi"] == reliquat
    assert d["ecart_identite"] == 0 and d["ecart_identite_premier_achat"] == 0
    p = LQ.provision_entree(o)
    assert (p["provision_pire_cas"], p["marge"], p["marge_courtage_plus_cher"]) == (prov, marge, marge2)
    assert LQ.arrondi_restes(o)["francs_ajoutes"] == arr
    assert LQ.reserve_fonctionnement(o)["trimestres"] == {"2": r2, "3": r3}  # demi vers le haut : 93 094,5 → 93 095


def test_decomposition_10M_texte():
    d = LQ.decomposition(J.ordre("10M"))
    assert (d["hors_cible"], d["reliquat_arrondi"], d["frais_achat"]) == (200_000, 149_440, 160_588)


def test_parts_investies_maximales():
    p = LQ.provision_entree(J.ordre("10M"))
    assert abs(p["rho"] - 1.00984) < 1e-5 and abs(p["tau"] - 0.01244) < 1e-9
    attendu = {"optimistic": 0.9819, "central": 0.9781, "stress": 0.9758, "severe": 0.9702}
    for k, v in attendu.items():
        assert abs(p["parts_par_scenario"][k] - v) < 0.0001, k
    assert abs(p["part_investie_max"] - 0.9781) < 0.0001
    assert "la cible de 98 % n'est pas atteignable" in p["texte"] and "9\u202f866\u202f731 FCFA" in p["texte"]


def test_arrondi_plus_forts_restes_10M():
    o = J.ordre("10M")
    a = LQ.arrondi_restes(o)
    assert not a["applique"] and a["titres_ajoutes"] == 8 and a["investi"] == 9_716_045
    assert round(a["part_investie"], 4) == 0.9716 and a["marge_pire_cas"] == 66_323 and a["frais_achat_en_plus"] == 1_205
    assert round(100 * a["somme_ecarts"], 3) == 1.052 and round(100 * a["somme_ecarts_depart"], 3) == 1.494
    assert a["marge_courtage_1_5pct"] == -14_720 and abs(a["marge_M"] - 62_250) < 1e-6
    for s, q in a["quantites"].items():  # au plus un titre de plus par ligne
        ligne = next(l for l in o["lignes"] if l["symbole"] == s)
        assert ligne["cibles"] <= q <= ligne["cibles"] + 1
    assert a["somme_ecarts"] <= a["somme_ecarts_depart"] and a["investi"] <= 0.98 * 10_000_000
    assert "Avec l'arrondi « plus forts restes » : +65\u202f485 FCFA placés (97,16 % au lieu de 96,51 %)" in a["texte"]
    assert "écart à la règle testée" in a["texte"]
    assert round(LQ.arrondi_restes(J.ordre("1M"))["part_investie"], 4) == 0.9273
    m50 = LQ.arrondi_restes(J.ordre("50M"))
    assert m50["francs_ajoutes"] == 0 and m50["motif"].startswith("marge de")


def test_arrondi_refuse_sur_tarif_suppose_et_plafond_sature():
    o = J.ordre("10M")
    with pytest.raises(ValueError, match="grille du courtier est supposée"):
        LQ.arrondi_restes(o, appliquer=True)
    assert LQ.arrondi_restes(o, appliquer=True, forcer=True)["applique"]
    o2 = copy.deepcopy(o)
    for e in o2["explications"]:
        if e["symbole"] == "SIBC":
            e["plafonds"]["upper"] = 0.0  # plafond saturé : la ligne ne reçoit rien
    a = LQ.arrondi_restes(o2)
    assert "SIBC" not in a["lignes_ajoutees"] and a["quantites"]["SIBC"] == 62
    o3 = copy.deepcopy(o)
    for e in o3["explications"]:
        e["plafonds"].pop("upper", None)  # plafond inconnu : rien
    assert LQ.arrondi_restes(o3)["titres_ajoutes"] == 0


def test_projection_a_cours_constants():
    pr = LQ.projection(J.ordre("10M"))
    assert pr["dividendes_total"] == 435_988 and pr["n_paiements"] == 20
    assert pr["premier_paiement"] == "2027-05-03" and pr["dernier_paiement"] == "2027-09-23"
    assert pr["dividendes_par_mois"] == {"2027-05": 176_222, "2027-06": 82_179, "2027-07": 109_374, "2027-08": 62_762,
                                         "2027-09": 5_451}
    assert abs(pr["moyenne_avant_remise_a_niveau"] - 183_259) < 1_000
    assert abs(pr["moyenne_annee_suivante"] - 388_420) < 1_000
    assert abs(pr["pointe"] - 550_364) < 1 and abs(pr["a_la_remise_a_niveau"] - 487_791) < 1
    for d in (p for p in [pr["premier_paiement"], pr["dernier_paiement"]]):
        assert dt.date.fromisoformat(d) > dt.date(2026, 11, 20)  # aucune date de paiement dans le passé
    ed = LQ.projection(J.ordre("10M"), reinvestir=True)
    assert [(a["date"], a["symbole"], a["titres"]) for a in ed["achats"]] == [("2027-05-31", "SGBC", 3), ("2027-08-31", "SNTS", 30)]
    assert ed["frais_achats"] == 3_250 and ed["achete"] == 237_585
    assert abs(ed["moyenne_annee_suivante"] - 260_923) < 1_000 and abs(ed["remis_au_travail_moyen"] - 127_497) < 1_000
    g = G.defaut().avec(courtage_min_par_ordre=2500)
    assert LQ.projection(J.ordre("10M"), g, reinvestir=True)["achats"] == []  # montant permis sous S


def test_argent_qui_dort_portefeuille_detenu():
    o = J.ordre("detenu_624840")
    # Sans panel, les dividendes reçus depuis janvier ne sont pas connus ; aucun ordre n'est en cours (lignes gelées
    # par la bande) : rien n'est « prévu » sans preuve, l'argent qui dort est de cause « inconnue ».
    a = LQ.argent_qui_dort(o)
    assert a["D"] == 419_332 and a["aucun_ordre"] and a["D"] == a["D_prevu"] + a["D_hors_regle"]
    assert a["D_prevu"] == 0 and [c["code"] for c in a["causes"]] == ["inconnue"] and a["D_hors_regle"] == 419_332
    # Mesuré (mémoire ou carnet) : l'argent laissé par la dernière remise à niveau est prévu par la règle.
    m = LQ.argent_qui_dort(o, memoire={"reliquat_remise_a_niveau": 150_000})
    assert next(c for c in m["causes"] if c["code"] == "bande_mesuree")["montant"] == 150_000 and m["D_prevu"] == 150_000
    p = {"dividends_table": J.dividendes_2026()}
    b = LQ.argent_qui_dort(o, panels=p)
    div = next(c for c in b["causes"] if c["code"] == "dividendes_gardes")
    assert div["statut"] == "Estimation" and div["prevu"] and b["D_hors_regle"] == 0
    assert b["texte"].startswith("Liquidités 624\u202f840 FCFA (6,1 %). Aucun ordre proposé : la règle n'achète pas hors de "
                                 "la remise à niveau de janvier, et la bande de 2 points gèle chaque ligne. Cet argent est "
                                 "prévu par la règle testée")
    assert "(dividendes gardés jusqu'à fin janvier)" in b["texte"]
    assert sum(c["montant"] for c in b["causes"]) == b["D"] == b["D_prevu"] + b["D_hors_regle"]
    est = LQ.dividendes_depuis_janvier(o, p)
    assert est["depuis"] == "2026-01-30" and est["montant"] == 435_988  # SNTS ramené à la division de 10 pour 1


def test_argent_qui_dort_service_partiel():
    o = J.ordre("partiel")
    orig = {l["symbole"]: l["cibles"] for l in J.ordre("10M")["lignes"] if l["cibles"] > 0}
    a = LQ.argent_qui_dort(o, memoire={"quantites_origine": orig})
    ns = next(c for c in a["causes"] if c["code"] == "ordres_non_servis")
    assert ns["montant"] == 469_430 and not ns["prevu"]
    # Le reste (6 982 FCFA) vient des lignes gelées : cause inconnue sans mesure, sous le seuil de l'alerte.
    assert a["D"] == 476_412 and a["D_hors_regle"] == 476_412 and a["D"] == a["D_prevu"] + a["D_hors_regle"]
    assert next(c for c in a["causes"] if c["code"] == "inconnue")["montant"] == 6_982
    sans = LQ.argent_qui_dort(o)
    assert sans["D"] == 476_412


def test_consignes():
    o = J.ordre("10M")
    c = LQ.consignes(o)
    assert c == LQ.CONSIGNES and len(c) == 6
    c7 = LQ.consignes(o, carnet=J.carnet())
    assert c7[:6] == LQ.CONSIGNES
    assert c7[6] == ("Au dernier carnet, 5 lignes ont un prix demandé au-dessus de votre limite et 5 n'offrent pas assez "
                     "de titres au meilleur prix.")


def test_argent_d_origine_inconnue_n_est_pas_range_dans_la_regle():
    # Portefeuille détenu du 20/11/2026 plus 300 000 FCFA d'origine inconnue : la bande de 2 points gèle chaque ligne,
    # mais elle n'explique pas d'où vient cet argent : il n'est pas « prévu par la règle testée ».
    o = copy.deepcopy(J.ordre("detenu_624840"))
    for k in ("liquidites_initiales", "valeur_portefeuille"):
        o[k] += 300_000
    o["couts"]["liquidites_apres"] += 300_000
    a = LQ.argent_qui_dort(o, panels={"dividends_table": J.dividendes_2026()})
    assert a["D"] == 713_332 and a["D"] == a["D_prevu"] + a["D_hors_regle"]
    causes = {c["code"]: c for c in a["causes"]}
    assert causes["dividendes_gardes"]["montant"] == 435_988 and "regle" not in causes  # aucun ordre en cours
    assert causes["inconnue"]["montant"] == a["D_hors_regle"] == 277_344  # ancienne lecture : 0 (tout « prévu »)
    assert "(cause : inconnue)" in a["texte"]


def test_dividendes_depuis_janvier_sans_les_divisions_d_actions():
    o = J.ordre("detenu_624840")
    sans = J.dividendes_2026().drop(columns=["facteur_division"])
    est = LQ.dividendes_depuis_janvier(o, {"dividends_table": sans})
    assert est["montant"] is None and "non calculés" in est["non_calcule"]  # jamais un facteur 1 en silence
    a = LQ.argent_qui_dort(o, panels={"dividends_table": sans})
    assert "dividendes_gardes" not in {c["code"] for c in a["causes"]}
    assert "Dividendes depuis janvier : non calculés" in a["texte"]
    # Avec la table des opérations sur titres (vide : aucune division), le calcul a lieu.
    ca = pd.DataFrame(columns=["date", "symbol", "kind", "ratio"])
    assert LQ.dividendes_depuis_janvier(o, {"dividends_table": sans, "corporate_actions": ca})["montant"] is not None


def test_arrondi_possible_dit_gain_ou_perte_selon_le_marche_et_carnet_compte():
    o = J.ordre("10M")
    ar = LQ.arrondi_restes(o)
    assert ar["francs_ajoutes"] == 65_485 and ar["texte"].endswith("Gain ou perte selon le marché.")
    k = LQ.compte_carnet(o, J.carnet())
    assert k == {"n1": 5, "n2": 5, "date": "2026-11-20"} and LQ.compte_carnet(o, None) is None


def test_projection_serie_et_portefeuille_detenu():
    o = J.ordre("10M")
    pr = LQ.projection(o, serie=True)
    assert "serie" not in LQ.projection(o)
    assert pr["serie"][pr["fin"]] == pr["a_la_remise_a_niveau"] and len(pr["serie"]) > 400
    from brvm_alpha.suivi import bulletin as BU

    prevu = BU.prevu_depuis_projection(pr)
    assert prevu(pd.Timestamp("2027-06-30"), {"valeur": 10_000_000}) == pytest.approx(
        pr["serie"]["2027-06-30"] - 0.02 * 10_000_000)
    assert prevu(pd.Timestamp("2030-01-01"), {"valeur": 1}) is None

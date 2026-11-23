"""F10 — Journal du suivi : pont « fuites / pertes latentes » à une seule base, valeur de part, divisions, semaines
manquantes, idempotence, « le passé a changé », bulletin (cahier ``docs/RENDEMENT_NET.md``, §F10).

Panels de synthèse fabriqués (aucune date réelle choisie après coup, aucune donnée réelle) ; écritures dans des dossiers
temporaires seulement.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

import suivi_jeux as J
from brvm_alpha import suivi as S
from brvm_alpha.rendement import reglages as RG
from brvm_alpha.suivi import bulletin as BU
from brvm_alpha.suivi import carnet as CN
from brvm_alpha.suivi import etat as ET

JOURS = pd.bdate_range("2026-12-01", periods=15)


def _carnet(tmp_path, nom="MOI"):
    return CN.ouvrir(nom, tmp_path)


def _achat(c, date, sym, n, prix, ref, frais, decision=None):
    o = c.ajouter({"type": "ordre", "date": decision or date, "symbole": sym, "sens": "achat", "titres": n,
                   "limite": prix + 5, "cours_reference": ref, "motif": "remise_a_niveau"})
    return c.ajouter({"type": "execution", "date": date, "symbole": sym, "sens": "achat", "titres": n, "prix": prix,
                      "frais": {"courtage": frais}, "ordre": o["n"], "source": "papier"})


def test_pont_exemple_de_recette_achat_puis_vente(tmp_path):
    # apport 2 000 ; achat de 10 titres, référence 100, exécution 101, frais 10 ; clôture 105
    p = J.panel_simple(JOURS[:8], {"AAA": [100, 100, 105, 105, 110, 110, 110, 110]})
    c = _carnet(tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[0], "montant": 2000})
    _achat(c, JOURS[1], "AAA", 10, 101, 100, 10, decision=JOURS[0])
    x = ET.pont(c.operations(), p, JOURS[2])
    assert (x["L"], x["V"], x["E"]) == (980.0, 2030.0, 30.0)
    assert (x["effet_cours"], x["frais_transaction"]) == (50.0, 20.0) and x["identite_ok"]
    # vente des 10 titres : référence 110, exécution 109, frais f2 = 7
    o = c.ajouter({"type": "ordre", "date": JOURS[4], "symbole": "AAA", "sens": "vente", "titres": 10, "limite": 105,
                   "cours_reference": 110, "motif": "sortie"})
    c.ajouter({"type": "execution", "date": JOURS[5], "symbole": "AAA", "sens": "vente", "titres": 10, "prix": 109,
               "frais": {"courtage": 7}, "ordre": o["n"], "source": "papier"})
    y = ET.pont(c.operations(), p, JOURS[6])
    assert y["effet_cours"] == 100.0 and y["frais_transaction"] == 10 + 7 + 10 + 10
    assert y["E"] == 80 - 10 - 7 == y["V"] - y["K"] and y["identite_ok"]
    # l'ancienne écriture (effet de cours contre le prix d'exécution ET coût dans le prix dans les frais) donnait 20
    assert x["effet_cours"] - x["frais_transaction"] != 20


def test_cout_dans_le_prix_negatif_accepte(tmp_path):
    p = J.panel_simple(JOURS[:5], {"AAA": [100, 100, 100, 104, 104]})
    c = _carnet(tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[0], "montant": 5000})
    _achat(c, JOURS[1], "AAA", 20, 98, 100, 15, decision=JOURS[0])  # servi sous le cours de référence
    ops = c.operations()
    assert ops.loc[ops["type"] == "achat", "cout_prix"].iloc[0] == -40.0
    x = ET.pont(ops, p, JOURS[4])
    assert x["frais_transaction"] == 15 - 40 and x["identite_ok"] and x["E"] == x["V"] - x["K"]


def test_valeur_de_part_deux_apports_marche_plat_sans_frais(tmp_path):
    p = J.panel_simple(JOURS, {"AAA": [100.0] * len(JOURS)}, indice=250.0)
    c = _carnet(tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[0], "montant": 1_000_000})
    _achat(c, JOURS[1], "AAA", 5000, 100, 100, 0, decision=JOURS[0])
    c.ajouter({"type": "apport", "date": JOURS[7], "montant": 3_000_000})
    ls = BU.lignes_semaines(c.operations(), p, debut=JOURS[0])
    assert len(ls) == 3
    for l in ls:
        assert l["ecart_au_marche"] == pytest.approx(0.0, abs=1e-12) and l["valeur_de_part"] == pytest.approx(1.0)
    # l'ancien calcul V ÷ K ÷ indice serait juste ici ; avec une hausse entre deux apports il serait faux :
    p2 = J.panel_simple(JOURS, {"AAA": [100.0] * 5 + [110.0] * 10}, indice=[100.0] * 5 + [110.0] * 10)
    ls2 = BU.lignes_semaines(c.operations(), p2, debut=JOURS[0])
    l = ls2[-1]
    assert l["valeur_de_part"] == pytest.approx(1 + 0.5 * 0.10)  # moitié investie lors de la hausse
    assert l["ecart_au_marche"] == pytest.approx(1.05 / 1.10 - 1)


def test_division_aucune_fausse_perte(tmp_path):
    # 64 titres à 1 000 ; division 10 pour 1 : 640 titres à 100 le jour de la division
    raw = [1000.0] * 6 + [100.0] * 9
    p = J.panel_simple(JOURS, {"AAA": [100.0] * 15}, raw={"AAA": raw})
    c = _carnet(tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[0], "montant": 100_000})
    _achat(c, JOURS[1], "AAA", 64, 1000, 1000, 0, decision=JOURS[0])
    sans = ET.serie(c.operations(), p, debut=JOURS[0])
    assert sans.loc[JOURS[6], "V"] - sans.loc[JOURS[5], "V"] == -57_600  # sans la division : fausse perte de 90 %
    c.ajouter({"type": "division", "date": JOURS[6], "symbole": "AAA", "rapport": 10})
    s = ET.serie(c.operations(), p, debut=JOURS[0])
    assert s.loc[JOURS[6], "V"] == s.loc[JOURS[5], "V"] == 100_000
    assert (s["ecart_identite"].abs() < 0.5).all()
    pos = c.positions(JOURS[6])["AAA"]
    assert pos["titres"] == 640 and pos["prix_de_revient"] == pytest.approx(100.0)


def test_vendredi_sans_bulletin_une_ligne_feu_orange(tmp_path):
    jours = JOURS[:3]  # du mardi 01/12 au jeudi 03/12/2026 : le vendredi 04/12 est sans bulletin
    p = J.panel_simple(jours, {"AAA": [100.0] * len(jours)})
    c = _carnet(tmp_path)
    c.ajouter({"type": "apport", "date": jours[0], "montant": 10_000})
    ls = BU.lignes_semaines(c.operations(), p, debut=jours[0], jusqu_au="2026-12-07")
    assert [l["vendredi"] for l in ls] == ["2026-12-04"]
    assert ls[0]["date"] == "2026-12-03" and ls[0]["bulletins_manquants"] == 1
    BU.ecrire_semaines("MOI", ls, tmp_path)
    b = BU.depuis_journal("MOI", tmp_path, aujourd_hui="2026-12-07")
    assert b["feux"]["donnees"]["etat"] == "orange"
    # la table des séances du panel fait foi quand elle existe
    ses = pd.DataFrame({"date": JOURS[:5], "available": [True, True, True, False, True]})
    p2 = J.panel_simple(JOURS[:5], {"AAA": [100.0] * 5}, sessions=ses)
    l2 = BU.lignes_semaines(c.operations(), p2, debut=JOURS[0])
    assert l2[0]["bulletins_manquants"] == 1


def test_idempotence_et_passe_a_change(tmp_path):
    p = J.panel_simple(JOURS, {"AAA": [100.0 + i for i in range(15)]})
    c = _carnet(tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[0], "montant": 10_000})
    _achat(c, JOURS[1], "AAA", 50, 101, 100, 12, decision=JOURS[0])
    ls = BU.lignes_semaines(c.operations(), p, debut=JOURS[0])
    r1 = BU.ecrire_semaines("MOI", ls, tmp_path)
    r2 = BU.ecrire_semaines("MOI", ls, tmp_path)
    assert r1["ajoutees"] == 3 and r2["ajoutees"] == 0 and r2["identiques"] == 3 and not r2["passe_a_change"]
    f = tmp_path / "MOI" / "semaines.csv"
    assert len(f.read_text(encoding="utf-8").splitlines()) == 4
    avant = f.read_bytes()
    p2 = J.panel_simple(JOURS, {"AAA": [100.0 + i for i in range(5)] + [90.0] * 10})
    ls2 = BU.lignes_semaines(c.operations(), p2, debut=JOURS[0])
    r3 = BU.ecrire_semaines("MOI", ls2, tmp_path)
    assert r3["passe_a_change"] and len(r3["anomalies"]) == 2 and f.read_bytes() == avant
    r4 = BU.ecrire_semaines("MOI", ls2, tmp_path)
    assert r4["anomalies"] == []  # une seule entrée par écart
    a = [json.loads(x) for x in (tmp_path / "MOI" / "anomalies.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all(x["cause"] == "le passé a changé" and x["cause_probable"] == "donnée corrigée" for x in a)
    # chaîne : une réécriture de semaines.csv est détectée
    lignes = f.read_text(encoding="utf-8").splitlines()
    lignes[1] = lignes[1].replace(",50,", ",51,", 1)
    f.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    assert not BU.verifier_semaines("MOI", tmp_path)["ok"]
    assert BU.depuis_journal("MOI", tmp_path, aujourd_hui="2026-12-21")["feux"]["donnees"]["etat"] == "rouge"


def test_refus_des_dates_de_S1_et_de_reports(tmp_path):
    p = J.panel_simple(pd.bdate_range("2022-11-07", periods=10), {"AAA": [100.0] * 10})
    with pytest.raises(S.DateDeS1):
        BU.lignes_semaines(CN.operations_depuis_mouvements([]), p, debut="2022-11-14")
    with pytest.raises(S.DateDeS1):
        _carnet(tmp_path).ajouter({"type": "apport", "date": "2022-11-16", "montant": 1})
    with pytest.raises(S.DossierInterdit):
        BU.ecrire_semaines("MOI", [], J.RACINE / "reports" / "suivi_S2")
    avant = sorted(p.name for p in (J.RACINE / "reports").iterdir())
    with pytest.raises(S.DossierInterdit):
        CN.ouvrir("MOI", J.RACINE / "reports")
    assert sorted(p.name for p in (J.RACINE / "reports").iterdir()) == avant


def _ligne_bulletin(tmp_path):
    p = J.panel_simple(JOURS, {"AAA": [100.0] * 5 + [95.0] * 10})
    c = _carnet(tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[0], "montant": 10_000})
    _achat(c, JOURS[1], "AAA", 50, 101, 100, 12, decision=JOURS[0])
    return BU.lignes_semaines(c.operations(), p, debut=JOURS[0])


def test_bulletin_gabarit_phrases_et_lexique(tmp_path):
    ls = _ligne_bulletin(tmp_path)
    b = BU.bulletin(ls[-1], nom="MOI", aujourd_hui="2026-12-21", ecart_marche_temoin=-0.012)
    t = BU.rendre(b, "texte")
    assert t.startswith("BULLETIN DE LA SEMAINE — vendredi 18/12/2026 — semaine 3 — portefeuille sur papier")
    plat = " ".join(t.split())
    for ph in (RG.BANNER, RG.PH_ETUDE, RG.phrase_seance("2026-12-21"), RG.PH_REVUE, "Étude seulement.",
               "Frais partis pour de bon", "Baisses de cours non vendues", "elles peuvent se retourner", "ou s'aggraver",
               "FEU PERTE", "FEU FUITES", "FEU DONNÉES", "À REVOIR (pas à vendre)", "PROCHAINS RENDEZ-VOUS",
               "remise à niveau le 29/01/2027", "LE PANIER DE RÉFÉRENCE FACE AU MARCHÉ : −1,2 %",
               "retard attendu", "3,3 à 4,2 points", "cet écart ne prouve rien"):
        assert ph in plat, ph
    assert RG.mots_interdits(t) == []
    assert max(len(x) for x in t.splitlines()) <= 100
    l = ls[-1]
    assert f"Mon portefeuille vaut {RG.fcfa(l['valeur'])}" in t
    assert RG.fcfa(l["fuites_definitives"]) in t
    md, js = BU.rendre(b, "md"), json.loads(BU.rendre(b, "json"))
    assert RG.BANNER in md and js["bandeau"] == RG.BANNER and js["valeurs"]["valeur"] == l["valeur"]
    with pytest.raises(ValueError):
        BU.rendre(b, "pdf")


def test_bulletin_semaine_zero_et_sans_journal(tmp_path):
    b = BU.bulletin(None, nom="MOI", aujourd_hui="2026-11-24")
    t = BU.rendre(b)
    assert "semaine 0" in t and "état avant achat" in t and "le suivi n'a pas commencé" in t
    assert RG.mots_interdits(t) == [] and RG.BANNER in t and "à partir du 01/12/2026" in t
    b2 = BU.depuis_journal("RIEN", tmp_path, aujourd_hui="2026-11-24")
    assert b2["semaine"] == 0 and b2["feux"]["perte"]["etat"] == "—"


@pytest.mark.parametrize("jour", ["2026-11-23", "2026-11-25", "2026-11-20", "2026-11-22"])
def test_semaine_zero_en_tete_au_dernier_vendredi(jour):
    t = BU.rendre(BU.bulletin(None, nom="REF-S2", aujourd_hui=jour))
    assert t.startswith("BULLETIN DE LA SEMAINE — vendredi 20/11/2026 — semaine 0 — portefeuille sur papier")
    assert BU.dernier_vendredi(jour) == pd.Timestamp("2026-11-20")


def test_semaine_zero_du_temoin_argent_engage_et_pas_encore_de_titres():
    t = " ".join(BU.rendre(BU.bulletin(None, nom="REF-S2", aujourd_hui="2026-11-23")).split())
    assert ("Argent engagé : 10 000 000 FCFA (en liquidités) ; premier achat prévu à la séance du 01/12/2026."
            in t.replace("\u202f", " "))
    assert "PROCHAINS RENDEZ-VOUS : pas encore de titres ; remise à niveau le 29/01/2027" in t
    assert "aucun dividende attendu dans les 12 mois" not in t
    # Un portefeuille dont les rendez-vous ne sont pas calculés ne dit pas « aucun dividende attendu ».
    ls = _ligne_bulletin_simple()
    t2 = " ".join(BU.rendre(BU.bulletin(ls[-1], nom="MOI", aujourd_hui="2026-12-21")).split())
    assert "prochain dividende : non calculé" in t2 and "aucun dividende attendu" not in t2


def _ligne_bulletin_simple():
    import tempfile
    from pathlib import Path

    return _ligne_bulletin(Path(tempfile.mkdtemp(prefix="bulletin_")))


def test_ecart_au_marche_d_un_autre_portefeuille_jamais_sous_le_libelle_du_panier(tmp_path):
    ls = _ligne_bulletin(tmp_path)
    BU.ecrire_semaines("MOI", ls, tmp_path)
    t = " ".join(BU.rendre(BU.depuis_journal("MOI", tmp_path, aujourd_hui="2026-12-21")).split())
    assert f"{BU.LIGNE_MARCHE} : non calculé" in t  # pas de journal REF-S2 dans le dossier
    assert RG.pct(ls[-1]["ecart_au_marche"], 1, signe=True) not in t.split(BU.LIGNE_MARCHE)[1][:30]
    ref = [dict(l, ecart_au_marche=-0.0345) for l in ls]
    BU.ecrire_semaines("REF-S2", ref, tmp_path)
    t2 = " ".join(BU.rendre(BU.depuis_journal("MOI", tmp_path, aujourd_hui="2026-12-21")).split())
    assert f"{BU.LIGNE_MARCHE} : −3,5 %" in t2  # lu dans le journal du témoin
    t3 = " ".join(BU.rendre(BU.depuis_journal("REF-S2", tmp_path, aujourd_hui="2026-12-21")).split())
    assert f"{BU.LIGNE_MARCHE} : −3,5 %" in t3


def test_remise_a_niveau_de_fin_janvier():
    assert BU.remise_a_niveau_suivante("2026-12-04") == pd.Timestamp("2027-01-29")
    assert BU.remise_a_niveau_suivante("2027-01-29") == pd.Timestamp("2028-01-31")
    assert BU.vendredis("2026-11-30", "2026-12-18") == [pd.Timestamp(x) for x in ("2026-12-04", "2026-12-11",
                                                                                  "2026-12-18")]


def test_etat_par_ligne_si_l_on_vendait(tmp_path):
    p = J.panel_simple(JOURS, {"AAA": [100.0] * 5 + [80.0] * 10},
                       dividendes=[{"symbol": "AAA", "ex_date": JOURS[12], "amount": 4.0, "payment_date": JOURS[14],
                                    "date": JOURS[2]}])
    c = _carnet(tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[0], "montant": 10_000})
    _achat(c, JOURS[1], "AAA", 50, 101, 100, 12, decision=JOURS[0])
    e = ET.etat(c, p, JOURS[8])
    l = e["lignes"][0]
    assert l["titres"] == 50 and l["prix_de_revient"] == pytest.approx((50 * 101 + 12) / 50)
    assert l["baisse_depuis_achat"] == pytest.approx(1 - 80 / l["prix_de_revient"])
    assert l["si_l_on_vendait"]["frais_sortie"] > 0 and l["dividende_attendu"] == 200.0
    assert e["identite_ok"] and e["pertes_non_realisees"] == 50 * (80 - 100)
    assert e["fuites_definitives"] == 12 + 50


def test_prochains_rendez_vous_dans_le_bulletin(tmp_path):
    from brvm_alpha.portfolio import recommend as R

    p = J.panel_moteur()
    rv = BU.rendez_vous({"ABJC": 100, "BICB": 50}, p, "2024-02-15", valeur_titres=1_000_000)
    assert rv["dividende"]["statut"] == "estimé" and rv["dividende"]["montant"] > 0
    # Date de paiement calculée avec le calendrier des séances du panel (comme l'ordre de bataille).
    sch = R.dividend_schedule({"ABJC": 100, "BICB": 50}, "2024-02-15", p, calendar=pd.DatetimeIndex(p["close"].index))
    sch = sch[(sch["montant_net"] > 0) & sch["date_paiement_prevue"].notna()]
    assert rv["dividende"]["date"] == str(pd.to_datetime(sch["date_paiement_prevue"]).min().date())
    # Prélèvement au prorata des jours depuis le dernier prélèvement (fin du trimestre précédent : 91 jours).
    assert rv["prelevement"] == {"date": "2024-03-31", "statut": "supposé", "jours": 91,
                                 "montant": round((0.0025 * 1e6 + 2 * 5000) * 91 / 365)}
    # Depuis le début du suivi : prorata depuis ce jour-là ; témoin : son rythme de prélèvement (chaque semaine).
    rv2 = BU.rendez_vous({"ABJC": 100, "BICB": 50}, p, "2024-02-15", valeur_titres=1_000_000, dernier_prelevement="2024-03-01")
    assert rv2["prelevement"]["jours"] == 30 and rv2["prelevement"]["montant"] == round(12_500 * 30 / 365)
    rv3 = BU.rendez_vous({"ABJC": 100, "BICB": 50}, p, "2024-02-15", valeur_titres=1_000_000, rythme="semaine")
    assert rv3["prelevement"] == {"date": "2024-02-16", "statut": "supposé", "jours": 7, "montant": round(12_500 * 7 / 365)}
    assert rv["frais_annuels"] == 12_500 and rv["dividendes_12_mois"] >= rv["dividende"]["montant"]
    assert rv["remise_a_niveau"] == "2025-01-31"
    ls = _ligne_bulletin(tmp_path)
    t = " ".join(BU.rendre(BU.bulletin(ls[-1], rendez_vous=rv, aujourd_hui="2026-12-21")).split())
    assert "dividende attendu ABJC" in t and "estimé" in t and "prélèvement de frais vers le 31/03/2024" in t
    assert "remise à niveau le 31/01/2025" in t and RG.mots_interdits(t) == []
    assert BU.rendez_vous({}, p, "2024-02-15") == {"remise_a_niveau": "2025-01-31"}

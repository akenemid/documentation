"""F12 — Carnet : journal en ajout seul, prix de revient, mémoire, avis d'opéré (cahier ``docs/RENDEMENT_NET.md``, §F12).

Dossiers temporaires seulement ; dates de suivi fabriquées (après S1).
"""

from __future__ import annotations

import pandas as pd
import pytest

import suivi_jeux as J
from brvm_alpha import suivi as S
from brvm_alpha.rendement import grille as GR
from brvm_alpha.suivi import carnet as CN
from brvm_alpha.suivi import etat as ET

JOURS = pd.bdate_range("2026-12-01", periods=12)


def _exec(c, d, sym, sens, n, prix, frais=0.0, ordre=None, ref=None):
    return c.ajouter({"type": "execution", "date": d, "symbole": sym, "sens": sens, "titres": n, "prix": prix,
                      "frais": {"courtage": frais}, "ordre": ordre, "cours_reference": ref, "source": "papier"})


def test_identite_comptable_au_franc(tmp_path):
    p = J.panel_simple(JOURS, {"AAA": [100 + i for i in range(12)], "BBB": [50.0] * 12})
    c = CN.ouvrir("MOI", tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[0], "montant": 100_000})
    _exec(c, JOURS[1], "AAA", "achat", 300, 101, 377, ref=100)
    _exec(c, JOURS[1], "BBB", "achat", 500, 50, 311, ref=50)
    c.ajouter({"type": "dividende", "date": JOURS[4], "symbole": "BBB", "titres": 500, "net_par_titre": 2,
               "montant": 1000})
    c.ajouter({"type": "frais", "date": JOURS[5], "nature": "garde", "montant": 250})
    _exec(c, JOURS[6], "AAA", "vente", 100, 107, 133, ref=106)
    c.ajouter({"type": "retrait", "date": JOURS[8], "montant": 5000})
    c.ajouter({"type": "apport", "date": JOURS[9], "symbole": "CCC", "titres": 10, "cours": 300})
    p["close"]["CCC"] = 300.0
    for d in JOURS[1:]:
        x = ET.pont(c.operations(), p, d)
        # apports − retraits + résultat = titres + liquidités
        assert x["K"] + x["E"] == pytest.approx(x["T"] + x["L"]) and x["identite_ok"], d
    pos = c.positions()
    assert pos["AAA"]["titres"] == 200 and pos["AAA"]["prix_de_revient"] == pytest.approx((300 * 101 + 377) / 300)
    assert pos["AAA"]["resultat_realise"] == pytest.approx(100 * (107 - (300 * 101 + 377) / 300) - 133)
    assert pos["CCC"]["titres"] == 10 and x["T0"] == 3000 and x["K"] == 100_000 - 5000 + 3000


def test_division_10_pour_1(tmp_path):
    c = CN.ouvrir("MOI", tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[0], "montant": 1_000_000})
    _exec(c, JOURS[1], "SNTS", "achat", 64, 15_000, 1200)
    pr = c.positions()["SNTS"]["prix_de_revient"]
    c.ajouter({"type": "division", "date": JOURS[3], "symbole": "SNTS", "rapport": 10})
    p = c.positions()["SNTS"]
    assert p["titres"] == 640 and p["prix_de_revient"] == pytest.approx(pr / 10)
    assert c.positions(JOURS[2])["SNTS"]["titres"] == 64


def test_refus_double_vente_excessive_S1_type_correction(tmp_path):
    c = CN.ouvrir("MOI", tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[0], "montant": 10_000})
    with pytest.raises(ValueError, match="double"):
        c.ajouter({"type": "apport", "date": JOURS[0], "montant": 10_000})
    with pytest.raises(ValueError, match="vente refusée"):
        _exec(c, JOURS[1], "AAA", "vente", 1, 100)
    with pytest.raises(S.DateDeS1):
        c.ajouter({"type": "apport", "date": "2021-03-01", "montant": 5})
    with pytest.raises(ValueError, match="inconnu"):
        c.ajouter({"type": "cadeau", "date": JOURS[1]})
    with pytest.raises(ValueError, match="correction"):
        c.ajouter({"type": "correction", "date": JOURS[1], "annule": 99, "motif": "erreur"})
    with pytest.raises(ValueError, match="entier"):
        _exec(c, JOURS[1], "AAA", "achat", 1.5, 100)
    assert len(c.mouvements(actifs=False)) == 1


def test_correction_annule_sans_effacer(tmp_path):
    c = CN.ouvrir("MOI", tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[0], "montant": 10_000})
    m = _exec(c, JOURS[1], "AAA", "achat", 10, 100, 5)
    c.ajouter({"type": "correction", "date": JOURS[2], "annule": m["n"], "motif": "saisie sur le mauvais titre"})
    assert c.positions() == {} and c.liquidites() == 10_000
    assert len(c.mouvements(actifs=False)) == 3 and c.verifier()["ok"]


def test_chaine_du_carnet(tmp_path):
    c = CN.ouvrir("MOI", tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[0], "montant": 10_000})
    c.ajouter({"type": "apport", "date": JOURS[1], "montant": 20_000})
    t = c.fichier.read_text(encoding="utf-8")
    c.fichier.write_text(t.replace("10000", "11000", 1), encoding="utf-8")
    assert not c.verifier()["ok"]
    with pytest.raises(ValueError, match="chaîne rompue"):
        c.ajouter({"type": "apport", "date": JOURS[2], "montant": 1})


def test_memoire_pour_le_suivi(tmp_path):
    c = CN.ouvrir("PLAN", tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[0], "montant": 1_000_000})
    o1 = c.ajouter({"type": "ordre", "date": JOURS[0], "symbole": "AAA", "sens": "achat", "titres": 100, "limite": 105,
                    "cours_reference": 100, "motif": "remise_a_niveau"})
    o2 = c.ajouter({"type": "ordre", "date": JOURS[0], "symbole": "BBB", "sens": "achat", "titres": 40, "limite": 52,
                    "cours_reference": 50, "motif": "remise_a_niveau"})
    _exec(c, JOURS[1], "AAA", "achat", 100, 101, 100, ordre=o1["n"])
    _exec(c, JOURS[1], "BBB", "achat", 25, 51, 30, ordre=o2["n"])
    c.ajouter({"type": "expiration", "date": JOURS[10], "symbole": "BBB", "titres": 15, "ordre": o2["n"]})
    m = c.memoire()
    assert m["titres"] == {"AAA": 100, "BBB": 25} and m["memoire_ref"] == {"annee": 2026, "date": "2026-12-01"}
    assert m["non_servis"] == {"BBB": 15}
    assert m["liquidites"] == pytest.approx(1_000_000 - 100 * 101 - 100 - 25 * 51 - 30)
    ords = c.ordres()
    assert [o["etat"] for o in ords] == ["servi", "expiré"] and ords[1]["expire_le"] == JOURS[10].date().isoformat()


def test_avis_d_opere(tmp_path):
    g = GR.defaut()
    c = CN.ouvrir("MOI", tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[0], "montant": 1_000_000})
    a = 50 * 4000
    f = GR.frais_explicites(a, g)
    avis = [{"date": JOURS[1], "symbole": "SNTS", "sens": "achat", "titres": 50, "prix": 4000, "courtage": f["courtage"],
             "taxe": f["tva"], "brvm": f["brvm"], "dcbr": f["dcbr"], "cours_reference": 4010}]
    r = c.saisir_avis(avis, g)
    assert r["concorde"] and r["grille"].champs["courtage"].statut == GR.AVIS
    assert r["grille"].champs["taxe_courtage"].statut == GR.AVIS and g.champs["courtage"].statut == GR.SUPPOSE
    assert r["lignes"][0]["cout_prix_mesure"] == -500  # coût dans le prix négatif : accepté tel quel
    assert c.positions()["SNTS"]["titres"] == 50
    ops = c.operations()
    assert ops.iloc[-1]["source"] == "avis_opere" and ops.iloc[-1]["cout_prix"] == -500
    # courtage de 1 % : écart affiché en FCFA, grille inchangée tant que l'utilisateur ne confirme pas
    avis2 = [dict(avis[0], date=JOURS[2], courtage=0.01 * a, taxe=round(0.18 * 0.01 * a), autres_frais=1500)]
    r2 = c.saisir_avis(avis2, g)
    assert not r2["concorde"] and r2["lignes"][0]["ecarts_fcfa"]["courtage"] == 400
    assert r2["grille"] is g and r2["grille"].champs["courtage"].statut == GR.SUPPOSE
    assert r2["grille_proposee"].valeur("courtage") == pytest.approx(0.01)
    assert r2["postes_nouveaux"][0]["montant"] == 1500


def test_aucune_ecriture_hors_du_dossier_du_portefeuille(tmp_path):
    c = CN.ouvrir("MOI", tmp_path / "suivi")
    c.ajouter({"type": "apport", "date": JOURS[0], "montant": 10})
    fichiers = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    assert fichiers == ["suivi/MOI/carnet.jsonl"]
    with pytest.raises(ValueError):
        CN.ouvrir("../ailleurs", tmp_path)

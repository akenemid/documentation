"""F12 — Exécution sur papier avec test de limite (mode ``limite``) et sans (mode ``test``) (cahier
``docs/RENDEMENT_NET.md``, §F12, article E-L du §8.3).

Panels fabriqués, cours moyen du jour = clôture (valeur = clôture × volume) ; dossiers temporaires seulement.
"""

from __future__ import annotations

import pandas as pd
import pytest

import suivi_jeux as J
from brvm_alpha import suivi as S
from brvm_alpha.suivi import carnet as CN
from brvm_alpha.suivi import papier as PA

JOURS = pd.bdate_range("2026-12-01", periods=20)


def _carnet(tmp_path, montant=1_000_000):
    c = CN.ouvrir("PLAN", tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[0], "montant": montant})
    return c


def _ordre(c, sym, sens, n, limite, ref, d=None):
    return c.ajouter({"type": "ordre", "date": d or JOURS[0], "symbole": sym, "sens": sens, "titres": n, "limite": limite,
                      "cours_reference": ref, "validite": 10, "motif": "remise_a_niveau"})


def test_ordre_non_servi_au_dessus_de_la_limite_puis_expire(tmp_path):
    p = J.panel_simple(JOURS, {"AAA": [100.0] + [104.0] * 19})
    c = _carnet(tmp_path)
    o = _ordre(c, "AAA", "achat", 50, 102, 100)
    r = PA.executer(c, p, JOURS[-1])
    types = [m["type"] for m in r["ajoutes"]]
    assert "execution" not in types and types.count("expiration") == 1
    exp = next(m for m in r["ajoutes"] if m["type"] == "expiration")
    assert exp["date"] == JOURS[10].date().isoformat() and exp["titres"] == 50 and exp["ordre"] == o["n"]
    # mode « test » (§7.1, sans test de limite) : servi au cours moyen du jour suivant
    c2 = CN.ouvrir("E-C", tmp_path)
    c2.ajouter({"type": "apport", "date": JOURS[0], "montant": 1_000_000})
    _ordre(c2, "AAA", "achat", 50, 102, 100)
    r2 = PA.executer(c2, p, JOURS[-1], mode="test")
    ex = [m for m in r2["ajoutes"] if m["type"] == "execution"]
    assert len(ex) == 1 and ex[0]["date"] == JOURS[1].date().isoformat() and ex[0]["prix"] == 104.0
    assert ex[0]["frais"]["autres"] > 0  # écart et impact estimés, payés comme dans le moteur


def test_servi_sous_la_limite_dix_pour_cent_du_volume_et_report(tmp_path):
    p = J.panel_simple(JOURS, {"AAA": [100.0] * 20}, volume=200.0)
    c = _carnet(tmp_path)
    _ordre(c, "AAA", "achat", 50, 102, 100)
    r = PA.executer(c, p, JOURS[-1])
    ex = [m for m in r["ajoutes"] if m["type"] == "execution"]
    assert [m["titres"] for m in ex] == [20, 20, 10] and [m["date"] for m in ex] == [d.date().isoformat() for d in JOURS[1:4]]
    assert all(m["prix"] == 100.0 and m["frais"]["courtage"] > 0 for m in ex)
    assert c.ordres()[0]["etat"] == "servi"
    m = r["mesures"]
    assert m["part_servie"] == {"1_seances": 0.4, "3_seances": 1.0, "10_seances": 1.0} and m["seances_pour_finir"] == [3]
    # relance : idempotente
    assert PA.executer(c, p, JOURS[-1])["ajoutes"] == []


def test_vente_au_dessus_de_la_limite_seulement(tmp_path):
    p = J.panel_simple(JOURS, {"AAA": [100.0, 100.0, 95.0, 99.0] + [101.0] * 16})
    c = _carnet(tmp_path)
    c.ajouter({"type": "execution", "date": JOURS[0], "symbole": "AAA", "sens": "achat", "titres": 30, "prix": 100,
               "frais": {}, "source": "papier"})
    _ordre(c, "AAA", "vente", 30, 100, 100, d=JOURS[1])
    r = PA.executer(c, p, JOURS[6])
    ex = [m for m in r["ajoutes"] if m["type"] == "execution"]
    assert len(ex) == 1 and ex[0]["date"] == JOURS[4].date().isoformat() and ex[0]["prix"] == 101.0


def test_annulation_et_ressaisie_le_jour_d_un_detachement(tmp_path):
    prix = [100.0, 104.0, 104.0, 104.0, 96.0] + [96.0] * 15  # détachement de 8 FCFA le 5e jour
    div = [{"symbol": "AAA", "ex_date": JOURS[4], "amount": 8.0, "payment_date": JOURS[6], "date": JOURS[0]}]
    p = J.panel_simple(JOURS, {"AAA": prix}, dividendes=div)
    c = _carnet(tmp_path)
    o = _ordre(c, "AAA", "achat", 40, 102, 100)
    r = PA.executer(c, p, JOURS[8])
    res = [m for m in r["ajoutes"] if m["type"] == "ordre"]
    assert len(res) == 1 and res[0]["ressaisie_de"] == o["n"] and res[0]["date"] == JOURS[4].date().isoformat()
    assert res[0]["limite"] < 102 and res[0]["raison"] == "détachement"
    # référence ajustée : dernier cours 104 − 8 = 96 ; limite 102 × 96 ÷ 104 = 94,15 → pas de 1 FCFA sous 100 : 94
    assert res[0]["limite"] == 94.0
    ords = {o2["n"]: o2 for o2 in c.ordres()}
    assert ords[o["n"]]["etat"] == "ressaisi"


def test_achat_differe_jusqu_au_reglement_d_une_vente(tmp_path):
    p = J.panel_simple(JOURS, {"AAA": [100.0] * 20, "BBB": [50.0] * 20})
    c = CN.ouvrir("PLAN", tmp_path)
    c.ajouter({"type": "apport", "date": JOURS[0], "symbole": "AAA", "titres": 100, "cours": 100})
    _ordre(c, "AAA", "vente", 100, 99, 100, d=JOURS[0])
    _ordre(c, "BBB", "achat", 150, 51, 50, d=JOURS[0])
    r = PA.executer(c, p, JOURS[6])
    ex = [m for m in r["ajoutes"] if m["type"] == "execution"]
    vente = next(m for m in ex if m["sens"] == "vente")
    achats = [m for m in ex if m["sens"] == "achat"]
    assert vente["date"] == JOURS[1].date().isoformat()
    assert achats and achats[0]["date"] == JOURS[3].date().isoformat()  # règlement à deux séances


def test_dividende_credite_a_la_date_de_paiement_et_frais_de_trimestre(tmp_path):
    jours = pd.bdate_range("2026-12-01", "2027-01-08")
    div = [{"symbol": "AAA", "ex_date": pd.Timestamp("2026-12-10"), "amount": 5.0,
            "payment_date": pd.Timestamp("2026-12-14"), "date": pd.Timestamp("2026-12-01")}]
    p = J.panel_simple(jours, {"AAA": [100.0] * len(jours)}, dividendes=div)
    c = _carnet(tmp_path)
    _ordre(c, "AAA", "achat", 300, 101, 100)
    r = PA.executer(c, p, jours[-1])
    dv = [m for m in r["ajoutes"] if m["type"] == "dividende"]
    assert len(dv) == 1 and dv[0]["date"] == "2026-12-14" and dv[0]["montant"] == 300 * 5.0
    fr = [m for m in r["ajoutes"] if m["type"] == "frais"]
    assert len(fr) == 1 and fr[0]["date"] == "2026-12-31" and fr[0]["montant"] > 0
    assert "fin de trimestre" in fr[0]["hypothese"]


def test_division_du_panel_titres_et_ordre_ressaisi(tmp_path):
    raw = [1000.0] * 5 + [100.0] * 15
    act = [{"date": JOURS[5], "symbol": "AAA", "kind": "split", "ratio": 10.0, "confidence": "haute"}]
    p = J.panel_simple(JOURS, {"AAA": [100.0] * 20}, raw={"AAA": raw}, actions=act, volume=1.0)
    c = _carnet(tmp_path)
    c.ajouter({"type": "execution", "date": JOURS[0], "symbole": "AAA", "sens": "achat", "titres": 64, "prix": 1000,
               "frais": {}, "source": "papier"})
    o = _ordre(c, "AAA", "achat", 3, 1010, 1000, d=JOURS[3])  # volume trop faible : rien n'est servi avant
    PA.executer(c, p, JOURS[6])
    assert c.positions()["AAA"]["titres"] == 64 * 10
    res = [m for m in c.mouvements(types=("ordre",)) if m.get("ressaisie_de") == o["n"]]
    # limite 1 010 ÷ 10 = 101, ramenée au pas de 5 FCFA (au-dessus de 100) : 100
    assert len(res) == 1 and res[0]["titres"] == 30 and res[0]["limite"] == 100.0


def test_refus_S1_et_aucune_vente_creee(tmp_path):
    p = J.panel_simple(JOURS, {"AAA": [100.0] * 20})
    c = _carnet(tmp_path)
    with pytest.raises(S.DateDeS1):
        PA.executer(c, p, "2022-11-16")
    c.ajouter({"type": "execution", "date": JOURS[0], "symbole": "AAA", "sens": "achat", "titres": 10, "prix": 100,
               "frais": {}, "source": "papier"})
    r = PA.executer(c, p, JOURS[-1])
    assert not any(m["type"] == "execution" and m["sens"] == "vente" for m in r["ajoutes"])
    assert not any(m["type"] == "ordre" for m in r["ajoutes"])
    with pytest.raises(ValueError):
        PA.executer(c, p, JOURS[-1], mode="au mieux")


def test_controle_p8_publie_les_ecarts():
    a = [{"vendredi": "2026-12-04", "valeur": 10_000_000.0, "titres_servis": 120},
         {"vendredi": "2026-12-11", "valeur": 10_050_000.0, "titres_servis": 0}]
    assert PA.controle_p8(a, a)["conforme"]
    b = [dict(a[0]), dict(a[1], valeur=10_049_000.0)]
    r = PA.controle_p8(b, a)
    assert not r["conforme"] and r["ecarts"] == [{"vendredi": "2026-12-11", "ecart_valeur_fcfa": -1000.0,
                                                  "ecart_titres_servis": 0}]
    assert "réserve" in r["mention"] and PA.controle_p8([], a)["semaines_comparees"] == 0

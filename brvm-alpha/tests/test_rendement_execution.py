"""Options d'exécution du §F13 (cahier ``docs/RENDEMENT_NET.md``) branchées dans ``recommend`` et ``_build_plan`` :
toutes éteintes par défaut ; chacune est un écart à la règle testée, mentionné sur la sortie, sauf la mémoire annuelle
``--suivi`` (la règle testée, sans écart). Panel de synthèse (dates de S0 seulement), aucune donnée réelle.

Performance passée ≠ garantie. Aucun gain n'est garanti.
"""

from __future__ import annotations

import warnings

import pandas as pd
import pytest

import rendement_jeux as J
from brvm_alpha.portfolio import recommend as R
from brvm_alpha.rendement import raccord as RX
from brvm_alpha.strategy import BrvmAlpha

K = 10_000_000


@pytest.fixture(scope="module")
def jeu(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("execution")
    P = J.panel_synthese()
    reg = J.registre_vide(tmp / "trials.parquet")
    base = dict(panels=P, validation_dir=tmp / "absent", registry_path=reg, notes_store=False, n_boot=200, seed=0,
                index_evaluation=False, comparison=False, explanations=False, rendement=False)
    return P, base


def _reco(t, capital, base, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return R.recommend(t, capital, **{**base, **kw})


def _ordres(o):
    return [(r.symbole, r.sens, int(r.quantite)) for r in o.lignes.itertuples(index=False) if r.sens != "aucun"]


def _cibles(o):
    return {r.symbole: int(r.cibles) for r in o.lignes.itertuples(index=False) if r.cibles > 0}


def _js(o):
    d = o.to_dict()
    return repr({k: d[k] for k in ("lignes", "couts", "tranches", "dividendes", "distribution", "stress")})


def _janvier(P):
    idx = P["close"].index
    return idx[idx.year == 2024][0]


def test_sans_option_aucun_changement(jeu):
    P, base = jeu
    assert RX.options_execution(memoire=None, apport=None, completer=False, reinvestir=False, continuite=False,
                                 arrondi="bas", sessions=None, pdir=None) == ({}, [])
    t = P["close"].index[-1]
    o = _reco(t, K, base)
    o2 = _reco(t, K, base, arrondi="bas", completer=False, reinvestir=False, continuite=False, memoire=None)
    assert _js(o) == _js(o2)
    assert not any("règle testée :" in a or "Essai sur papier" in a for a in o.avertissements)
    with pytest.raises(ValueError, match="arrondi inconnu"):
        _reco(t, K, base, arrondi="haut")


# --------------------------------------------------------------------- (a) mémoire annuelle --suivi


def test_memoire_annuelle_rend_la_decision_du_moteur_sans_ordre(jeu):
    P, base = jeu
    jan = _janvier(P)
    idx = P["close"].index
    mai = idx[(idx.year == 2024) & (idx.month == 5)][10]
    oj = _reco(jan, K, base)
    held = _cibles(oj)
    cash = K - sum(q * float(P["close"].loc[jan, s]) for s, q in held.items()) - oj.couts["achats_couts"]
    # le moteur : le même modèle décide en janvier (remise à niveau), puis en mai avec les positions
    m = BrvmAlpha(variant="REF", capital=K, notes=None)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.decide(jan, P, None)
        c = P["close"].loc[mai]
        nav = sum(q * float(c[s]) for s, q in held.items()) + cash
        hw = pd.Series({s: q * float(c[s]) / nav for s, q in held.items()})
        dm = m.decide(mai, P, hw)
    assert (dm.diagnostics.get("index") or {}).get("action") == "conservation"
    mem = {"titres": held, "liquidites": cash, "memoire_ref": {"annee": 2024, "date": str(jan.date())}, "non_servis": {}}
    om = _reco(mai, nav, base, memoire=mem)
    forcees = set(((dm.diagnostics.get("index") or {}).get("forced_exits") or {}))
    assert {s for s, sens, _q in _ordres(om)} <= forcees  # aucun ordre hors sorties forcées
    wm = dm.weights.astype(float).fillna(0.0)
    wr = om.lignes.set_index("symbole")["poids_cible"].reindex(wm.index).fillna(0.0)
    assert float((wr - wm).abs().max()) < 1e-12  # mêmes poids que le moteur ce jour-là
    assert om.valeur_portefeuille == pytest.approx(nav) and om.liquidites_initiales == pytest.approx(cash)
    assert not any("règle testée :" in a for a in om.avertissements)  # la mémoire n'est pas un écart


# --------------------------------------------------------------------- (c) arrondi « plus forts restes »


def test_arrondi_plus_forts_restes(jeu):
    P, base = jeu
    t = P["close"].index[-1]
    od = _reco(t, K, base)
    with pytest.raises(ValueError, match="refusé : la grille du courtier est supposée"):
        _reco(t, K, base, arrondi="restes")
    oa = _reco(t, K, base, arrondi="restes", forcer=True)
    qd, qa = _cibles(od), _cibles(oa)
    assert set(qa) == set(qd)
    assert all(qd[s] <= qa[s] <= qd[s] + 1 for s in qd) and sum(qa.values()) > sum(qd.values())
    assert oa.couts["investi_apres"] > od.couts["investi_apres"]
    assert oa.couts["investi_apres"] <= oa.couts["cible_investie"]
    assert oa.couts["achats_pire_cas"] <= oa.liquidites_initiales
    assert not oa.execution.get("reductions")
    assert any(a.startswith("Écart à la règle testée : arrondi « plus forts restes » (E-A).") for a in oa.avertissements)
    assert any("plus forts restes" in m for m in oa.messages_modele)


# --------------------------------------------------------------------- (b) apport, compléter


def test_apport_aucune_vente_et_refus_sans_liquidites_reelles(jeu):
    P, base = jeu
    t = P["close"].index[-1]
    full = _cibles(_reco(t, K, base))
    c = P["close"].loc[t]
    held = {s: (2 * q) // 3 for s, q in full.items()}
    cash = K - sum(q * float(c[s]) for s, q in held.items()) - 60_000
    with pytest.raises(ValueError, match="liquidités réelles nécessaires"):
        _reco(t, K, base, holdings=held, apport=3_000_000)
    with pytest.raises(ValueError, match="doit comprendre l'apport"):
        _reco(t, K, base, holdings=held, cash=1_000_000, apport=3_000_000)
    o0 = _reco(t, K, base, holdings=held, cash=cash)
    oa = _reco(t, K, base, holdings=held, cash=cash, apport=3_000_000)
    assert not [x for x in _ordres(oa) if x[1] == "vente"]
    assert oa.couts["investi_apres"] >= o0.couts["investi_apres"]
    assert len([x for x in _ordres(oa) if x[1] == "achat"]) > len([x for x in _ordres(o0) if x[1] == "achat"])
    assert oa.couts["achats_pire_cas"] <= oa.liquidites_initiales  # contrôle du pire cas inchangé
    assert any("(E-B)" in a and a.startswith("Écart à la règle testée") for a in oa.avertissements)


def test_completer_achete_le_manque_de_l_ordre_d_origine(jeu):
    P, base = jeu
    t = P["close"].index[-1]
    od = _reco(t, K, base)
    full = _cibles(od)
    s1, s2, s3 = sorted(full)[:3]
    part = dict(full)
    part[s1] -= 3
    part[s2] -= 1
    del part[s3]  # ligne de l'ordre d'origine jamais servie
    c = P["close"].loc[t]
    cash = K - sum(q * float(c[s]) for s, q in part.items()) - od.couts["achats_couts"]
    mem = {"titres": part, "liquidites": cash, "memoire_ref": {"annee": 2024, "date": str(_janvier(P).date())},
           "non_servis": {s1: 3, s2: 1, s3: full[s3]}}
    assert _ordres(_reco(t, K, base, memoire=mem)) == []  # sans l'option : la règle garde les positions
    oc = _reco(t, K, base, memoire=mem, completer=True)
    assert sorted(_ordres(oc)) == sorted([(s1, "achat", 3), (s2, "achat", 1), (s3, "achat", full[s3])])
    assert oc.couts["achats_pire_cas"] <= oc.liquidites_initiales
    assert any("(E-B)" in a for a in oc.avertissements)


# --------------------------------------------------------------------- (d) réinvestissement de fin de mois


def test_reinvestir_une_ligne_en_fin_de_mois_seulement(jeu):
    P, base = jeu
    idx = P["close"].index
    jan = _janvier(P)
    full = _cibles(_reco(jan, K, base))
    fins = [d for d in idx if (d + pd.offsets.BDay(1)).month != d.month]
    t = [d for d in fins if d.year == 2024 and d.month == 7][0]
    c = P["close"].loc[t]
    nav = sum(q * float(c[s]) for s, q in full.items()) + 600_000
    mem = {"titres": full, "liquidites": 600_000, "memoire_ref": {"annee": 2024, "date": str(jan.date())},
           "non_servis": {}}
    assert _ordres(_reco(t, nav, base, memoire=mem)) == []
    orr = _reco(t, nav, base, memoire=mem, reinvestir=True)
    o = _ordres(orr)
    assert len(o) == 1 and o[0][1] == "achat"  # une seule ligne, aucune vente
    sym, _sens, q = o[0]
    # jamais au-dessus du poids cible du jour + 1 point
    m2 = BrvmAlpha(variant="REF", capital=nav, notes=None)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        w_ref = m2.decide(t, P, None).weights.astype(float).fillna(0.0)
    assert (full[sym] + q) * float(c[sym]) / nav <= float(w_ref[sym]) + 0.01 + 1e-12
    assert any(m.startswith("réinvestissement de fin de mois (E-D) : " + sym) for m in orr.messages_modele)
    assert any(a.startswith("Essai sur papier : réinvestissement de fin de mois (E-D).") for a in orr.avertissements)
    # hors de la dernière séance du mois : rien
    on = _reco(idx[-5], nav, base, memoire=mem, reinvestir=True)
    assert _ordres(on) == [] and any("n'est pas la dernière séance du mois" in m for m in on.messages_modele)
    # montant permis sous le seuil : rien (liquidités à peine au-dessus de la réserve de 2 %)
    nav2 = sum(q * float(c[s]) for s, q in full.items()) + 0.021 * nav
    op = _reco(t, nav2, base, memoire={**mem, "liquidites": 0.021 * nav}, reinvestir=True)
    assert _ordres(op) == [] and any("sous le seuil" in m for m in op.messages_modele)


# --------------------------------------------------------------------- (e) continuité des données


def test_continuite_garde_une_position_seulement_si_des_bulletins_manquent(jeu):
    P, base = jeu
    idx = P["close"].index
    t = idx[-1]
    jan = _janvier(P)
    full = _cibles(_reco(jan, K, base))
    S = sorted(full)[3]
    P2 = {k: (v.copy() if hasattr(v, "copy") else v) for k, v in P.items()}
    fen = idx[-110:]  # le titre ne s'échange plus : inéligible (U3) entre deux remises à niveau
    P2["volume"].loc[fen, S] = 0.0
    P2["value"].loc[fen, S] = 0.0
    P2["status"].loc[fen, S] = "not_traded"
    b2 = {**base, "panels": P2}
    c = P2["close"].loc[t]
    nav = sum(q * float(c[s]) for s, q in full.items()) + 98_000
    mem = {"titres": full, "liquidites": 98_000, "memoire_ref": {"annee": 2024, "date": str(jan.date())},
           "non_servis": {}}
    vente = (S, "vente", full[S])
    assert _ordres(_reco(t, nav, b2, memoire=mem)) == [vente]  # la règle testée vend (mémoire seule : pas E-C)
    sess = pd.DataFrame({"date": idx, "available": True})
    o_plein = _reco(t, nav, b2, memoire=mem, continuite=True, sessions=sess)
    assert _ordres(o_plein) == [vente]  # sans bulletin manquant : mêmes ordres qu'option éteinte
    trou = sess.copy()
    trou.loc[trou.index[-50], "available"] = False
    o_trou = _reco(t, nav, b2, memoire=mem, continuite=True, sessions=trou)
    assert _ordres(o_trou) == []
    note = o_trou.lignes.set_index("symbole").loc[S, "note"]
    assert "continuité des données (E-C)" in note and "position gardée, aucun achat" in note
    assert any(a.startswith("Essai sur papier : continuité des données (E-C).") for a in o_trou.avertissements)
    # un trou hors de la fenêtre de 126 séances ne change rien
    loin = sess.copy()
    loin.loc[loin.index[-200], "available"] = False
    assert _ordres(_reco(t, nav, b2, memoire=mem, continuite=True, sessions=loin)) == [vente]

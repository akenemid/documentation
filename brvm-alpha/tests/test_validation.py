"""Tests de la validation (spécification §8.1-8.3, §12.3 n° 8) : mesures hebdomadaires,
registre des essais, validation croisée purgée / CPCV et statut REJETÉ / CANDIDAT / PROMU.

Toutes les séries sont **synthétiques** (graine fixe) et datées hors de
l'échantillon vierge S1 : aucun calcul de performance n'est fait sur S1.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from brvm_alpha.backtest import metrics as mt
from brvm_alpha.backtest.walkforward import (
    N_TRIALS_START,
    STATUS_THRESHOLDS,
    STATUT_CANDIDAT,
    STATUT_DECLARE,
    STATUT_EXECUTE,
    STATUT_INDETERMINE,
    STATUT_PREENREGISTRE,
    STATUT_PROMU,
    STATUT_REJETE,
    TrialRegistry,
    cpcv,
    declared_s0_trials,
    evaluate_status,
    preregistered_s1_variants,
    purged_kfold,
    status_thresholds,
)

#: Semaines synthétiques (W-FRI), postérieures à S1.
WEEKS = pd.date_range("2030-01-04", periods=312, freq="W-FRI")
SUBS = [(WEEKS[0], WEEKS[155]), (WEEKS[156], WEEKS[-1])]


def _series(values: np.ndarray, index: pd.DatetimeIndex = WEEKS) -> pd.Series:
    return pd.Series(np.asarray(values, dtype=float), index=index[: len(values)])


# ---------------------------------------------------------------------------
# Échantillons et rendements hebdomadaires
# ---------------------------------------------------------------------------


def test_samples_and_virgin_guard() -> None:
    assert mt.S1 == ("2017-01-02", "2022-11-16") and mt.S0 == ("2022-11-17", "2026-11-20")
    assert mt.overlaps_s1("2022-01-01", "2023-01-01") and mt.overlaps_s1(None, "2017-01-02")
    assert not mt.overlaps_s1("2022-11-17", "2026-11-20")
    assert mt.N_BOOT == 5000 and mt.WEEKLY_MEAN_BLOCK == 8 and mt.WEEKLY_FREQ == "W-FRI"


def test_weekly_returns_compound_w_fri_and_exclusions() -> None:
    days = pd.bdate_range("2031-03-03", periods=15)  # lundi → vendredi, 3 semaines
    days = days.drop(pd.Timestamp("2031-03-14"))  # vendredi férié
    r = pd.Series(0.01, index=days)
    r.iloc[2] = np.nan  # séance sans rendement : ignorée
    w = mt.weekly_returns(r)
    assert list(w.index) == list(pd.DatetimeIndex(["2031-03-07", "2031-03-14", "2031-03-21"]))
    assert (w.index.dayofweek == 4).all()
    assert w.iloc[0] == pytest.approx(1.01**4 - 1.0)
    assert w.iloc[1] == pytest.approx(1.01**4 - 1.0)  # semaine sans le vendredi férié
    assert w.iloc[2] == pytest.approx(1.01**5 - 1.0)
    ex = mt.weekly_returns(r, exclude_windows=[("2031-03-12", "2031-03-12")])
    assert list(ex.index) == [pd.Timestamp("2031-03-07"), pd.Timestamp("2031-03-21")]
    frame = mt.weekly_returns(pd.DataFrame({"a": r, "b": 2 * r}))
    assert frame.shape == (3, 2)
    assert mt.EXCLUDE_STATS_WINDOWS == (("2021-05-06", "2021-06-25"),)


def test_active_returns_and_annualized_measures() -> None:
    b = _series(np.full(104, 0.002))
    s = _series(np.full(104, 0.003))
    a = mt.active_returns(s, b)
    assert np.allclose(a, 0.001)
    assert mt.annualized_return(s) == pytest.approx(1.003**52 - 1.0)
    assert mt.annualized_active_return(s, b) == pytest.approx(1.003**52 - 1.002**52)
    path = _series([0.10, -0.20, 0.05, 0.0])
    assert mt.max_drawdown(path) == pytest.approx(-0.20)
    assert mt.max_drawdown(_series([-0.05, 0.02])) == pytest.approx(-0.05)  # capital initial = premier plus haut
    rel = mt.relative_drawdown(_series([0.0, -0.10, 0.0]), _series([0.0, 0.10, 0.0]))
    assert rel == pytest.approx(0.9 / 1.1 - 1.0)


# ---------------------------------------------------------------------------
# Trois Sharpe, GLM, PSR / DSR
# ---------------------------------------------------------------------------


def test_glm_smoothing_recovers_theta_and_lowers_sharpe() -> None:
    rng = np.random.default_rng(42)
    e = rng.normal(0.004, 0.02, 2002)
    theta = np.array([0.5, 0.3, 0.2])
    smoothed = theta[0] * e[2:] + theta[1] * e[1:-1] + theta[2] * e[:-2]
    idx = pd.date_range("2030-01-04", periods=smoothed.size, freq="W-FRI")
    x = pd.Series(smoothed, index=idx)
    sm = mt.glm_smoothing(x, k=2)
    assert sm.theta.sum() == pytest.approx(1.0)
    assert np.allclose(sm.theta, theta, atol=0.06)
    assert sm.xi == pytest.approx(float(sm.theta @ sm.theta))
    trip = mt.sharpe_triplet(x)
    assert trip["glm"] == pytest.approx(trip["naive"] * math.sqrt(sm.xi), rel=1e-6)
    assert trip["glm"] < trip["naive"] and trip["lo"] < trip["naive"]
    assert trip["lo_q"] == 4
    # rendements i.i.d. : peu de lissage, les trois Sharpe sont proches
    iid = pd.Series(rng.normal(0.004, 0.02, 2000), index=pd.date_range("2030-01-04", periods=2000, freq="W-FRI"))
    t2 = mt.sharpe_triplet(iid)
    assert t2["glm_theta"][0] > 0.85
    assert t2["lo"] == pytest.approx(t2["naive"], rel=0.15) and t2["glm"] == pytest.approx(t2["naive"], rel=0.15)
    assert not t2["divergence"]
    # méthode CSS : même ordre de grandeur
    assert np.allclose(mt.glm_smoothing(x, method="css").theta, theta, atol=0.08)


def test_sharpe_triplet_flags_lo_glm_divergence() -> None:
    rng = np.random.default_rng(7)
    # autocorrélation négative à l'ordre 1 : Lo augmente le Sharpe, GLM (θ ≥ 0) ne peut pas
    e = rng.normal(0.003, 0.02, 801)
    x = pd.Series(e[1:] - 0.6 * e[:-1], index=pd.date_range("2030-01-04", periods=800, freq="W-FRI"))
    trip = mt.sharpe_triplet(x)
    assert trip["lo_glm_gap"] == pytest.approx(abs(trip["lo"] - trip["glm"]) / abs(trip["lo"]))
    assert trip["divergence"] == (trip["lo_glm_gap"] > 0.25)


def test_psr_and_dsr_with_registry_n() -> None:
    rng = np.random.default_rng(1)
    a = _series(rng.normal(0.002, 0.01, 300))
    p = mt.psr(a)
    assert 0.5 < p <= 1.0
    d1 = mt.dsr(a, n_trials=1, sr_variance=0.002)
    d63 = mt.dsr(a, n_trials=63, sr_variance=0.002)
    assert d1 == pytest.approx(p)  # N = 1 : pas de dégonflement
    assert d63 < d1
    assert math.isnan(mt.dsr(a, n_trials=63, sr_variance=math.nan))


def test_dsr_reads_n_from_registry(tmp_path) -> None:
    rng = np.random.default_rng(2)
    a = _series(rng.normal(0.002, 0.01, 300))
    reg = TrialRegistry.initialize(tmp_path / "trials.parquet")
    assert math.isnan(mt.dsr(a, reg))  # aucun essai exécuté : variance des Sharpe inconnue
    assert mt.dsr(a, reg, sr_variance=0.002) == pytest.approx(mt.dsr(a, 63, 0.002))


# ---------------------------------------------------------------------------
# Bootstrap stationnaire et CVaR
# ---------------------------------------------------------------------------


def test_bootstrap_ci_defaults_and_reproducibility() -> None:
    rng = np.random.default_rng(3)
    a = _series(rng.normal(0.002, 0.01, 300))
    ci = mt.bootstrap_ci(a)
    assert ci["n_boot"] == 5000 and ci["mean_block"] == 8.0 and ci["n_valid"] == 5000
    assert ci["lower"] < ci["point"] < ci["upper"]
    assert ci["point"] == pytest.approx(mt.information_ratio(a))
    assert mt.bootstrap_ci(a, seed=0) == ci  # graine fixe
    m = mt.bootstrap_ci(a, "mean", n_boot=500)
    assert m["point"] == pytest.approx(float(a.mean()) * 52)


def test_cvar_exact_and_ratio_by_joint_bootstrap() -> None:
    x = np.array([-0.10, -0.08, -0.05, 0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06] * 2)
    # 20 scénarios, 5 % ⇒ k = 1 pire scénario
    assert mt.cvar(x, 0.95) == pytest.approx(0.10)
    assert mt.cvar(x, 0.80) == pytest.approx(np.mean([0.10, 0.10, 0.08, 0.08]))
    rng = np.random.default_rng(5)
    b = _series(rng.normal(0.002, 0.02, 300))
    same = mt.cvar_ratio(b, b, n_boot=500)
    assert same["ratio"] == pytest.approx(1.0) and same["ratio_median"] == pytest.approx(1.0)
    double = mt.cvar_ratio(2.0 * b, b, n_boot=500)
    assert double["ratio"] == pytest.approx(2.0)  # tirage conjoint : CVaR(2x) = 2·CVaR(x)
    cb = mt.cvar_bootstrap(b)
    assert cb["n_boot"] == 5000 and cb["lower"] <= cb["cvar"] <= cb["upper"]


def test_family_pbo_uses_lo_sharpe_on_ten_weekly_blocks() -> None:
    rng = np.random.default_rng(11)
    mat = pd.DataFrame(rng.normal(0.0, 0.01, size=(300, 8)), index=WEEKS[:300], columns=list("ABCDEFGH"))
    res = mt.family_pbo(mat)
    assert res["n_splits"] == 10 and res["n_combinations"] == math.comb(10, 5)
    assert res["metric"] == "sharpe_lo_q4"
    assert 0.0 <= res["pbo"] <= 1.0
    # une variante réellement supérieure : PBO faible
    mat["A"] += 0.01
    assert mt.family_pbo(mat)["pbo"] < 0.1


# ---------------------------------------------------------------------------
# K-fold purgé et CPCV
# ---------------------------------------------------------------------------


def test_purged_kfold_purge_and_embargo() -> None:
    cal = pd.bdate_range("2030-01-01", periods=1000)
    splits = purged_kfold(cal, n_splits=10, purge=21, embargo=21)
    assert len(splits) == 10
    mid = splits[4]
    assert len(mid.test) == 100 and len(mid.purged) == 21 and len(mid.embargoed) == 21
    assert len(mid.train) == 1000 - 100 - 42
    lo = cal.get_loc(mid.test[0])
    hi = cal.get_loc(mid.test[-1])
    assert list(mid.purged) == list(cal[lo - 21 : lo])
    assert list(mid.embargoed) == list(cal[hi + 1 : hi + 22])
    for s in splits:
        assert not set(s.train) & set(s.test)
        assert not set(s.train) & (set(s.purged) | set(s.embargoed))
    assert len(splits[0].purged) == 0 and len(splits[-1].embargoed) == 0


def test_cpcv_ten_groups_k2_paths() -> None:
    cal = pd.bdate_range("2030-01-01", periods=1200)
    cv = cpcv(cal)
    assert cv.n_splits == 45 and cv.n_paths == 9
    assert cv.purge == 21 and cv.embargo == 21
    for g in range(10):
        assert sum(g in s.test_groups for s in cv.splits) == 9
    for path in cv.paths:
        assert sorted(path) == list(range(10))
        covered = pd.DatetimeIndex(np.concatenate([cv.groups[g].to_numpy() for g in range(10)]))
        assert covered.equals(cal)
        for g, s in path.items():
            assert g in cv.splits[s].test_groups
    # groupes 0 et 1 adjacents : un seul bloc de test, embargo après le groupe 1 seulement
    s01 = next(s for s in cv.splits if s.test_groups == (0, 1))
    assert len(s01.purged) == 0 and len(s01.embargoed) == 21
    s03 = next(s for s in cv.splits if s.test_groups == (0, 3))
    assert len(s03.purged) == 21 and len(s03.embargoed) == 42
    # assemblage des chemins : sortie = identifiant du découpage
    outputs = {s.split: pd.Series(float(s.split), index=s.test) for s in cv.splits}
    paths = cv.path_returns(outputs)
    assert paths.shape == (1200, 9) and paths.notna().all().all()
    g5 = cv.groups[5]
    assert (paths.loc[g5, "chemin_1"] == cv.paths[0][5]).all()


# ---------------------------------------------------------------------------
# Registre des essais (§8.2, §12.3 n° 8)
# ---------------------------------------------------------------------------


def test_registry_starts_with_63_trials(tmp_path) -> None:
    s0 = declared_s0_trials()
    s1 = preregistered_s1_variants()
    assert len(s0) == 55 and len(s1) == 8
    assert sum(r["famille"] == "R04 grille momentum 36" for r in s0) == 36
    assert sum(r["famille"] == "R03 fenêtres de momentum" for r in s0) == 6
    assert sum(r["famille"] == "R03 configurations acheteuses" for r in s0) == 13
    path = tmp_path / "reports" / "trials.parquet"
    reg = TrialRegistry.initialize(path)
    assert path.exists()
    assert reg.n_trials() == N_TRIALS_START == 63  # §12.3 n° 8 : au moins 63 essais avant S1
    assert reg.n_trials("S0") == 55 and reg.n_trials("S1") == 8
    f = reg.frame
    assert (f.loc[f["echantillon"] == "S0", "statut"] == STATUT_DECLARE).all()
    assert (f.loc[f["echantillon"] == "S1", "statut"] == STATUT_PREENREGISTRE).all()
    assert list(f.columns[:7]) == ["id", "variante", "famille", "parametres", "echantillon", "statut", "date_execution"]
    a = json.loads(f.loc[f["id"] == "S1-A", "parametres"].iloc[0])
    assert a["poids"] == {"ep": 0.15, "dy": 0.20, "mom6_1": 0.35, "lowvol": 0.20, "quality_proxy": 0.10}
    # relecture et ré-initialisation idempotente
    again = TrialRegistry.initialize(path)
    assert again.n_trials() == 63
    assert TrialRegistry.load(path).n_trials() == 63
    assert reg.n_trials(include_declared=False) == 0
    assert math.isnan(reg.sharpe_variance()) and not reg.is_complete()


def test_registry_record_freezes_params_and_single_s1_test(tmp_path) -> None:
    reg = TrialRegistry.initialize(tmp_path / "trials.parquet")
    rng = np.random.default_rng(0)
    params_a = json.loads(reg.frame.loc[reg.frame["id"] == "S1-A", "parametres"].iloc[0])
    with pytest.raises(ValueError, match="FIGÉS"):
        reg.record("A", {**params_a, "frequence": "hebdomadaire"}, "S1", _series(rng.normal(0, 0.01, 10)))
    for code in "ABCDEFGH":
        p = json.loads(reg.frame.loc[reg.frame["id"] == f"S1-{code}", "parametres"].iloc[0])
        tid = reg.record(code, p, "S1", _series(rng.normal(0.001, 0.01, 100)), {"ir": 0.1}, save=True)
        assert tid == f"S1-{code}"
    assert reg.n_trials() == 63  # les variantes pré-enregistrées sont complétées, pas ajoutées
    assert reg.n_trials(include_declared=False) == 8
    with pytest.raises(RuntimeError, match="UN test"):
        reg.record("A", params_a, "S1", _series(rng.normal(0, 0.01, 10)))
    assert reg.is_complete()
    mat = reg.returns_matrix("S1", variants=list("ABCDEFGH"))
    assert mat.shape == (100, 8)
    srs = [float(mat[c].mean() / mat[c].std(ddof=1)) for c in mat]
    assert reg.sharpe_variance("S1") == pytest.approx(float(np.var(srs, ddof=1)))
    # un nouvel essai (S0, diagnostic) augmente N
    tid = reg.record("A-hebdo", {"frequence": "hebdomadaire"}, "S0", _series(rng.normal(0, 0.01, 50)))
    assert reg.n_trials() == 64 and tid.startswith("S0-A-hebdo")
    back = TrialRegistry.load(tmp_path / "trials.parquet")
    assert back.n_trials() == 63  # le dernier essai n'a pas été sauvegardé
    w = back.weekly_returns("S1-C")
    assert len(w) == 100 and (back.frame.loc[back.frame["id"] == "S1-C", "statut"] == STATUT_EXECUTE).all()
    with pytest.raises(ValueError, match="obligatoires"):
        reg.record("Z", {}, "S0", pd.Series(dtype=float))


# ---------------------------------------------------------------------------
# Statut (§8.3)
# ---------------------------------------------------------------------------


def _bench(seed: int = 100, n: int = 312) -> pd.Series:
    rng = np.random.default_rng(seed)
    return _series(rng.normal(0.002, 0.015, n))


def _good_active(seed: int = 200, n: int = 312, mu: float = 0.003, sd: float = 0.006) -> pd.Series:
    rng = np.random.default_rng(seed)
    return _series(rng.normal(mu, sd, n))


def test_status_rejected_on_negative_active_return() -> None:
    b = _bench()
    a = _good_active(mu=-0.001, sd=0.004)
    rep = evaluate_status(a, a - 0.0001, b, SUBS, turnover=0.10, pbo=0.3, cvar_ratio=1.0, n_boot=500)
    assert rep.statut == STATUT_REJETE
    assert rep.critere("rejet", "R1")["verifie"] is True
    assert rep.critere("candidat", "C1")["verifie"] is False
    assert rep.bandeau.endswith("Statut : REJETÉ") and "Aucun gain n'est garanti" in rep.bandeau
    assert any("indice discipliné" in x for x in rep.avertissements)


def test_each_rejection_criterion() -> None:
    b = _bench()
    zeros = np.zeros(312)
    # R2 : actif positif au coût central mais < −1 %/an au coût de stress
    a = _good_active(mu=0.0004, sd=0.002)
    rep = evaluate_status(a, a - 0.0008, b, SUBS, turnover=0.1, pbo=0.3, cvar_ratio=1.0, n_boot=200)
    assert rep.critere("rejet", "R1")["verifie"] is False
    assert rep.critere("rejet", "R2")["verifie"] is True and rep.statut == STATUT_REJETE
    # R3 : IR < −0,5 sur la première sous-période seulement
    rng = np.random.default_rng(9)
    v = np.r_[rng.normal(-0.0005, 0.002, 156), rng.normal(0.003, 0.002, 156)]
    rep = evaluate_status(_series(v), _series(v), b, SUBS, turnover=0.1, pbo=0.3, cvar_ratio=1.0, n_boot=200)
    ir1, ir2 = rep.mesures["ir_sous_periodes"]
    assert ir1 < -0.5 < ir2
    assert rep.critere("rejet", "R1")["verifie"] is False and rep.critere("rejet", "R3")["verifie"] is True
    # R4 : drawdown relatif < −20 % puis rattrapage
    v = np.r_[np.full(50, -0.005), np.full(262, 0.0035)]
    rep = evaluate_status(_series(v), _series(v), _series(zeros), SUBS, turnover=0.1, pbo=0.3, cvar_ratio=1.0,
                          n_boot=200)
    assert rep.mesures["drawdown_relatif"] == pytest.approx(0.995**50 - 1.0)
    assert rep.critere("rejet", "R4")["verifie"] is True and rep.statut == STATUT_REJETE
    # R5 : drawdown absolu pire que celui du TR de plus de 10 points
    bb = zeros.copy()
    bb[100] = -0.10
    v = np.full(312, 0.001)
    v[100] = -0.16
    rep = evaluate_status(_series(v), _series(v), _series(bb), SUBS, turnover=0.1, pbo=0.3, cvar_ratio=1.0,
                          n_boot=200)
    assert rep.critere("rejet", "R4")["verifie"] is False
    assert rep.mesures["drawdown_tr"] == pytest.approx(-0.10)
    assert rep.critere("rejet", "R5")["verifie"] is True and rep.statut == STATUT_REJETE


def test_status_candidate_and_boundaries() -> None:
    b = _bench()
    a = _good_active()
    common = {"n_boot": 500, "pbo_slope": 0.0, "n_trials": 63, "sr_variance": 1e-4}
    rep = evaluate_status(a, a - 0.00005, b, SUBS, turnover=0.15, pbo=0.4, cvar_ratio=1.2, **common)
    assert rep.statut == STATUT_CANDIDAT
    assert rep.groupe("candidat")["verifie"].tolist() == [True] * 7
    assert rep.groupe("rejet")["verifie"].tolist() == [False] * 5
    assert any("PROMU est impossible" in x for x in rep.avertissements)
    # bornes exactes : 20 %/mois de rotation, PBO 0,5 et CVaR 1,25 sont admis
    rep = evaluate_status(a, a, b, SUBS, turnover=0.20, pbo=0.5, cvar_ratio=1.25, **common)
    assert rep.statut == STATUT_CANDIDAT
    # au-delà : ni rejeté ni candidat
    for kw in ({"turnover": 0.2001, "pbo": 0.4, "cvar_ratio": 1.0},
               {"turnover": 0.1, "pbo": 0.51, "cvar_ratio": 1.0},
               {"turnover": 0.1, "pbo": 0.4, "cvar_ratio": 1.26},
               {"turnover": None, "pbo": 0.4, "cvar_ratio": 1.0}):
        rep = evaluate_status(a, a, b, SUBS, **kw, **common)
        assert rep.statut == STATUT_INDETERMINE
    # stress à −0,75 %/an (entre −1 % et −0,5 %) : ni rejet (R2) ni candidat (C1)
    from scipy.optimize import brentq

    zeros = _series(np.zeros(312))
    delta = brentq(lambda d: mt.annualized_active_return(a - d, zeros) + 0.0075, 0.0, 0.01)
    rep = evaluate_status(a, a - delta, zeros, SUBS, turnover=0.1, pbo=0.4, cvar_ratio=1.0, **common)
    assert rep.mesures["actif_net_stress_an"] == pytest.approx(-0.0075)
    assert rep.critere("rejet", "R2")["verifie"] is False and rep.critere("candidat", "C1")["verifie"] is False
    assert rep.statut == STATUT_INDETERMINE
    # IR < 0,20 : pas candidat
    weak = _good_active(seed=5, mu=0.0003, sd=0.02)
    rep = evaluate_status(weak, weak, b, SUBS, turnover=0.1, pbo=0.4, cvar_ratio=1.0, **common)
    assert rep.critere("candidat", "C2")["valeur"] < 0.2
    assert rep.statut in (STATUT_INDETERMINE, STATUT_REJETE)


def test_status_promoted_requires_g1_g9_on_s1_and_12_months_of_s2() -> None:
    b = _bench()
    a = _good_active(mu=0.004, sd=0.006)
    rng = np.random.default_rng(77)
    ic = pd.Series(rng.normal(0.05, 0.05, 40), index=pd.date_range("2030-01-31", periods=40, freq="ME"))
    s2_index = pd.date_range("2036-01-04", periods=60, freq="W-FRI")
    s2 = pd.Series(rng.normal(0.004, 0.006, 60), index=s2_index)
    kw = {
        "turnover": 0.12,
        "pbo": 0.10,
        "cvar_ratio": 1.0,
        "pbo_slope": 0.1,
        "n_trials": 63,
        "sr_variance": 1e-4,
        "registry_complete": True,
        "ic_monthly": ic,
        "n_boot": 500,
    }
    rep = evaluate_status(a, a - 0.0001, b, SUBS, s2_active_weekly_returns=s2, **kw)
    assert rep.groupe("promotion_S1")["verifie"].tolist() == [True] * 9
    assert rep.groupe("promotion_S2")["verifie"].tolist() == [True] * 9
    assert rep.statut == STATUT_PROMU
    assert any("ERREUR" in x for x in rep.avertissements)  # IR > 1 : suspect par principe
    # moins de 52 semaines de suivi réel : pas de promotion
    rep = evaluate_status(a, a - 0.0001, b, SUBS, s2_active_weekly_returns=s2.iloc[:51], **kw)
    assert rep.statut == STATUT_CANDIDAT
    # un seul filtre G rouge suffit (G4 : PBO > 0,25 ; G1 : registre incomplet ; G7 : IC trop court)
    assert evaluate_status(a, a, b, SUBS, s2_active_weekly_returns=s2, **{**kw, "pbo": 0.3}).statut == STATUT_CANDIDAT
    assert (
        evaluate_status(a, a, b, SUBS, s2_active_weekly_returns=s2, **{**kw, "registry_complete": False}).statut
        == STATUT_CANDIDAT
    )
    short_ic = evaluate_status(a, a, b, SUBS, s2_active_weekly_returns=s2, **{**kw, "ic_monthly": ic.iloc[:30]})
    assert short_ic.critere("promotion_S1", "G7")["verifie"] is False and short_ic.statut == STATUT_CANDIDAT
    # pente de dégradation ≤ −0,5 : G4 rouge
    slope = evaluate_status(a, a, b, SUBS, s2_active_weekly_returns=s2, **{**kw, "pbo_slope": -0.6})
    assert slope.critere("promotion_S1", "G4")["verifie"] is False
    # sans variance des Sharpe entre essais : DSR non évaluable, pas de promotion
    no_var = evaluate_status(a, a, b, SUBS, s2_active_weekly_returns=s2, **{**kw, "sr_variance": None})
    assert no_var.critere("promotion_S1", "G3")["verifie"] is None and no_var.statut == STATUT_CANDIDAT


def test_status_uses_registry_for_n_and_g1(tmp_path) -> None:
    reg = TrialRegistry.initialize(tmp_path / "trials.parquet")
    b = _bench()
    a = _good_active()
    rep = evaluate_status(a, a, b, SUBS, turnover=0.1, pbo=0.2, cvar_ratio=1.0, registry=reg, n_boot=200)
    assert rep.mesures["promotion_S1_n_trials"] == 63
    assert rep.critere("promotion_S1", "G1")["verifie"] is False  # variantes S1 non exécutées


def test_status_thresholds_match_strategy_yaml() -> None:
    assert STATUS_THRESHOLDS["candidate_ir_ge"] == 0.20 and STATUS_THRESHOLDS["reject_rel_dd_lt"] == -0.20
    try:
        from brvm_alpha import settings

        cfg = settings.load_strategy_config()
    except Exception:  # pragma: no cover - fichier de paramètres d'un autre agent
        pytest.skip("configs/strategy_v1.yaml indisponible")
    assert status_thresholds(cfg) == STATUS_THRESHOLDS
    custom = status_thresholds({"candidate_ir_ge": 0.3})
    assert custom["candidate_ir_ge"] == 0.3
    with pytest.raises(KeyError):
        status_thresholds({"seuil_inconnu": 1.0})

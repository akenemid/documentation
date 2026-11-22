"""Tests de brvm_alpha.portfolio.risk et brvm_alpha.portfolio.construct.

Tous les tests sont déterministes (générateurs numpy à graine fixe).
"""

from __future__ import annotations

import itertools
import warnings
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import optimize
from scipy.cluster import hierarchy as sch
from scipy.spatial.distance import squareform
from sklearn.covariance import LedoitWolf

from brvm_alpha.config import Constraints
from brvm_alpha.portfolio.construct import (
    apply_no_trade_band,
    average_daily_value,
    build_portfolio,
    cap_turnover,
    constraint_violations,
    fractional_kelly_scale,
    grinold_alpha,
    liquidity_caps,
    to_lots,
)
from brvm_alpha.portfolio.risk import (
    aggregate_returns,
    cov_to_corr,
    hrp_weights,
    inverse_vol_weights,
    ledoit_wolf_cov,
    nearest_correlation,
    nearest_psd_cov,
    portfolio_volatility,
    risk_contributions,
)

ROOT = Path(__file__).resolve().parents[1]
TOL = 1e-8

#: Contraintes que ces tests supposaient avant le calibrage de ``config.py`` d'après la
#: spécification v1 (anciens défauts : poids max 15 %, 6 à 15 lignes, secteur 40 %,
#: pays 60 %, participation 20 %). Elles sont fixées explicitement pour que le
#: comportement testé ne change pas ; les défauts v1 sont testés dans
#: ``tests/test_portfolio_v1.py``.
LEGACY_CONSTRAINTS = Constraints(
    max_weight=0.15,
    min_weight=0.02,
    max_names=15,
    min_names=6,
    max_sector_weight=0.40,
    max_country_weight=0.60,
    max_adv_participation=0.20,
    max_days_to_liquidate=20.0,
)


# ---------------------------------------------------------------------------
# Données synthétiques
# ---------------------------------------------------------------------------


def _returns(seed: int, t: int = 250, p: int = 12, nan_frac: float = 0.0) -> pd.DataFrame:
    """Rendements à structure factorielle (1 facteur marché + 2 sectoriels)."""
    rng = np.random.default_rng(seed)
    mkt = rng.standard_normal((t, 1)) * 0.010
    sec = rng.standard_normal((t, 2)) * 0.008
    load = rng.uniform(0.5, 1.5, (1, p))
    sec_load = np.zeros((2, p))
    sec_load[0, : p // 2] = 1.0
    sec_load[1, p // 2 :] = 1.0
    idio = rng.standard_normal((t, p)) * rng.uniform(0.008, 0.025, p)
    x = mkt @ load + sec @ sec_load + idio
    df = pd.DataFrame(
        x,
        index=pd.bdate_range("2024-01-01", periods=t),
        columns=[f"T{i:02d}" for i in range(p)],
    )
    if nan_frac > 0:
        df = df.mask(rng.random(df.shape) < nan_frac)
    return df


def _problem(seed: int, n: int = 30, tight: bool = False):
    """Problème de construction aléatoire (alpha, cov annualisée, groupes, liquidité)."""
    rng = np.random.default_rng(seed)
    rets = _returns(seed, t=300, p=n)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cov = ledoit_wolf_cov(rets, annualize=True)
    names = cov.index
    alpha = pd.Series(rng.normal(0.05, 0.08, n), index=names)
    sectors = pd.Series(rng.choice(["FIN", "TEL", "CB", "IND", "SPU"], n, p=[0.5, 0.1, 0.2, 0.1, 0.1]), index=names)
    countries = pd.Series(rng.choice(["CI", "SN", "BF", "TG"], n, p=[0.6, 0.2, 0.1, 0.1]), index=names)
    hi = 0.05 if tight else 0.4
    liquidity = pd.Series(rng.uniform(0.0, hi, n), index=names)
    prev = pd.Series(0.0, index=names)
    held = rng.choice(n, 8, replace=False)
    prev.iloc[held] = rng.dirichlet(np.ones(8)) * 0.9
    return alpha, cov, liquidity, prev, sectors, countries


def _assert_feasible(w, cons, liquidity=None, sectors=None, countries=None, tol=TOL):
    viol = constraint_violations(w, cons, liquidity, sectors, countries)
    for key, val in viol.items():
        assert val <= tol, f"contrainte {key} violée de {val}"
    assert np.all(np.isfinite(w.to_numpy()))
    assert (w >= -tol).all()
    assert w.sum() <= 1.0 - cons.cash_buffer + tol
    assert abs(w.sum() - w.attrs["budget"]) <= 1e-7


# ---------------------------------------------------------------------------
# Implémentations de référence (transcriptions des codes publiés)
# ---------------------------------------------------------------------------


def _ref_covcor(x: np.ndarray) -> tuple[np.ndarray, float]:
    """Transcription de covCor.m (Ledoit & Wolf 2004, cible corrélation constante)."""
    t, n = x.shape
    x = x - x.mean(axis=0)
    sample = x.T @ x / t
    var = np.diag(sample).reshape(-1, 1)
    sqrtvar = np.sqrt(var)
    rbar = (np.sum(sample / (sqrtvar @ sqrtvar.T)) - n) / (n * (n - 1))
    prior = rbar * (sqrtvar @ sqrtvar.T)
    np.fill_diagonal(prior, var.ravel())
    y = x**2
    phi_mat = y.T @ y / t - sample**2
    phi = phi_mat.sum()
    term1 = (x**3).T @ x / t
    help_ = x.T @ x / t
    help_diag = np.diag(help_).reshape(-1, 1)
    term2 = (help_diag @ np.ones((1, n))) * sample
    term3 = help_ * (var @ np.ones((1, n)))
    term4 = (var @ np.ones((1, n))) * sample
    theta_mat = term1 - term2 - term3 + term4
    np.fill_diagonal(theta_mat, 0.0)
    rho = np.diag(phi_mat).sum() + rbar * np.sum(((1.0 / sqrtvar) @ sqrtvar.T) * theta_mat)
    gamma = np.linalg.norm(sample - prior, "fro") ** 2
    kappa = (phi - rho) / gamma
    shrink = max(0.0, min(1.0, kappa / t))
    return shrink * prior + (1 - shrink) * sample, shrink


def _ref_ivp(cov: pd.DataFrame) -> np.ndarray:
    ivp = 1.0 / np.diag(cov)
    return ivp / ivp.sum()


def _ref_cluster_var(cov: pd.DataFrame, items: list) -> float:
    cov_ = cov.loc[items, items]
    w_ = _ref_ivp(cov_).reshape(-1, 1)
    return float((w_.T @ cov_.to_numpy() @ w_)[0, 0])


def _ref_quasi_diag(link: np.ndarray) -> list[int]:
    """getQuasiDiag de López de Prado (2016), adapté à pandas 3 (concat)."""
    link = link.astype(int)
    sort_ix = pd.Series([link[-1, 0], link[-1, 1]])
    num_items = link[-1, 3]
    while sort_ix.max() >= num_items:
        sort_ix.index = range(0, sort_ix.shape[0] * 2, 2)
        df0 = sort_ix[sort_ix >= num_items]
        i = df0.index
        j = df0.to_numpy() - num_items
        sort_ix.loc[i] = link[j, 0]
        df0 = pd.Series(link[j, 1], index=i + 1)
        sort_ix = pd.concat([sort_ix, df0]).sort_index()
        sort_ix.index = range(sort_ix.shape[0])
    return sort_ix.tolist()


def _ref_rec_bipart(cov: pd.DataFrame, sort_ix: list) -> pd.Series:
    """getRecBipart de López de Prado (2016)."""
    w = pd.Series(1.0, index=sort_ix)
    c_items = [sort_ix]
    while len(c_items) > 0:
        c_items = [
            i[j:k] for i in c_items for j, k in ((0, len(i) // 2), (len(i) // 2, len(i))) if len(i) > 1
        ]
        for i in range(0, len(c_items), 2):
            c0, c1 = c_items[i], c_items[i + 1]
            v0, v1 = _ref_cluster_var(cov, c0), _ref_cluster_var(cov, c1)
            a = 1 - v0 / (v0 + v1)
            w[c0] *= a
            w[c1] *= 1 - a
    return w


def _ref_hrp(cov: pd.DataFrame, distance_of_distances: bool) -> pd.Series:
    corr = cov_to_corr(cov)
    dist = ((1 - corr) / 2.0) ** 0.5
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if distance_of_distances:
            link = sch.linkage(dist.to_numpy(), "single")
        else:
            d = dist.to_numpy().copy()
            np.fill_diagonal(d, 0.0)
            link = sch.linkage(squareform(d, checks=False), "single")
    sort_ix = corr.index[_ref_quasi_diag(link)].tolist()
    return _ref_rec_bipart(cov, sort_ix).reindex(cov.index)


# ---------------------------------------------------------------------------
# risk.py — Ledoit-Wolf
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed,t,p", [(0, 250, 12), (1, 40, 25), (2, 600, 5)])
def test_ledoit_wolf_identity_matches_sklearn(seed, t, p):
    df = _returns(seed, t=t, p=p)
    ours = ledoit_wolf_cov(df, target="identity", min_periods=10)
    ref = LedoitWolf().fit(df.to_numpy())
    np.testing.assert_allclose(ours.to_numpy(), ref.covariance_, rtol=1e-10, atol=1e-16)
    assert ours.attrs["shrinkage"] == pytest.approx(ref.shrinkage_, rel=1e-10)


@pytest.mark.parametrize("seed,t,p", [(3, 250, 12), (4, 60, 20)])
def test_ledoit_wolf_constant_correlation_matches_reference(seed, t, p):
    df = _returns(seed, t=t, p=p)
    ours = ledoit_wolf_cov(df, target="constant_correlation", min_periods=10)
    ref, shrink = _ref_covcor(df.to_numpy())
    np.testing.assert_allclose(ours.to_numpy(), ref, rtol=1e-10, atol=1e-16)
    assert ours.attrs["shrinkage"] == pytest.approx(shrink, rel=1e-10)
    assert 0.0 < ours.attrs["shrinkage"] < 1.0


@pytest.mark.parametrize("target", ["constant_correlation", "identity"])
@pytest.mark.parametrize("seed", [5, 6, 7])
def test_ledoit_wolf_with_nan_is_psd(seed, target):
    df = _returns(seed, t=120, p=15, nan_frac=0.35)
    cov = ledoit_wolf_cov(df, target=target, min_periods=20)
    a = cov.to_numpy()
    assert np.all(np.isfinite(a))
    np.testing.assert_allclose(a, a.T, atol=0)
    eig = np.linalg.eigvalsh(a)
    assert eig.min() >= -1e-12 * eig.max()
    assert 0.0 <= cov.attrs["shrinkage"] <= 1.0
    # variances = variances par titre sur ses observations, rétrécies vers la cible
    if target == "constant_correlation":
        np.testing.assert_allclose(np.diag(a), df.var(ddof=0).to_numpy(), rtol=1e-10)


def test_pairwise_covariance_without_shrinkage():
    """Avec δ = 0, la covariance par paires est celle calculée à la main."""
    df = _returns(8, t=200, p=6)
    # cotations tardives : disponibilité emboîtée (cas des introductions en bourse)
    for k, start in enumerate([0, 0, 30, 60, 90, 120]):
        df.iloc[:start, k] = np.nan
    cov = ledoit_wolf_cov(df, shrinkage=0.0, min_periods=20)
    assert not cov.attrs["projected"]
    x = df.to_numpy()
    mean = np.nanmean(x, axis=0)
    expected = np.empty((6, 6))
    for i in range(6):
        for j in range(6):
            m = np.isfinite(x[:, i]) & np.isfinite(x[:, j])
            expected[i, j] = np.mean((x[m, i] - mean[i]) * (x[m, j] - mean[j]))
    np.testing.assert_allclose(cov.to_numpy(), expected, rtol=1e-12)


def test_ledoit_wolf_projects_indefinite_pairwise_matrix():
    """Des paires observées sur des sous-périodes disjointes donnent une matrice
    indéfinie : la projection de Higham doit la rendre SDP."""
    rng = np.random.default_rng(9)
    t = 300
    z = rng.standard_normal((t, 3)) * 0.01
    a = z[:, 0]
    b = a + 0.1 * z[:, 1]
    c = np.where(np.arange(t) < 150, b, -a) + 0.1 * z[:, 2]
    df = pd.DataFrame({"A": a, "B": b, "C": c})
    df.loc[df.index < 150, "A"] = np.nan  # A–C observés ensemble seulement quand C ≈ −A
    df.loc[df.index >= 150, "B"] = np.nan  # B–C observés ensemble seulement quand C ≈ B
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cov = ledoit_wolf_cov(df, shrinkage=0.0, min_periods=20, min_overlap=20)
    assert cov.attrs["projected"]
    eig = np.linalg.eigvalsh(cov.to_numpy())
    assert eig.min() >= -1e-12
    np.testing.assert_allclose(np.diag(cov), df.var(ddof=0).to_numpy(), rtol=1e-9)


def test_ledoit_wolf_drops_short_or_constant_series():
    df = _returns(10, t=100, p=5)
    df["NEW"] = np.nan
    df.iloc[-5:, df.columns.get_loc("NEW")] = 0.01  # 5 observations seulement
    df["DEAD"] = 0.0  # jamais échangé : rendement toujours nul
    with pytest.warns(RuntimeWarning, match="NEW"):
        cov = ledoit_wolf_cov(df, min_periods=20)
    assert "NEW" not in cov.index and "DEAD" not in cov.index
    assert set(cov.attrs["dropped"]) == {"NEW", "DEAD"}
    assert cov.shape == (5, 5)


def test_ledoit_wolf_horizon_and_annualization():
    df = _returns(11, t=500, p=6)
    weekly = aggregate_returns(df, 5)
    c_h = ledoit_wolf_cov(df, horizon=5, shrinkage=0.0)
    expected = weekly.cov(ddof=0).to_numpy() / 5.0
    np.testing.assert_allclose(c_h.to_numpy(), expected, rtol=1e-10)
    c_a = ledoit_wolf_cov(df, horizon=5, shrinkage=0.0, annualize=True)
    np.testing.assert_allclose(c_a.to_numpy(), expected * 252, rtol=1e-10)
    fixed = ledoit_wolf_cov(df, shrinkage=0.3)
    assert fixed.attrs["shrinkage"] == 0.3


def test_aggregate_returns_end_aligned_compounding():
    idx = pd.bdate_range("2025-01-01", periods=7)
    df = pd.DataFrame({"A": [0.5, 0.1, 0.1, -0.1, 0.0, 0.2, np.nan], "B": [np.nan] * 4 + [0.1, 0.1, 0.1]})
    df.index = idx
    out = aggregate_returns(df, 3, min_valid_fraction=0.6)
    # 7 séances -> 2 blocs (séances 2-4 et 5-7), la première séance est écartée
    assert list(out.index) == [idx[3], idx[6]]
    assert out.loc[idx[3], "A"] == pytest.approx(1.1 * 1.1 * 0.9 - 1)
    assert out.loc[idx[6], "A"] == pytest.approx(1.0 * 1.2 - 1)  # NaN = cours inchangé
    assert np.isnan(out.loc[idx[3], "B"])  # aucune observation
    assert out.loc[idx[6], "B"] == pytest.approx(1.1**3 - 1)


def test_multi_day_returns_reduce_stale_price_bias():
    """Prix périmés : la corrélation quotidienne est fortement biaisée vers 0,
    l'agrégation multi-séances la corrige en grande partie."""
    rng = np.random.default_rng(42)
    t, rho, vol = 2500, 0.6, 0.02
    chol = np.linalg.cholesky(np.array([[1.0, rho], [rho, 1.0]]))
    latent = np.exp(np.cumsum(rng.standard_normal((t, 2)) @ chol.T * vol, axis=0))
    traded = rng.random((t, 2)) < 0.3
    traded[0] = True
    obs = pd.DataFrame(np.where(traded, latent, np.nan), columns=["X", "Y"]).ffill()
    rets = (obs / obs.shift(1) - 1).iloc[1:]
    corr = {
        h: cov_to_corr(ledoit_wolf_cov(rets, shrinkage=0.0, horizon=h)).iloc[0, 1] for h in (1, 5, 20)
    }
    assert corr[1] < 0.2
    assert corr[1] < corr[5] < corr[20]
    assert abs(corr[20] - rho) < 0.1
    # l'échelle quotidienne est préservée (Σ^(h)/h)
    vol20 = np.sqrt(np.diag(ledoit_wolf_cov(rets, shrinkage=0.0, horizon=20)))
    np.testing.assert_allclose(vol20, vol, rtol=0.15)


# ---------------------------------------------------------------------------
# risk.py — Higham
# ---------------------------------------------------------------------------


def test_nearest_correlation_higham_example():
    """Exemple de Higham (2002) : A = [[1,1,0],[1,1,1],[0,1,1]]."""
    a = np.array([[1.0, 1.0, 0.0], [1.0, 1.0, 1.0], [0.0, 1.0, 1.0]])
    x = nearest_correlation(a)
    expected = np.array([[1.0, 0.7607, 0.1573], [0.7607, 1.0, 0.7607], [0.1573, 0.7607, 1.0]])
    np.testing.assert_allclose(x, expected, atol=2e-4)
    np.testing.assert_allclose(np.diag(x), 1.0)
    assert np.linalg.eigvalsh(x).min() >= -1e-12


def test_nearest_correlation_keeps_valid_matrix():
    c = cov_to_corr(np.cov(_returns(12, t=100, p=8).to_numpy().T))
    np.testing.assert_allclose(nearest_correlation(c), c, atol=1e-9)
    cdf = pd.DataFrame(c)
    assert isinstance(nearest_correlation(cdf), pd.DataFrame)


def test_nearest_psd_cov_keeps_variances():
    cov = pd.DataFrame([[4.0, 3.9, 0.0], [3.9, 4.0, 3.9], [0.0, 3.9, 4.0]], index=list("abc"), columns=list("abc"))
    psd = nearest_psd_cov(cov)
    np.testing.assert_allclose(np.diag(psd), 4.0)
    assert np.linalg.eigvalsh(psd.to_numpy()).min() >= -1e-12


# ---------------------------------------------------------------------------
# risk.py — HRP et décomposition du risque
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("distance_of_distances", [False, True])
@pytest.mark.parametrize("seed", [13, 14])
def test_hrp_matches_reference_implementation(seed, distance_of_distances):
    df = _returns(seed, t=260, p=10)
    cov = df.cov()
    ours = hrp_weights(cov, distance_of_distances=distance_of_distances)
    ref = _ref_hrp(cov, distance_of_distances)
    np.testing.assert_allclose(ours.to_numpy(), ref.to_numpy(), rtol=1e-12)
    assert list(ours.index) == list(cov.index)


def test_hrp_small_hand_example():
    """2 actifs : HRP = inverse-variance ; blocs identiques : poids égaux par bloc."""
    cov2 = pd.DataFrame([[0.04, 0.01], [0.01, 0.01]], index=["A", "B"], columns=["A", "B"])
    for split in ("halves", "tree"):
        w = hrp_weights(cov2, split=split)
        np.testing.assert_allclose(w.to_numpy(), [0.2, 0.8])
    block = np.kron(np.eye(2), np.full((2, 2), 0.5)) + 0.5 * np.eye(4)
    cov4 = pd.DataFrame(block * 0.01, index=list("ABCD"), columns=list("ABCD"))
    w4 = hrp_weights(cov4, split="tree")
    np.testing.assert_allclose(w4.to_numpy(), 0.25)
    assert hrp_weights(cov4.iloc[:1, :1]).iloc[0] == 1.0


def test_hrp_properties():
    cov = ledoit_wolf_cov(_returns(15, p=20))
    for split in ("halves", "tree"):
        w = hrp_weights(cov, split=split)
        assert w.sum() == pytest.approx(1.0)
        assert (w > 0).all()
    with pytest.raises(ValueError):
        hrp_weights(cov.where(cov.index.to_series() != "T00"))


def test_inverse_vol_and_risk_contributions():
    vols = np.array([0.1, 0.2, 0.4])
    cov = pd.DataFrame(np.diag(vols**2), index=list("abc"), columns=list("abc"))
    w = inverse_vol_weights(cov)
    np.testing.assert_allclose(w.to_numpy(), (1 / vols) / (1 / vols).sum())
    rc = risk_contributions(w, cov)
    np.testing.assert_allclose(rc.to_numpy(), 1 / 3)  # parité de risque si ρ = 0
    w2 = inverse_vol_weights(cov, power=2)
    np.testing.assert_allclose(w2.to_numpy(), (1 / vols**2) / (1 / vols**2).sum())
    full = ledoit_wolf_cov(_returns(16, p=8))
    ww = pd.Series(np.linspace(1, 2, 8), index=full.index)
    ww /= ww.sum()
    rc_abs = risk_contributions(ww, full, relative=False)
    assert rc_abs.sum() == pytest.approx(portfolio_volatility(ww, full))
    assert risk_contributions(ww, full).sum() == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# construct.py — liquidité
# ---------------------------------------------------------------------------


def test_liquidity_caps_formula():
    adv = pd.Series({"SNTS": 50_000_000.0, "ORAC": 2_500_000.0, "XXX": np.nan, "ZERO": 0.0})
    caps = liquidity_caps(adv, capital=10_000_000.0, max_adv_participation=0.2, max_days_to_liquidate=20)
    # 0,2 × 2,5 M × 20 / 10 M = 1,0 ; 50 M -> plafonné à 1
    assert caps["ORAC"] == pytest.approx(1.0)
    assert caps["SNTS"] == 1.0
    assert caps["XXX"] == 0.0 and caps["ZERO"] == 0.0
    caps2 = liquidity_caps(adv, capital=100_000_000.0, max_adv_participation=0.1, max_days_to_liquidate=10)
    assert caps2["ORAC"] == pytest.approx(0.1 * 2_500_000 * 10 / 100_000_000)


def test_average_daily_value_has_no_lookahead():
    idx = pd.bdate_range("2025-01-01", periods=10)
    value = pd.DataFrame({"A": [100.0] * 5 + [1e9] * 5, "B": [np.nan, 50.0] * 5}, index=idx)
    adv = average_daily_value(value, window=4, asof=idx[4], min_periods=2)
    assert adv["A"] == pytest.approx(100.0)  # les séances futures (1e9) sont ignorées
    assert adv["B"] == pytest.approx(25.0)  # séances sans échange = 0
    med = average_daily_value(value, window=4, asof=idx[4], stat="median", min_periods=2)
    assert med["B"] == pytest.approx(25.0)


# ---------------------------------------------------------------------------
# construct.py — build_portfolio
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["mv_alpha", "hrp_tilt", "equal"])
@pytest.mark.parametrize("seed", list(range(8)))
def test_build_portfolio_respects_constraints(method, seed):
    alpha, cov, liq, prev, sectors, countries = _problem(seed)
    cons = LEGACY_CONSTRAINTS
    w = build_portfolio(alpha, cov, cons, liq, prev, sectors, countries, method=method)
    _assert_feasible(w, cons, liq, sectors, countries)
    assert w.attrs["feasible_full_budget"]
    assert w.sum() == pytest.approx(1.0 - cons.cash_buffer, abs=1e-8)
    nz = w[w > 0]
    assert cons.min_names <= len(nz) <= cons.max_names
    assert set(w.index) == set(alpha.index) | set(prev.index)


@pytest.mark.parametrize("method", ["mv_alpha", "hrp_tilt", "equal"])
@pytest.mark.parametrize("seed", [20, 21, 22])
def test_build_portfolio_tight_liquidity_keeps_cash(method, seed):
    """Plafonds de liquidité trop serrés : on n'investit que la capacité (PL)."""
    alpha, cov, liq, prev, sectors, countries = _problem(seed, tight=True)
    cons = LEGACY_CONSTRAINTS
    w = build_portfolio(alpha, cov, cons, liq, prev, sectors, countries, method=method)
    _assert_feasible(w, cons, liq, sectors, countries)
    assert not w.attrs["feasible_full_budget"]
    # capacité maximale atteignable avec max_names lignes (borne supérieure)
    best = np.sort(np.minimum(liq.to_numpy(), cons.max_weight))[::-1][: cons.max_names].sum()
    assert w.sum() <= best + 1e-9
    assert w.sum() < 1.0 - cons.cash_buffer


def test_build_portfolio_custom_tight_groups():
    alpha, cov, liq, prev, sectors, countries = _problem(30)
    cons = replace(LEGACY_CONSTRAINTS, max_sector_weight=0.25, max_country_weight=0.35, max_weight=0.10, max_names=12)
    for method in ("mv_alpha", "hrp_tilt", "equal"):
        w = build_portfolio(alpha, cov, cons, liq, prev, sectors, countries, method=method)
        _assert_feasible(w, cons, liq, sectors, countries)


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_mv_alpha_is_optimal():
    """Sans élagage ni coûts, la solution coïncide avec un solveur indépendant."""
    alpha, cov, liq, _, sectors, countries = _problem(40, n=12)
    cons = replace(LEGACY_CONSTRAINTS, min_weight=0.0, max_names=12, min_names=1, max_weight=0.3)
    lam = 4.0
    w = build_portfolio(alpha, cov, cons, liq, None, sectors, countries, risk_aversion=lam, tcost=0.0)
    _assert_feasible(w, cons, liq, sectors, countries)
    a, s = alpha.to_numpy(), cov.loc[alpha.index, alpha.index].to_numpy()
    u = np.minimum(liq.to_numpy(), 0.3)
    groups = []
    for labels, cap in ((sectors, cons.max_sector_weight), (countries, cons.max_country_weight)):
        for lab in labels.unique():
            groups.append(((labels == lab).to_numpy().astype(float), cap))
    lin = [optimize.LinearConstraint(np.ones((1, 12)), 0.98, 0.98)]
    lin += [optimize.LinearConstraint(g[None, :], -np.inf, c) for g, c in groups]
    ref = optimize.minimize(
        lambda x: -(a @ x - 0.5 * lam * x @ s @ x),
        np.full(12, 0.98 / 12),
        jac=lambda x: -(a - lam * s @ x),
        hess=lambda x: lam * s,
        bounds=optimize.Bounds(np.zeros(12), u),
        constraints=lin,
        method="trust-constr",
        options={"gtol": 1e-12, "xtol": 1e-14, "maxiter": 10000},
    )
    obj = lambda x: a @ x - 0.5 * lam * x @ s @ x  # noqa: E731
    assert obj(w.loc[alpha.index].to_numpy()) >= obj(ref.x) - 1e-8


def test_mv_alpha_low_risk_aversion_fills_best_names_to_cap():
    names = [f"N{i}" for i in range(10)]
    alpha = pd.Series(np.linspace(0.30, 0.01, 10), index=names)
    cov = pd.DataFrame(np.eye(10) * 0.04, index=names, columns=names)
    w = build_portfolio(alpha, cov, LEGACY_CONSTRAINTS, None, None, risk_aversion=1e-6, tcost=0.0)
    # 6 meilleurs à 15 %, puis 8 % sur le 7e : Σ = 0,98
    np.testing.assert_allclose(w.iloc[:6].to_numpy(), 0.15, atol=1e-7)
    assert w.iloc[6] == pytest.approx(0.08, abs=1e-7)
    assert w.iloc[7:].sum() == pytest.approx(0.0, abs=1e-7)


def test_mv_alpha_transaction_costs_create_inertia():
    alpha, cov, _, _, sectors, countries = _problem(50, n=20)
    cons = replace(LEGACY_CONSTRAINTS, max_names=20, min_names=1)
    prev = pd.Series(0.0, index=alpha.index)
    prev.iloc[:10] = 0.098  # portefeuille réalisable : Σ = 0,98, ≤ 15 %
    w_free = build_portfolio(alpha, cov, cons, None, prev, method="mv_alpha", tcost=0.0)
    w_sticky = build_portfolio(alpha, cov, cons, None, prev, method="mv_alpha", tcost=10.0)
    to_free = 0.5 * (w_free - prev).abs().sum()
    to_sticky = 0.5 * (w_sticky - prev).abs().sum()
    assert to_sticky < 1e-6 < to_free
    np.testing.assert_allclose(w_sticky.to_numpy(), prev.to_numpy(), atol=1e-6)


def test_max_names_min_weight_and_min_names():
    alpha, cov, *_ = _problem(60, n=30)
    cons = replace(LEGACY_CONSTRAINTS, max_names=8, min_names=6, min_weight=0.05, max_weight=0.3)
    for method in ("mv_alpha", "hrp_tilt", "equal"):
        w = build_portfolio(alpha, cov, cons, None, None, method=method)
        nz = w[w > 0]
        assert 6 <= len(nz) <= 8
        assert nz.min() >= 0.05 - 1e-9
        assert w.sum() == pytest.approx(0.98, abs=1e-8)
        # les titres retenus figurent parmi les 8 meilleurs alphas
        assert set(nz.index) <= set(alpha.nlargest(8).index)


def test_min_names_overrides_pruning():
    """Un alpha très concentré pousserait à < min_names lignes : on en garde 6."""
    names = [f"N{i}" for i in range(10)]
    alpha = pd.Series([1.0, 0.9] + [-0.5] * 8, index=names)
    cov = pd.DataFrame(np.eye(10) * 0.04, index=names, columns=names)
    cons = replace(LEGACY_CONSTRAINTS, max_weight=0.6, min_names=6, max_names=10)
    w = build_portfolio(alpha, cov, cons, None, None, risk_aversion=0.01, tcost=0.0)
    nz = w[w > 0]
    assert len(nz) == 6
    assert nz.min() >= cons.min_weight - 1e-9
    assert w.sum() == pytest.approx(0.98, abs=1e-8)


def test_equal_and_untilted_hrp_when_constraints_slack():
    alpha, cov, *_ = _problem(70, n=20)
    cons = replace(LEGACY_CONSTRAINTS, max_weight=1.0, min_weight=0.0, max_names=10, min_names=1)
    top = alpha.nlargest(10).index
    w_eq = build_portfolio(alpha, None, cons, method="equal")
    np.testing.assert_allclose(w_eq.loc[top].to_numpy(), 0.098)
    w_hrp = build_portfolio(alpha, cov, cons, method="hrp_tilt", tilt_strength=0.0)
    ref = hrp_weights(cov.loc[w_hrp[w_hrp > 0].index, w_hrp[w_hrp > 0].index]) * 0.98
    assert set(w_hrp[w_hrp > 0].index) == set(top)
    np.testing.assert_allclose(w_hrp.loc[ref.index].to_numpy(), ref.to_numpy(), atol=1e-12)
    # l'inclinaison augmente le poids relatif des meilleurs alphas
    w_tilt = build_portfolio(alpha, cov, cons, method="hrp_tilt", tilt_strength=1.0)
    best, worst = alpha.loc[top].idxmax(), alpha.loc[top].idxmin()
    assert w_tilt[best] / w_tilt[worst] > w_hrp[best] / w_hrp[worst]


def test_sector_cap_binds_when_alpha_concentrated():
    names = [f"B{i}" for i in range(8)] + [f"O{i}" for i in range(8)]
    alpha = pd.Series(np.r_[np.full(8, 0.3), np.full(8, 0.02)], index=names)
    sectors = pd.Series(["FIN"] * 8 + ["IND", "TEL", "CB", "SPU"] * 2, index=names)
    cov = pd.DataFrame(np.eye(16) * 0.04, index=names, columns=names)
    for method in ("mv_alpha", "hrp_tilt", "equal"):
        w = build_portfolio(alpha, cov, LEGACY_CONSTRAINTS, None, None, sectors=sectors, method=method)
        _assert_feasible(w, LEGACY_CONSTRAINTS, sectors=sectors)
        assert w[sectors == "FIN"].sum() <= 0.40 + 1e-9
        assert w.sum() == pytest.approx(0.98, abs=1e-8)


def test_ineligible_names_get_zero():
    alpha, cov, liq, *_ = _problem(80, n=15)
    alpha.iloc[0] = np.nan
    liq = liq.drop(liq.index[1])  # liquidité inconnue -> non détenable
    cov2 = cov.copy()
    w = build_portfolio(alpha, cov2, LEGACY_CONSTRAINTS, liq, None)
    assert w.iloc[0] == 0.0 and w.iloc[1] == 0.0
    with pytest.warns(RuntimeWarning):
        empty = build_portfolio(alpha, cov, LEGACY_CONSTRAINTS, liq * 0.0, None)
    assert (empty == 0).all() and empty.attrs["budget"] == 0.0
    with pytest.raises(ValueError):
        build_portfolio(alpha, cov, replace(LEGACY_CONSTRAINTS, long_only=False), None, None)


def test_build_portfolio_is_deterministic():
    alpha, cov, liq, prev, sectors, countries = _problem(90)
    w1 = build_portfolio(alpha, cov, LEGACY_CONSTRAINTS, liq, prev, sectors, countries)
    perm = np.random.default_rng(0).permutation(len(alpha))
    w2 = build_portfolio(alpha.iloc[perm], cov, LEGACY_CONSTRAINTS, liq, prev, sectors, countries)
    np.testing.assert_allclose(w1.to_numpy(), w2.reindex(w1.index).to_numpy(), atol=1e-7)


# ---------------------------------------------------------------------------
# construct.py — sélection sous contrainte de capacité (non-régression)
# ---------------------------------------------------------------------------
#
# Anomalie corrigée : la sélection gloutonne retenait tout titre augmentant la
# capacité, même de très peu ; elle atteignait max_names avec des titres peu
# liquides avant d'atteindre le budget, laissant le portefeuille en liquidités
# (et feasible_full_budget=False) alors qu'une sélection d'au plus max_names
# titres permettait d'investir B = 1 − cash_buffer.


def _ref_max_investable(
    upper: np.ndarray,
    floor: float,
    groups: list[tuple[np.ndarray, float]],
    budget: float,
    k: int,
    n_min: int = 0,
) -> float:
    """Référence indépendante : ``max 1ᵀw`` avec au plus ``k`` lignes, chacune
    dans ``{0} ∪ [floor, u_i]``, au moins ``n_min`` lignes (abandonné si
    irréalisable), plafonds de groupe et ``1ᵀw ≤ budget`` (PLNE big-M)."""
    n = len(upper)

    def solve(nmin: int) -> float | None:
        a = [np.hstack([np.eye(n), -np.diag(upper)]), np.hstack([-np.eye(n), floor * np.eye(n)])]
        lo = [np.full(2 * n, -np.inf)]
        hi = [np.zeros(2 * n)]
        a.append(np.r_[np.zeros(n), np.ones(n)][None, :])
        lo.append([nmin])
        hi.append([k])
        for member, cap in groups:
            a.append(np.r_[member, np.zeros(n)][None, :])
            lo.append([-np.inf])
            hi.append([cap])
        a.append(np.r_[np.ones(n), np.zeros(n)][None, :])
        lo.append([-np.inf])
        hi.append([budget])
        res = optimize.milp(
            np.r_[-np.ones(n), np.zeros(n)],
            constraints=optimize.LinearConstraint(np.vstack(a), np.concatenate(lo), np.concatenate(hi)),
            integrality=np.r_[np.zeros(n), np.ones(n)],
            bounds=optimize.Bounds(np.zeros(2 * n), np.r_[upper, np.ones(n)]),
            options={"mip_rel_gap": 1e-10},
        )
        return float(-res.fun) if res.status == 0 else None

    nm = min(n_min, k, n)
    val = solve(nm)
    if val is None and nm > 0:
        val = solve(0)
    assert val is not None
    return val


def _label_groups(names: pd.Index, labels: pd.Series | None, cap: float) -> list[tuple[np.ndarray, float]]:
    if labels is None:
        return []
    lab = labels.reindex(names).astype(str).to_numpy()
    return [((lab == g).astype(float), cap) for g in sorted(set(lab))]


def _illiquid_top_problem():
    """15 titres à fort alpha mais peu liquides (plafond 3 %) et 5 liquides (15 %)."""
    names = [f"I{i:02d}" for i in range(15)] + [f"L{i}" for i in range(5)]
    alpha = pd.Series(np.r_[np.linspace(0.30, 0.20, 15), np.linspace(0.19, 0.15, 5)], index=names)
    cov = pd.DataFrame(np.eye(20) * 0.04, index=names, columns=names)
    liq = pd.Series(np.r_[np.full(15, 0.03), np.full(5, 0.15)], index=names)
    return alpha, cov, liq


@pytest.mark.parametrize("method", ["mv_alpha", "hrp_tilt", "equal"])
def test_selection_reaches_full_budget_with_liquid_names(method):
    """Ancien comportement : 15 illiquides retenus, 45 % investis,
    feasible_full_budget=False. Or 10 illiquides + 5 liquides (15 lignes)
    permettent d'investir 98 %."""
    alpha, cov, liq = _illiquid_top_problem()
    cons = LEGACY_CONSTRAINTS
    w = build_portfolio(alpha, cov, cons, liq, None, method=method)
    _assert_feasible(w, cons, liq)
    assert w.sum() == pytest.approx(0.98, abs=1e-8)
    assert w.attrs["feasible_full_budget"]
    assert w.attrs["max_investable"] == pytest.approx(0.98, abs=1e-7)
    assert w.attrs["selection"] == "milp"
    # sélection lexicographique par score : on garde les 10 meilleurs illiquides
    # (au-delà, les 5 places restantes ne suffisent plus) et les 5 liquides
    expected = set(alpha.index[:10]) | set(alpha.index[15:])
    assert set(w[w > 0].index) == expected
    assert w.attrs["n_names"] == 15
    np.testing.assert_allclose(w.iloc[:10].to_numpy(), 0.03, atol=1e-8)


def test_mv_alpha_selection_beats_hand_built_feasible_portfolio():
    """L'objectif moyenne-variance obtenu domine un portefeuille réalisable
    construit à la main (5 liquides à 15 % + 8 meilleurs illiquides)."""
    alpha, cov, liq = _illiquid_top_problem()
    lam = 5.0
    w = build_portfolio(alpha, cov, LEGACY_CONSTRAINTS, liq, None, risk_aversion=lam, tcost=0.0)
    alt = pd.Series(0.0, index=alpha.index)
    alt.iloc[15:] = 0.15
    alt.iloc[:8] = 0.23 / 8  # Σ = 0,98, ≤ 3 %
    assert constraint_violations(alt, LEGACY_CONSTRAINTS, liq)["liquidity"] == 0.0
    s = cov.to_numpy()

    def obj(x: pd.Series) -> float:
        v = x.reindex(alpha.index).to_numpy()
        return float(alpha.to_numpy() @ v - 0.5 * lam * v @ s @ v)

    assert obj(w) >= obj(alt) - 1e-10
    assert float(alpha @ w) > 0.19


def _brute_force_capacity(u: np.ndarray, sectors: np.ndarray, cons: Constraints) -> float:
    """Capacité exacte par énumération des ensembles de lignes (un seul niveau de
    groupes) : pour S fixé, l'ensemble réalisable est un polytope et
    ``max Σ_{S∩g} w = min(cap, Σ_{S∩g} u)`` dès que ``|S∩g|·m ≤ cap``."""
    m, b, k = cons.min_weight, 1.0 - cons.cash_buffer, cons.max_names
    best: dict[bool, float] = {}
    for r in range(1, k + 1):
        for subset in itertools.combinations(range(len(u)), r):
            s = list(subset)
            if r * m > b + 1e-12:
                continue
            tot, ok = 0.0, True
            for lab in set(sectors[s]):
                mem = [i for i in s if sectors[i] == lab]
                if len(mem) * m > cons.max_sector_weight + 1e-12:
                    ok = False
                    break
                tot += min(cons.max_sector_weight, float(u[mem].sum()))
            if ok:
                key = r >= cons.min_names
                best[key] = max(best.get(key, 0.0), min(b, tot))
    return best[True] if True in best else best[False]


def _anti_liquid_problem(seed: int, scale: float):
    """Les meilleurs alphas sont les titres les moins liquides (cas BRVM typique)."""
    rng = np.random.default_rng(seed)
    n = 12
    names = [f"N{i:02d}" for i in range(n)]
    liq = pd.Series(np.sort(rng.uniform(0.02, scale, n)), index=names)
    alpha = pd.Series(np.sort(rng.normal(0.1, 0.05, n))[::-1], index=names)
    sectors = pd.Series(rng.choice(["FIN", "IND", "TEL", "CB"], n), index=names)
    return alpha, liq, sectors


@pytest.mark.parametrize(("scale", "seed"), [(0.25, s) for s in range(6)] + [(0.45, s) for s in range(3)])
def test_selection_capacity_matches_brute_force(scale, seed):
    """Investissement = capacité exacte (énumération) ; feasible_full_budget et
    max_investable reflètent cette capacité, pas la sélection retenue."""
    alpha, liq, sectors = _anti_liquid_problem(seed, scale)
    cons = replace(LEGACY_CONSTRAINTS, max_weight=0.3, max_names=5, min_names=2, max_sector_weight=0.4)
    u = np.minimum(liq.to_numpy(), cons.max_weight)
    ref = _brute_force_capacity(u, sectors.to_numpy(), cons)
    b = 1.0 - cons.cash_buffer
    for method in ("equal", "hrp_tilt", "mv_alpha"):
        cov = pd.DataFrame(np.eye(12) * 0.04, index=alpha.index, columns=alpha.index)
        w = build_portfolio(alpha, cov, cons, liq, None, sectors=sectors, method=method)
        _assert_feasible(w, cons, liq, sectors)
        assert w.attrs["selection"] == "milp"
        assert w.sum() == pytest.approx(ref, abs=1e-7)
        assert w.attrs["max_investable"] == pytest.approx(ref, abs=1e-7)
        assert w.attrs["feasible_full_budget"] == (ref >= b - 1e-9)
        assert cons.min_names <= w.attrs["n_names"] <= cons.max_names


@pytest.mark.parametrize("seed", [0, 2])
def test_select_is_lexicographically_best_among_max_capacity_sets(seed):
    """_select renvoie, parmi les ensembles de max_names titres dont la capacité
    atteint C*, le meilleur pour l'ordre lexicographique des scores."""
    from brvm_alpha.portfolio.construct import _group_matrix, _select

    alpha, liq, sectors = _anti_liquid_problem(seed, 0.25)
    cons = replace(LEGACY_CONSTRAINTS, max_weight=0.3, max_names=5, min_names=2, max_sector_weight=0.4)
    names = alpha.index
    u = np.minimum(liq.to_numpy(), cons.max_weight)
    b = 1.0 - cons.cash_buffer
    g, c, _ = _group_matrix(names, sectors, cons.max_sector_weight, b)
    order = np.lexsort((np.asarray(names.astype(str)), -alpha.to_numpy()))
    res = _select(order, cons.max_names, u, g, c, b, floor=cons.min_weight, n_min=cons.min_names)
    c_star = _brute_force_capacity(u, sectors.to_numpy(), cons)
    assert res.capacity == pytest.approx(c_star, abs=1e-7)
    assert set(res.support) <= set(res.idx) and len(res.idx) == cons.max_names
    rank = {int(v): r for r, v in enumerate(order)}
    best = None
    for subset in itertools.combinations(range(len(names)), cons.max_names):
        cap = _brute_force_capacity(u[list(subset)], sectors.to_numpy()[list(subset)], cons)
        if cap >= c_star - 1e-9:
            key = tuple(sorted(rank[i] for i in subset))
            best = key if best is None or key < best else best
    assert tuple(sorted(rank[int(i)] for i in res.idx)) == best


@pytest.mark.parametrize(("capital", "seed"), [(5e8, 23), (5e8, 50), (5e8, 58), (2e9, 16), (2e9, 48)])
def test_selection_realistic_brvm_liquidity(capital, seed):
    """Univers BRVM réaliste (45 titres, ADV log-normale, secteurs et pays) :
    cas où l'ancien glouton laissait de 2 à 12 % en liquidités en trop."""
    rng = np.random.default_rng(seed)
    n = 45
    names = pd.Index([f"S{i:02d}" for i in range(n)])
    adv = pd.Series(np.exp(rng.normal(np.log(5e6), 1.5, n)), index=names)
    liq = liquidity_caps(adv, capital, max_adv_participation=0.20, max_days_to_liquidate=20)
    alpha = pd.Series(rng.normal(0.05, 0.1, n), index=names)
    sectors = pd.Series(
        rng.choice(["FIN", "TEL", "CB", "IND", "SPU", "DIS", "AGR"], n, p=[0.35, 0.05, 0.15, 0.1, 0.1, 0.15, 0.1]),
        index=names,
    )
    countries = pd.Series(
        rng.choice(["CI", "SN", "BF", "TG", "BJ", "ML"], n, p=[0.6, 0.1, 0.1, 0.1, 0.05, 0.05]),
        index=names,
    )
    cov = pd.DataFrame(np.eye(n) * 0.06 + 0.02, index=names, columns=names)
    cons = LEGACY_CONSTRAINTS
    b = 1.0 - cons.cash_buffer
    u = np.minimum(liq.to_numpy(), cons.max_weight)
    u = np.where(u >= cons.min_weight, u, 0.0)
    groups = _label_groups(names, sectors, cons.max_sector_weight)
    groups += _label_groups(names, countries, cons.max_country_weight)
    ref = _ref_max_investable(u, cons.min_weight, groups, b, cons.max_names, cons.min_names)
    for method in ("mv_alpha", "equal"):
        w = build_portfolio(alpha, cov, cons, liq, None, sectors, countries, method=method)
        _assert_feasible(w, cons, liq, sectors, countries)
        assert w.sum() == pytest.approx(ref, abs=1e-7)
        assert w.attrs["max_investable"] == pytest.approx(ref, abs=1e-7)
        assert w.attrs["feasible_full_budget"] == (ref >= b - 1e-9)


def test_pruning_keeps_capacity_with_overlapping_groups():
    """Plafonds secteur × pays croisés : l'élagage heuristique (planchers sur
    min_names lignes) perdait de la capacité (0,54 investis) ; on repart du
    témoin PLNE, qui respecte aussi min_names : 6 lignes, 0,58 investis."""
    names = [f"S{i:02d}" for i in range(8)]
    alpha = pd.Series([0.2958, 0.2569, 0.2029, 0.1853, 0.0873, -0.0861, -0.0313, 0.0971], index=names)
    liq = pd.Series([0.4564, 0.0920, 0.1833, 0.7450, 0.3669, 0.2967, 0.5340, 0.1198], index=names)
    sectors = pd.Series(["G1", "G1", "G0", "G0", "G1", "G0", "G1", "G1"], index=names)
    countries = pd.Series(["C1", "C0", "C1", "C1", "C1", "C1", "C0", "C1"], index=names)
    cov = pd.DataFrame(np.eye(8) * 0.04, index=names, columns=names)
    cons = replace(
        LEGACY_CONSTRAINTS,
        max_weight=0.3,
        min_weight=0.02,
        max_names=18,
        min_names=6,
        max_sector_weight=0.3,
        max_country_weight=0.3,
        cash_buffer=0.0,
    )
    u = np.minimum(liq.to_numpy(), cons.max_weight)
    groups = _label_groups(alpha.index, sectors, 0.3) + _label_groups(alpha.index, countries, 0.3)
    ref = _ref_max_investable(u, cons.min_weight, groups, 1.0, cons.max_names, cons.min_names)
    assert ref == pytest.approx(0.58, abs=1e-7)
    for method in ("equal", "hrp_tilt", "mv_alpha"):
        w = build_portfolio(alpha, cov, cons, liq, None, sectors, countries, method=method, tcost=0.0)
        _assert_feasible(w, cons, liq, sectors, countries)
        assert w.sum() == pytest.approx(ref, abs=1e-7)
        assert w.attrs["n_names"] >= cons.min_names
        assert not w.attrs["feasible_full_budget"]
        assert w.attrs["max_investable"] == pytest.approx(ref, abs=1e-7)


def test_selection_fast_path_unchanged_when_top_names_suffice():
    """Si les max_names meilleurs scores suffisent, aucun PLNE : sélection « top »."""
    alpha, cov, liq, prev, sectors, countries = _problem(3)
    w = build_portfolio(alpha, cov, LEGACY_CONSTRAINTS, liq, prev, sectors, countries)
    assert w.attrs["selection"] == "top"
    assert w.attrs["max_investable"] == pytest.approx(0.98)


# ---------------------------------------------------------------------------
# construct.py — Kelly, bandes, turnover, lots
# ---------------------------------------------------------------------------


def test_fractional_kelly_scale():
    assert fractional_kelly_scale(0.10, 0.04, fraction=0.25, max_gross=5.0) == pytest.approx(0.625)
    assert fractional_kelly_scale(0.10, 0.04, fraction=1.0, max_gross=1.0) == 1.0
    assert fractional_kelly_scale(-0.05, 0.04) == 0.0
    mu = pd.Series([0.08, 0.06], index=["a", "b"])
    cov = pd.DataFrame([[0.04, 0.01], [0.01, 0.09]], index=["a", "b"], columns=["a", "b"])
    w = pd.Series([0.5, 0.5], index=["a", "b"])
    mu_p, var_p = 0.07, 0.25 * (0.04 + 0.09 + 0.02)
    assert fractional_kelly_scale(mu, cov, fraction=0.5, max_gross=10, weights=w) == pytest.approx(0.5 * mu_p / var_p)
    # long-only sans contrainte active = Σ⁻¹μ
    full = np.linalg.solve(cov.to_numpy(), mu.to_numpy())
    assert np.all(full > 0)
    assert fractional_kelly_scale(mu, cov, fraction=0.25, max_gross=10) == pytest.approx(0.25 * full.sum())
    # un actif d'espérance négative est exclu (x ≥ 0)
    mu_neg = pd.Series([0.08, -0.06], index=["a", "b"])
    x = fractional_kelly_scale(mu_neg, cov, fraction=1.0, max_gross=10)
    assert 0 < x <= 0.08 / 0.04 + 1e-9


def test_apply_no_trade_band():
    prev = pd.Series({"A": 0.30, "B": 0.30, "C": 0.30, "D": 0.015})
    target = pd.Series({"A": 0.31, "B": 0.20, "C": 0.29, "D": 0.0, "E": 0.18})
    w = apply_no_trade_band(target, prev, band=0.02)
    assert w["A"] == 0.30 and w["C"] == 0.30  # dans la bande : inchangés
    assert w["D"] == 0.0  # cible nulle : vendu
    assert w.sum() <= target.sum() + 1e-12
    assert w["B"] <= 0.20 and w["E"] <= 0.18
    w_keep = apply_no_trade_band(target, prev, band=0.02, exit_zero_targets=False)
    assert w_keep["D"] == 0.015


def test_cap_turnover():
    prev = pd.Series({"A": 0.5, "B": 0.5})
    target = pd.Series({"A": 0.0, "B": 0.2, "C": 0.8})
    w = cap_turnover(target, prev, max_turnover=0.4)
    assert 0.5 * (w - prev.reindex(w.index).fillna(0)).abs().sum() == pytest.approx(0.4)
    assert w.sum() == pytest.approx(1.0)
    assert cap_turnover(target, prev, max_turnover=2.0).equals(target.reindex(w.index).astype(float))


def test_to_lots_exact_example():
    weights = pd.Series({"SNTS": 0.40, "ORAC": 0.35, "SGBC": 0.23})
    prices = pd.Series({"SNTS": 25_000.0, "ORAC": 14_000.0, "SGBC": 30_000.0})
    shares = to_lots(weights, prices, capital=1_000_000.0)
    # planchers : 16, 25, 7 (coût 400 000 + 350 000 + 210 000 = 960 000)
    # reliquat 980 000 − 960 000 = 20 000 ; restes : SGBC 0,667, ORAC 0, SNTS 0
    # SGBC coûte 30 000 > 20 000 : rien d'autre n'est acheté
    assert shares.to_dict() == {"SNTS": 16, "ORAC": 25, "SGBC": 7}
    assert shares.dtype == np.int64
    shares2 = to_lots(weights, prices, capital=1_050_000.0)
    spent = float((shares2 * prices).sum())
    assert spent <= 0.98 * 1_050_000.0 + 1e-6


def test_to_lots_properties():
    rng = np.random.default_rng(100)
    names = [f"S{i}" for i in range(15)]
    w = pd.Series(rng.dirichlet(np.ones(15)) * 0.98, index=names)
    px = pd.Series(rng.uniform(500, 60_000, 15), index=names)
    px.iloc[0] = np.nan
    capital = 5_000_000.0
    caps = w * 1.01
    q = to_lots(w, px, capital, max_weight=caps)
    assert q.iloc[0] == 0
    val = q * px.fillna(0)
    assert val.sum() <= w.sum() * capital + 1e-6
    assert (val <= caps * capital + 1e-6).all()
    # sans plafond, l'écart à la cible est < 1 titre sauf si la liquidité manque
    q2 = to_lots(w, px, capital)
    gap = w * capital - q2 * px
    assert (gap.iloc[1:] < px.iloc[1:] + 1e-6).all()


def test_grinold_alpha():
    z = pd.Series({"a": 1.0, "b": -2.0})
    vol = pd.Series({"a": 0.3, "b": 0.2})
    a = grinold_alpha(z, vol, ic=0.05)
    assert a["a"] == pytest.approx(0.015) and a["b"] == pytest.approx(-0.02)


# ---------------------------------------------------------------------------
# Test d'intégration (si le panel a été construit)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not (ROOT / "data" / "panel" / "equities.parquet").exists(),
    reason="panel data/panel/equities.parquet absent",
)
def test_smoke_on_real_panel():
    eq = pd.read_parquet(ROOT / "data" / "panel" / "equities.parquet")
    close = eq.pivot_table(index="date", columns="symbol", values="close", aggfunc="last").sort_index()
    value = eq.pivot_table(index="date", columns="symbol", values="value", aggfunc="last").sort_index()
    close = close.iloc[-300:]
    value = value.reindex(close.index)
    rets = (close / close.shift(1) - 1).iloc[1:]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cov = ledoit_wolf_cov(rets, horizon=5, min_periods=20, annualize=True)
    assert np.linalg.eigvalsh(cov.to_numpy()).min() >= -1e-10
    hrp = hrp_weights(cov)
    assert hrp.sum() == pytest.approx(1.0)
    mom = (close.iloc[-1] / close.iloc[-120] - 1).reindex(cov.index)
    sectors = eq.sort_values("date").groupby("symbol")["sector"].last()
    liq = liquidity_caps(
        average_daily_value(value, window=60), capital=10_000_000.0, max_adv_participation=0.20, max_days_to_liquidate=20
    )
    cons = LEGACY_CONSTRAINTS
    for method in ("mv_alpha", "hrp_tilt", "equal"):
        w = build_portfolio(mom * 0.5, cov, cons, liq, None, sectors=sectors, method=method)
        _assert_feasible(w, cons, liq, sectors)
        lots = to_lots(w, close.iloc[-1], 10_000_000.0)
        assert (lots >= 0).all()

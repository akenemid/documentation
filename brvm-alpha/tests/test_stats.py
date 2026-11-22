"""Tests de brvm_alpha.quant.stats.

Chaque mesure est comparée à un calcul indépendant (formule écrite à la main
avec NumPy, statsmodels, simulation Monte-Carlo à graine fixe). Tous les
tests sont déterministes.
"""

from __future__ import annotations

import itertools
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats as sps

from brvm_alpha.quant import stats as st

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "data" / "panel" / "equities.parquet"


# ---------------------------------------------------------------------------
# Utilitaires de test (calculs indépendants)
# ---------------------------------------------------------------------------


def _moments_by_hand(x: np.ndarray) -> tuple[float, float, float]:
    """SR (ddof=1), asymétrie et kurtosis brute « population » à la main."""
    d = x - x.mean()
    m2 = np.mean(d**2)
    skew = np.mean(d**3) / m2**1.5
    kurt = np.mean(d**4) / m2**2
    sr = x.mean() / x.std(ddof=1)
    return sr, skew, kurt


def _psr_by_hand(x: np.ndarray, sr_star: float) -> float:
    sr, g3, g4 = _moments_by_hand(x)
    z = (sr - sr_star) * math.sqrt(len(x) - 1) / math.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr**2)
    return float(sps.norm.cdf(z))


def _dates(n: int) -> pd.DatetimeIndex:
    return pd.bdate_range("2020-01-01", periods=n)


@pytest.fixture
def small_returns() -> pd.Series:
    return pd.Series([0.10, -0.05, 0.02, -0.10, 0.15, 0.0], index=_dates(6))


# ---------------------------------------------------------------------------
# Sharpe et synthèse de performance
# ---------------------------------------------------------------------------


def test_sharpe_ratio_matches_hand_computation(small_returns: pd.Series) -> None:
    x = small_returns.to_numpy()
    assert st.sharpe_ratio(x, periods_per_year=None) == pytest.approx(x.mean() / x.std(ddof=1))
    assert st.sharpe_ratio(x) == pytest.approx(x.mean() / x.std(ddof=1) * math.sqrt(252))
    rf = 0.05
    rf_p = (1 + rf) ** (1 / 252) - 1
    e = x - rf_p
    assert st.sharpe_ratio(x, rf=rf) == pytest.approx(e.mean() / e.std(ddof=1) * math.sqrt(252))
    assert math.isnan(st.sharpe_ratio([0.01, 0.01, 0.01]))
    assert math.isnan(st.sharpe_ratio([0.01]))


def test_perf_summary_hand_example(small_returns: pd.Series) -> None:
    r = small_returns
    x = r.to_numpy()
    s = st.perf_summary(r)
    wealth = np.cumprod(1 + x)
    assert s["n_obs"] == 6
    assert s["start"] == r.index[0] and s["end"] == r.index[-1]
    assert s["total_return"] == pytest.approx(wealth[-1] - 1)
    assert s["cagr"] == pytest.approx(wealth[-1] ** (252 / 6) - 1)
    assert s["ann_return"] == pytest.approx(x.mean() * 252)
    assert s["vol"] == pytest.approx(x.std(ddof=1) * math.sqrt(252))
    assert s["sharpe"] == pytest.approx(x.mean() / x.std(ddof=1) * math.sqrt(252))
    downside = math.sqrt(np.mean(np.minimum(x, 0) ** 2))
    assert s["sortino"] == pytest.approx(x.mean() * 252 / (downside * math.sqrt(252)))
    # Drawdown : plus haut 1,1 en séance 0, creux 1,1·0,95·1,02·0,9 en séance 3.
    trough_wealth = 1.1 * 0.95 * 1.02 * 0.90
    assert s["max_drawdown"] == pytest.approx(trough_wealth / 1.1 - 1)
    assert s["max_drawdown_duration"] == 3
    assert s["longest_drawdown_duration"] == 3
    assert s["max_drawdown_peak"] == r.index[0]
    assert s["max_drawdown_trough"] == r.index[3]
    assert s["max_drawdown_recovery"] == r.index[4]
    assert s["calmar"] == pytest.approx(s["cagr"] / abs(s["max_drawdown"]))
    assert s["hit_rate"] == pytest.approx(3 / 6)
    assert s["best"] == pytest.approx(0.15) and s["worst"] == pytest.approx(-0.10)
    assert s["avg_gain"] == pytest.approx((0.10 + 0.02 + 0.15) / 3)
    assert s["avg_loss"] == pytest.approx((-0.05 - 0.10) / 2)
    assert s["profit_factor"] == pytest.approx(0.27 / 0.15)
    assert s["skew"] == pytest.approx(sps.skew(x))
    assert s["kurtosis"] == pytest.approx(sps.kurtosis(x, fisher=True))
    q = np.quantile(x, 0.05)
    assert s["var_95"] == pytest.approx(q)
    assert s["cvar_95"] == pytest.approx(x[x <= q].mean())
    assert s["psr"] == pytest.approx(_psr_by_hand(x, 0.0))


def test_perf_summary_benchmark_exact_linear_relation() -> None:
    rng = np.random.default_rng(1)
    idx = _dates(800)
    b = pd.Series(rng.normal(0.0003, 0.01, 800), index=idx)
    r = 0.0005 + 1.5 * b
    s = st.perf_summary(r, benchmark=b)
    assert s["beta"] == pytest.approx(1.5)
    assert s["alpha"] == pytest.approx(0.0005 * 252)
    assert s["correlation"] == pytest.approx(1.0)
    assert s["beta_dimson"] == pytest.approx(1.5, abs=1e-8)
    active = (r - b).to_numpy()
    te = active.std(ddof=1) * math.sqrt(252)
    assert s["tracking_error"] == pytest.approx(te)
    assert s["information_ratio"] == pytest.approx(active.mean() * 252 / te)
    bx = b.to_numpy()
    assert s["benchmark_cagr"] == pytest.approx(np.prod(1 + bx) ** (252 / 800) - 1)
    assert s["excess_cagr"] == pytest.approx(s["cagr"] - s["benchmark_cagr"])
    up = bx > 0
    assert s["up_capture"] == pytest.approx(r.to_numpy()[up].mean() / bx[up].mean())
    # Avec taux sans risque : alpha de Jensen = P·(mean(r-rf) - β·mean(b-rf)).
    rf = 0.03
    rf_p = (1 + rf) ** (1 / 252) - 1
    s_rf = st.perf_summary(r, benchmark=b, rf=rf)
    expected_alpha = ((r - rf_p).mean() - 1.5 * (b - rf_p).mean()) * 252
    assert s_rf["alpha"] == pytest.approx(expected_alpha)


def test_perf_summary_nan_handling_and_degenerate_inputs() -> None:
    rng = np.random.default_rng(2)
    r = pd.Series(rng.normal(0.0005, 0.01, 300), index=_dates(300))
    with_nan = r.copy()
    with_nan.iloc[[3, 50, 51, 200]] = np.nan
    a = st.perf_summary(with_nan)
    b = st.perf_summary(with_nan.dropna())
    assert a["n_obs"] == 296
    for key in ("cagr", "vol", "sharpe", "sortino", "max_drawdown", "var_95", "psr"):
        assert a[key] == pytest.approx(b[key])

    empty = st.perf_summary(pd.Series([], dtype=float))
    assert empty["n_obs"] == 0 and math.isnan(empty["sharpe"]) and empty["start"] is None

    const = st.perf_summary(pd.Series([0.001] * 50))
    assert math.isnan(const["sharpe"]) and const["max_drawdown"] == 0.0
    assert const["max_drawdown_duration"] == 0 and math.isnan(const["calmar"])

    # Drawdown dès la première séance et jamais récupéré : dates manquantes = None.
    falling = st.perf_summary(pd.Series([-0.02, 0.01, -0.03], index=_dates(3)))
    assert falling["max_drawdown_peak"] is None and falling["max_drawdown_recovery"] is None
    assert falling["max_drawdown_trough"] == _dates(3)[2]
    assert falling["max_drawdown_duration"] == 3

    with pytest.raises(ValueError):
        st.perf_summary(pd.Series([0.01, np.inf]))
    assert "var_99" in st.perf_summary(r, var_level=0.99)


def test_perf_summary_benchmark_alignment_on_index() -> None:
    rng = np.random.default_rng(3)
    idx = _dates(400)
    b = pd.Series(rng.normal(0, 0.01, 400), index=idx)
    r = 2.0 * b
    # Benchmark plus long et désordonné : l'alignement se fait sur les dates.
    longer = pd.concat([b, pd.Series([0.5], index=[idx[-1] + pd.Timedelta(days=3)])])
    s = st.perf_summary(r, benchmark=longer.sample(frac=1.0, random_state=0).sort_index())
    assert s["n_obs_common"] == 400
    assert s["beta"] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# PSR, DSR, MinTRL
# ---------------------------------------------------------------------------


def test_probabilistic_sharpe_matches_hand_formula() -> None:
    rng = np.random.default_rng(4)
    x = rng.standard_t(df=5, size=500) * 0.01 + 0.0008
    for sr_star in (0.0, 0.02, -0.01):
        assert st.probabilistic_sharpe(x, sr_star) == pytest.approx(_psr_by_hand(x, sr_star))
    # Référence annualisée : 0,5 par an ↔ 0,5/sqrt(252) par séance.
    assert st.probabilistic_sharpe(x, 0.5, periods_per_year=252) == pytest.approx(
        _psr_by_hand(x, 0.5 / math.sqrt(252))
    )
    # NaN ignorés.
    x_nan = np.concatenate([x, [np.nan, np.nan]])
    assert st.probabilistic_sharpe(x_nan) == pytest.approx(st.probabilistic_sharpe(x))
    assert math.isnan(st.probabilistic_sharpe([0.01, 0.02]))


def test_probabilistic_sharpe_is_calibrated_under_skewness() -> None:
    """Sous H0 : SR = SR*, P(PSR > 0,95) ≈ 5 % malgré une asymétrie de -2.

    La version « normale » (γ3 = 0, γ4 = 3) sous-estime la variance du Sharpe
    et rejette trop souvent ; la correction de Mertens / Bailey-López de Prado
    rétablit le niveau nominal.
    """
    rng = np.random.default_rng(7)
    nsim, n, mu = 2000, 750, 0.1
    X = -(rng.exponential(1.0, (nsim, n)) - 1.0) + mu  # vrai SR = 0,1 par période
    psr = np.array([st.probabilistic_sharpe(x, mu) for x in X])
    adjusted_rate = float(np.mean(psr > 0.95))
    sr = X.mean(axis=1) / X.std(axis=1, ddof=1)
    naive = sps.norm.cdf((sr - mu) * math.sqrt(n - 1) / np.sqrt(1 + 0.5 * sr**2))
    naive_rate = float(np.mean(naive > 0.95))
    assert 0.03 <= adjusted_rate <= 0.065
    assert naive_rate > adjusted_rate + 0.01


def test_expected_max_sharpe_gumbel_vs_monte_carlo() -> None:
    rng = np.random.default_rng(11)
    for n_trials in (10, 100, 1000):
        mc = rng.standard_normal((10_000, n_trials)).max(axis=1).mean()
        approx = st.expected_max_sharpe(n_trials, 1.0)
        assert approx == pytest.approx(mc, rel=0.03)
    g = st.EULER_MASCHERONI
    hand = 0.3 + 0.2 * (
        (1 - g) * sps.norm.ppf(1 - 1 / 50) + g * sps.norm.ppf(1 - 1 / (50 * math.e))
    )
    assert st.expected_max_sharpe(50, 0.04, sr_mean=0.3) == pytest.approx(hand)
    assert st.expected_max_sharpe(1, 0.04, sr_mean=0.3) == pytest.approx(0.3)
    with pytest.raises(ValueError):
        st.expected_max_sharpe(0, 1.0)


def test_deflated_sharpe() -> None:
    rng = np.random.default_rng(5)
    x = rng.normal(0.001, 0.01, 1000)
    var = 0.5**2 / 252  # dispersion des Sharpe entre essais : 0,5 annualisé
    assert st.deflated_sharpe(x, 1, var) == pytest.approx(st.probabilistic_sharpe(x, 0.0))
    sr0 = st.expected_max_sharpe(100, var)
    assert st.deflated_sharpe(x, 100, var) == pytest.approx(_psr_by_hand(x, sr0))
    # Unités annualisées équivalentes.
    assert st.deflated_sharpe(x, 100, 0.25, periods_per_year=252) == pytest.approx(
        st.deflated_sharpe(x, 100, var)
    )
    values = [st.deflated_sharpe(x, n, var) for n in (1, 10, 100, 1000)]
    assert all(a > b for a, b in itertools.pairwise(values))
    assert values[-1] < st.probabilistic_sharpe(x)


def test_min_track_record_length() -> None:
    rng = np.random.default_rng(6)
    x = rng.standard_t(df=6, size=800) * 0.01 + 0.001
    sr, g3, g4 = _moments_by_hand(x)
    z = sps.norm.ppf(0.95)
    expected = 1 + (1 - g3 * sr + (g4 - 1) / 4 * sr**2) * (z / sr) ** 2
    mtrl = st.min_track_record_length(x, 0.0, alpha=0.05)
    assert mtrl == pytest.approx(expected)
    # Par construction, PSR évalué avec n = MinTRL vaut exactement 1 - α.
    zz = sr * math.sqrt(mtrl - 1) / math.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr**2)
    assert sps.norm.cdf(zz) == pytest.approx(0.95)
    assert st.min_track_record_length(x, sr_benchmark=10.0, periods_per_year=252) == math.inf
    assert st.min_track_record_length(-x) == math.inf
    with pytest.raises(ValueError):
        st.min_track_record_length(x, alpha=1.5)


# ---------------------------------------------------------------------------
# Sharpe de Lo
# ---------------------------------------------------------------------------


def test_lo_adjusted_sharpe_matches_statsmodels_acf() -> None:
    from statsmodels.tsa.stattools import acf

    rng = np.random.default_rng(8)
    e = rng.normal(0, 0.01, 3000)
    x = np.empty_like(e)
    x[0] = e[0]
    for t in range(1, x.size):
        x[t] = 0.3 * x[t - 1] + e[t]
    x += 0.0004
    q, T = 10, 252
    rho = acf(x, nlags=q, fft=False)[1:]
    k = np.arange(1, q + 1)
    eta = T / math.sqrt(T + 2 * np.sum((T - k) * rho))
    expected = eta * x.mean() / x.std(ddof=1)
    assert st.lo_adjusted_sharpe(x, q=q) == pytest.approx(expected)
    # AR(1) φ = 0,3 : facteur ≈ sqrt((1-φ)/(1+φ)) = 0,734 par rapport à sqrt(252).
    naive = x.mean() / x.std(ddof=1) * math.sqrt(T)
    assert st.lo_adjusted_sharpe(x, q=q) / naive == pytest.approx(math.sqrt(0.7 / 1.3), abs=0.05)


def test_lo_adjusted_sharpe_iid_is_close_to_naive() -> None:
    rng = np.random.default_rng(9)
    x = rng.normal(0.0005, 0.01, 5000)
    naive = st.sharpe_ratio(x)
    assert st.lo_adjusted_sharpe(x, q=5) == pytest.approx(naive, rel=0.05)
    assert math.isnan(st.lo_adjusted_sharpe(x[:5], q=5))
    with pytest.raises(ValueError):
        st.lo_adjusted_sharpe(x, q=0)


# ---------------------------------------------------------------------------
# Bootstrap stationnaire
# ---------------------------------------------------------------------------


def test_stationary_bootstrap_reproducible() -> None:
    rng = np.random.default_rng(10)
    x = rng.normal(0, 0.01, 500)
    a = st.stationary_bootstrap(x, np.mean, n_boot=300, mean_block=10, seed=3)
    b = st.stationary_bootstrap(x, np.mean, n_boot=300, mean_block=10, seed=3)
    c = st.stationary_bootstrap(x, np.mean, n_boot=300, mean_block=10, seed=4)
    assert a.shape == (300,)
    np.testing.assert_array_equal(a, b)
    assert not np.allclose(a, c)
    # Les premières répliques ne dépendent pas du nombre total de répliques.
    d = st.stationary_bootstrap(x, np.mean, n_boot=100, mean_block=10, seed=3)
    np.testing.assert_array_equal(a[:100], d)
    # Statistique vectorielle.
    v = st.stationary_bootstrap(x, lambda s: np.array([s.mean(), s.std()]), n_boot=50)
    assert v.shape == (50, 2)


def test_stationary_bootstrap_block_length_is_geometric() -> None:
    n, b = 1000, 10
    idx = np.arange(n, dtype=float)

    def continuation(sample: np.ndarray) -> float:
        step = np.diff(sample) % n
        return float(np.mean(step == 1))

    cont = st.stationary_bootstrap(idx, continuation, n_boot=200, mean_block=b, seed=0)
    # P(continuer le bloc) = 1 - 1/b (+ 1/(b·n) si le nouveau départ tombe juste après).
    assert cont.mean() == pytest.approx(1 - 1 / b + 1 / (b * n), abs=0.005)
    iid = st.stationary_bootstrap(idx, continuation, n_boot=200, mean_block=1, seed=0)
    assert iid.mean() == pytest.approx(1 / n, abs=0.002)
    # Chaque échantillon est une permutation avec remise des valeurs d'origine.
    same = st.stationary_bootstrap(idx, lambda s: float(np.isin(s, idx).all()), n_boot=20)
    assert same.min() == 1.0


def test_stationary_bootstrap_captures_serial_dependence() -> None:
    """Variance de la moyenne d'un AR(1) (φ = 0,5) : le bootstrap par blocs
    retrouve la variance de long terme de l'échantillon (≈ estimateur HAC),
    le bootstrap i.i.d. retombe sur σ²/n et la sous-estime d'un facteur
    ≈ (1-φ)/(1+φ)."""
    phi, n = 0.5, 2000
    block_sd, iid_sd = [], []
    for seed in range(12, 16):
        rng = np.random.default_rng(seed)
        e = rng.normal(0, 1, n)
        x = np.empty(n)
        x[0] = e[0] / math.sqrt(1 - phi**2)
        for t in range(1, n):
            x[t] = phi * x[t - 1] + e[t]
        block = st.stationary_bootstrap(x, np.mean, n_boot=1000, mean_block=50, seed=1).std()
        iid = st.stationary_bootstrap(x, np.mean, n_boot=1000, mean_block=1, seed=1).std()
        assert block == pytest.approx(math.sqrt(st.long_run_variance(x, 50) / n), rel=0.10)
        assert iid == pytest.approx(x.std() / math.sqrt(n), rel=0.10)
        block_sd.append(block)
        iid_sd.append(iid)
    true_sd = math.sqrt(1.0 / (1 - phi) ** 2 / n)  # σ_ε² / (1-φ)² / n
    assert float(np.mean(block_sd)) == pytest.approx(true_sd, rel=0.15)
    assert float(np.mean(iid_sd)) == pytest.approx(
        true_sd * math.sqrt((1 - phi) / (1 + phi)), rel=0.10
    )


def test_stationary_bootstrap_joint_rows_and_nan() -> None:
    rng = np.random.default_rng(13)
    b = rng.normal(0, 0.01, 600)
    r = 0.8 * b + rng.normal(0, 0.004, 600)
    df = pd.DataFrame({"r": r, "b": b})
    df.iloc[[5, 100], 0] = np.nan
    corr = st.stationary_bootstrap(df, lambda a: np.corrcoef(a[:, 0], a[:, 1])[0, 1], n_boot=200)
    full = df.dropna().corr().iloc[0, 1]
    assert np.median(corr) == pytest.approx(full, abs=0.02)
    with pytest.raises(ValueError):
        st.stationary_bootstrap(r, np.mean, mean_block=0.5)


# ---------------------------------------------------------------------------
# PBO / CSCV
# ---------------------------------------------------------------------------


def _pbo_brute_force(m: pd.DataFrame, n_splits: int) -> tuple[float, np.ndarray]:
    """Implémentation directe (boucles, pandas, scipy.rankdata)."""
    T, N = m.shape
    block = T // n_splits
    m = m.iloc[T - n_splits * block :]
    parts = [m.iloc[i * block : (i + 1) * block] for i in range(n_splits)]
    logits = []
    for combo in itertools.combinations(range(n_splits), n_splits // 2):
        train = pd.concat([parts[i] for i in combo])
        test = pd.concat([parts[i] for i in range(n_splits) if i not in combo])
        r_is = (train.mean() / train.std(ddof=1)).to_numpy()
        r_oos = (test.mean() / test.std(ddof=1)).to_numpy()
        best = int(np.argmax(r_is))
        w = sps.rankdata(r_oos)[best] / (N + 1)
        logits.append(math.log(w / (1 - w)))
    arr = np.array(logits)
    return float(np.mean(arr <= 0)), arr


def test_pbo_matches_brute_force_implementation() -> None:
    rng = np.random.default_rng(14)
    m = pd.DataFrame(rng.normal(0.0002, 0.01, (243, 7)))
    res = st.pbo_cscv(m, n_splits=6)
    pbo, logits = _pbo_brute_force(m, 6)
    assert res["n_combinations"] == math.comb(6, 3)
    assert res["block_size"] == 40
    assert res["pbo"] == pytest.approx(pbo)
    np.testing.assert_allclose(res["logits"], logits)
    np.testing.assert_allclose(res["logits"], np.log(res["oos_rank"] / (1 - res["oos_rank"])))

    # Une métrique fournie comme fonction donne le même résultat.
    def sharpe(a: np.ndarray) -> np.ndarray:
        return a.mean(axis=0) / a.std(axis=0, ddof=1) * math.sqrt(252)

    res_fn = st.pbo_cscv(m, n_splits=6, metric=sharpe)
    assert res_fn["pbo"] == pytest.approx(res["pbo"])
    np.testing.assert_allclose(res_fn["is_perf"], res["is_perf"])


def test_pbo_iid_noise_is_about_one_half() -> None:
    """Configurations sans signal, i.i.d. : en moyenne PBO ≈ 0,5."""
    values = []
    for seed in range(12):
        m = pd.DataFrame(np.random.default_rng(seed).normal(0, 0.01, (600, 20)))
        values.append(st.pbo_cscv(m, n_splits=10)["pbo"])
    assert 0.35 <= float(np.mean(values)) <= 0.65


def test_pbo_overfit_random_strategies_is_close_to_one() -> None:
    """Stratégies aléatoires de même performance sur l'échantillon complet :
    la meilleure IS est mécaniquement la pire OOS → PBO ≈ 1 et dégradation
    nette (pente négative, perte OOS fréquente)."""
    rng = np.random.default_rng(15)
    noise = pd.DataFrame(rng.normal(0, 0.01, (1000, 20)))
    overfit = noise - noise.mean()
    res = st.pbo_cscv(overfit, n_splits=16)
    assert res["n_combinations"] == 12870
    assert res["pbo"] > 0.95
    assert res["degradation_slope"] < 0
    assert res["prob_oos_loss"] > 0.95


def test_pbo_true_signal_is_low() -> None:
    rng = np.random.default_rng(16)
    m = pd.DataFrame(rng.normal(0, 0.01, (1000, 20)), columns=[f"cfg{i}" for i in range(20)])
    m["cfg0"] = rng.normal(0.002, 0.01, 1000)  # Sharpe annuel ≈ 3
    res = st.pbo_cscv(m, n_splits=16)
    assert res["pbo"] < 0.05
    assert res["selected"].index[0] == "cfg0"
    assert res["selected"].iloc[0] > 0.95
    assert res["prob_oos_loss"] < 0.05


def test_pbo_nan_and_validation() -> None:
    rng = np.random.default_rng(17)
    m = pd.DataFrame(rng.normal(0, 0.01, (400, 6)))
    m.iloc[:50, 2] = np.nan  # configuration lancée plus tard
    res = st.pbo_cscv(m, n_splits=8)
    assert np.isfinite(res["logits"]).all()
    assert 0.0 <= res["pbo"] <= 1.0
    sub = st.pbo_cscv(m, n_splits=8, max_combinations=20, seed=1)
    assert sub["n_combinations"] == 20
    with pytest.raises(ValueError):
        st.pbo_cscv(m, n_splits=7)
    with pytest.raises(ValueError):
        st.pbo_cscv(m.iloc[:, :1], n_splits=8)
    with pytest.raises(ValueError):
        st.pbo_cscv(m.iloc[:10], n_splits=8)


# ---------------------------------------------------------------------------
# Bêta de Dimson
# ---------------------------------------------------------------------------


def test_dimson_beta_recovers_known_lag_structure() -> None:
    rng = np.random.default_rng(18)
    n = 3000
    mkt = pd.Series(rng.normal(0, 0.01, n), index=_dates(n))
    asset = 0.5 * mkt + 0.7 * mkt.shift(1) + rng.normal(0, 0.005, n)
    betas = st.dimson_betas(asset, mkt, lags=2)
    assert list(betas.index) == [-2, -1, 0, 1, 2]
    assert betas[0] == pytest.approx(0.5, abs=0.03)
    assert betas[1] == pytest.approx(0.7, abs=0.03)
    assert st.dimson_beta(asset, mkt, lags=2) == pytest.approx(1.2, abs=0.06)
    ols = np.polyfit(mkt.iloc[1:], asset.iloc[1:], 1)[0]
    assert st.dimson_beta(asset.iloc[1:], mkt.iloc[1:], lags=0) == pytest.approx(ols)
    assert ols < 0.6


def test_dimson_beta_corrects_stale_prices() -> None:
    """Titre peu liquide : prix observé seulement 35 % des séances. Le bêta
    MCO est biaisé vers 0, le bêta de Dimson retrouve le vrai bêta (1)."""
    rng = np.random.default_rng(19)
    n = 4000
    m = rng.normal(0.0002, 0.01, n)
    true_log = 1.0 * m + rng.normal(0, 0.01, n)
    traded = rng.random(n) < 0.35
    log_price = np.cumsum(true_log)
    observed = pd.Series(np.where(traded, log_price, np.nan)).ffill().fillna(0.0)
    obs_ret = observed.diff().fillna(0.0)
    mkt = pd.Series(m)
    ols = st.dimson_beta(obs_ret, mkt, lags=0)
    dim = st.dimson_beta(obs_ret, mkt, lags=8)
    assert ols < 0.5
    assert dim == pytest.approx(1.0, abs=0.12)


def test_dimson_beta_nan_keeps_calendar() -> None:
    rng = np.random.default_rng(20)
    n = 1500
    mkt = pd.Series(rng.normal(0, 0.01, n), index=_dates(n))
    asset = 0.9 * mkt.shift(1) + rng.normal(0, 0.003, n)
    holes = asset.copy()
    holes.iloc[rng.choice(n, 300, replace=False)] = np.nan
    betas = st.dimson_betas(holes, mkt, lags=1)
    assert betas[1] == pytest.approx(0.9, abs=0.05)
    assert abs(betas[0]) < 0.05
    assert math.isnan(st.dimson_beta(mkt.iloc[:4], mkt.iloc[:4], lags=2))


# ---------------------------------------------------------------------------
# Newey-West et coefficient d'information
# ---------------------------------------------------------------------------


def test_newey_west_matches_statsmodels_hac() -> None:
    import statsmodels.api as sm

    rng = np.random.default_rng(21)
    e = rng.normal(0, 1, 800)
    x = np.convolve(e, [1.0, 0.6, 0.3])[:800] + 0.1
    for lags in (0, 3, 10):
        fit = sm.OLS(x, np.ones_like(x)).fit(
            cov_type="HAC", cov_kwds={"maxlags": lags, "use_correction": False}
        )
        assert st.newey_west_tstat(x, lags=lags) == pytest.approx(fit.tvalues[0])
    auto = st.newey_west_lags(800)
    assert auto == math.floor(4 * (800 / 100) ** (2 / 9))
    fit = sm.OLS(x, np.ones_like(x)).fit(
        cov_type="HAC", cov_kwds={"maxlags": auto, "use_correction": False}
    )
    assert st.newey_west_tstat(x) == pytest.approx(fit.tvalues[0])
    # Lags = 0 : t usuel avec variance « population ».
    assert st.newey_west_tstat(x, lags=0) == pytest.approx(x.mean() / (x.std() / math.sqrt(800)))
    assert st.newey_west_tstat(x, lags=3, mu0=0.1) == pytest.approx(
        (x.mean() - 0.1) / math.sqrt(st.long_run_variance(x, 3) / 800)
    )
    assert math.isnan(st.newey_west_tstat([1.0, 1.0, 1.0]))


def test_ic_summary() -> None:
    rng = np.random.default_rng(22)
    ic = pd.Series(rng.normal(0.03, 0.1, 500), index=_dates(500))
    ic.iloc[[10, 20]] = np.nan
    x = ic.dropna().to_numpy()
    s = st.ic_summary(ic)
    assert s["n_obs"] == 498
    assert s["mean"] == pytest.approx(x.mean())
    assert s["std"] == pytest.approx(x.std(ddof=1))
    assert s["ir"] == pytest.approx(x.mean() / x.std(ddof=1))
    assert s["t_stat_naive"] == pytest.approx(x.mean() / (x.std(ddof=1) / math.sqrt(498)))
    assert s["nw_lags"] == st.newey_west_lags(498)
    assert s["t_stat_nw"] == pytest.approx(st.newey_west_tstat(x, lags=st.newey_west_lags(498)))
    assert s["p_value_nw"] == pytest.approx(2 * sps.norm.sf(abs(s["t_stat_nw"])))
    assert s["hit_rate"] == pytest.approx(np.mean(x > 0))
    # IC sur rendements à 20 séances qui se chevauchent : retards ≥ 2h.
    s20 = st.ic_summary(ic, horizon=20)
    assert s20["nw_lags"] == 40
    assert st.ic_summary(ic, lags=3)["nw_lags"] == 3


def test_ic_summary_overlap_inflates_naive_t() -> None:
    """IC d'un signal nul évalué sur rendements à 20 jours qui se chevauchent :
    le t naïf est trompeur, le t de Newey-West reste raisonnable."""
    rng = np.random.default_rng(23)
    daily = rng.normal(0, 0.1, 3020)
    overlapping = pd.Series(np.convolve(daily, np.ones(20) / 20, mode="valid"))
    s = st.ic_summary(overlapping, horizon=20)
    assert abs(s["t_stat_nw"]) < abs(s["t_stat_naive"]) / 2.5


# ---------------------------------------------------------------------------
# Haircut de Harvey-Liu-Zhu
# ---------------------------------------------------------------------------


def test_adjust_pvalues_matches_statsmodels() -> None:
    from statsmodels.stats.multitest import multipletests

    rng = np.random.default_rng(24)
    p = np.concatenate([rng.uniform(0, 0.01, 5), rng.uniform(0, 1, 25)])
    rng.shuffle(p)
    for ours, theirs in (
        ("bonferroni", "bonferroni"),
        ("holm", "holm"),
        ("bh", "fdr_bh"),
        ("bhy", "fdr_by"),
    ):
        expected = multipletests(p, method=theirs)[1]
        np.testing.assert_allclose(st.adjust_pvalues(p, ours), expected, rtol=1e-12)
    with pytest.raises(ValueError):
        st.adjust_pvalues([0.1, 1.2])
    with pytest.raises(ValueError):
        st.adjust_pvalues([0.1], method="nope")


def test_haircut_sharpe() -> None:
    n_obs = 1260  # 5 ans
    years = n_obs / 252
    # Un seul test : aucune décote.
    for method in ("bonferroni", "holm", "bhy"):
        assert st.haircut_sharpe(1.0, n_obs, 1, method=method) == pytest.approx(1.0)
    # Bonferroni à la main.
    sr = 1.5
    t = sr * math.sqrt(years)
    p = 2 * sps.norm.sf(t)
    p_adj = min(10 * p, 1.0)
    expected = sps.norm.isf(p_adj / 2) / math.sqrt(years)
    assert st.haircut_sharpe(sr, n_obs, 10, method="bonferroni") == pytest.approx(expected)
    # Exemple : SR 1 sur 5 ans, 100 essais → plus rien de significatif.
    assert st.haircut_sharpe(1.0, n_obs, 100, method="bonferroni") == pytest.approx(0.0, abs=1e-12)
    # Holm et BHY avec les p-valeurs réelles des autres tests (statsmodels).
    from statsmodels.stats.multitest import multipletests

    others = np.array([0.0001, 0.002, 0.03, 0.2, 0.5, 0.7, 0.8, 0.9, 0.95])
    for ours, theirs in (("holm", "holm"), ("bhy", "fdr_by")):
        d = st.haircut_sharpe_details(sr, n_obs, 10, method=ours, other_pvalues=others)
        p_sm = multipletests(np.concatenate([[p], others]), method=theirs)[1][0]
        assert d["p_value"] == pytest.approx(p)
        assert d["p_value_adjusted"] == pytest.approx(p_sm)
        assert d["sr_haircut"] == pytest.approx(sps.norm.isf(p_sm / 2) / math.sqrt(years))
        assert 0.0 <= d["haircut"] <= 1.0
    bonf = st.haircut_sharpe(sr, n_obs, 10, method="bonferroni")
    holm = st.haircut_sharpe(sr, n_obs, 10, method="holm", other_pvalues=others)
    assert holm >= bonf
    # Symétrie pour un Sharpe négatif.
    assert st.haircut_sharpe(-sr, n_obs, 10, method="bonferroni") == pytest.approx(-bonf)
    with pytest.raises(ValueError):
        st.haircut_sharpe(sr, n_obs, 10, other_pvalues=[0.1, 0.2])


# ---------------------------------------------------------------------------
# Drawdowns
# ---------------------------------------------------------------------------


def test_rolling_drawdown_and_episodes(small_returns: pd.Series) -> None:
    dd = st.rolling_drawdown(small_returns)
    wealth = np.cumprod(1 + small_returns.to_numpy())
    peak = np.maximum.accumulate(np.maximum(wealth, 1.0))
    np.testing.assert_allclose(dd.to_numpy(), wealth / peak - 1)
    assert dd.index.equals(small_returns.index)
    # Perte dès la première séance : drawdown mesuré contre le capital initial.
    first_loss = st.rolling_drawdown(pd.Series([-0.1, 0.05]))
    np.testing.assert_allclose(first_loss.to_numpy(), [-0.1, 0.9 * 1.05 - 1])
    # Fenêtre : plus haut des 2 dernières valeurs de capital.
    w = st.rolling_drawdown(small_returns, window=2)
    full_w = np.concatenate([[1.0], wealth])
    expected = [full_w[i + 1] / max(full_w[max(0, i) : i + 2]) - 1 for i in range(6)]
    np.testing.assert_allclose(w.to_numpy(), expected)
    # NaN = rendement nul.
    with_nan = small_returns.copy()
    with_nan.iloc[2] = np.nan
    assert st.rolling_drawdown(with_nan).notna().all()

    # Capital : 0,9 | 1,08 | 1,026 | 0,9747 | 0,9942 → deux épisodes.
    idx = _dates(5)
    ep = st.drawdown_episodes(pd.Series([-0.1, 0.2, -0.05, -0.05, 0.02], index=idx))
    assert list(ep["length"]) == [1, 3]
    first, second = ep.iloc[0], ep.iloc[1]
    assert first["depth"] == pytest.approx(-0.1)
    assert pd.isna(first["peak"]) and bool(first["recovered"]) and first["recovery"] == idx[1]
    assert second["depth"] == pytest.approx(0.95 * 0.95 - 1)
    assert second["peak"] == idx[1] and second["trough"] == idx[3]
    assert not bool(second["recovered"]) and pd.isna(second["recovery"])
    assert second["to_trough"] == 2
    assert len(st.drawdown_episodes(pd.Series([-0.1, 0.2, -0.05, -0.05, 0.02]), top=1)) == 1


def test_rolling_max_drawdown_matches_brute_force() -> None:
    rng = np.random.default_rng(25)
    r = pd.Series(rng.normal(0, 0.02, 300), index=_dates(300))
    window = 40
    got = st.rolling_max_drawdown(r, window=window)
    assert got.iloc[: window - 1].isna().all()
    for end in (window - 1, 100, 299):
        chunk = r.iloc[end - window + 1 : end + 1]
        expected = st.perf_summary(chunk)["max_drawdown"]
        assert got.iloc[end] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Intégration « smoke » sur le panel réel (si disponible)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not PANEL.exists(), reason="panel parquet absent")
def test_smoke_real_panel() -> None:
    eq = pd.read_parquet(PANEL)
    if not {"date", "symbol", "close"}.issubset(eq.columns):
        pytest.skip("schéma du panel incomplet")
    close = eq.pivot_table(
        index="date", columns="symbol", values="close", aggfunc="last"
    ).sort_index()
    rets = close / close.shift(1) - 1.0
    rets = rets.where(np.isfinite(rets))
    if len(rets) < 60:
        pytest.skip("historique trop court")
    market = rets.mean(axis=1, skipna=True)
    liquid = rets.notna().sum().idxmax()
    summary = st.perf_summary(rets[liquid], benchmark=market)
    assert summary["n_obs"] > 0
    assert math.isfinite(summary["vol"])
    assert math.isfinite(summary["beta_dimson"])
    assert summary["max_drawdown"] <= 0
    boot = st.stationary_bootstrap(market, lambda a: a.mean(), n_boot=50)
    assert np.isfinite(boot).all()
    if rets.shape[1] >= 4 and len(rets) >= 160:
        res = st.pbo_cscv(rets.iloc[:, :8], n_splits=8)
        assert 0.0 <= res["pbo"] <= 1.0

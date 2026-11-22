"""Tests de brvm_alpha.quant.features, scoring et regime.

Trois familles de tests, toutes déterministes (graines fixes) :

1. **Absence d'anticipation** : on modifie toutes les données à partir d'une
   date ``t0`` ; aucune caractéristique, aucun score transversal et aucun
   régime daté avant ``t0`` ne doit changer.
2. **Propriétés connues** : momentum d'une série géométrique, IC = 1 pour un
   signal parfait, moyenne nulle par groupe après neutralisation, etc.
3. **Calculs indépendants** : comparaison avec une formule écrite à la main,
   avec ``brvm_alpha.quant.stats.dimson_beta`` ou avec statsmodels.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm, spearmanr

from brvm_alpha.quant import features as ft
from brvm_alpha.quant import regime as rg
from brvm_alpha.quant import scoring as sc
from brvm_alpha.quant import stats as st

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "data" / "panel" / "equities.parquet"


# ---------------------------------------------------------------------------
# Données synthétiques
# ---------------------------------------------------------------------------


def make_panels(T: int = 640, N: int = 10, seed: int = 0) -> dict[str, pd.DataFrame]:
    """Panel synthétique « type BRVM » : échanges rares, prix périmés, limites ±7,5 %,
    dividendes annuels, un titre introduit en cours de période, une suspension."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2019-01-02", periods=T)
    syms = [f"S{i:02d}" for i in range(N)]
    p_trade = rng.uniform(0.3, 0.95, N)
    traded = rng.random((T, N)) < p_trade[None, :]
    traded[0] = True
    mkt = rng.normal(0.0004, 0.008, T)
    betas = rng.uniform(0.3, 1.5, N)
    r = np.clip(betas[None, :] * mkt[:, None] + rng.normal(0, 0.02, (T, N)), -0.075, 0.075)
    r[rng.random((T, N)) < 0.01] = 0.075  # quelques plafonds hauts
    r[rng.random((T, N)) < 0.01] = -0.075  # et bas
    r = np.where(traded, r, 0.0)
    close = 1000.0 * np.exp(np.cumsum(np.log1p(r), axis=0))
    # Dividendes : un paiement par an et par titre (titres pairs), en juin.
    div_amount = np.full((T, N), np.nan)
    div_date = np.full((T, N), np.datetime64("NaT", "ns"), dtype="datetime64[ns]")
    tr = close.copy()
    growth = np.ones((T, N))
    for j in range(0, N, 2):
        amt = 30.0 + 5 * j
        for year in sorted({d.year for d in dates}):
            pay = pd.Timestamp(year=year, month=6, day=14 + j % 5)
            rows = np.flatnonzero(dates >= pay)
            if rows.size == 0:
                continue
            k = rows[0]
            amt *= 1.05
            div_amount[k:, j] = amt
            div_date[k:, j] = np.datetime64(pay, "ns")
            growth[k:, j] *= 1.0 + amt / close[k, j]
        # Un dividende connu avant le début de l'échantillon.
        first = np.flatnonzero(~np.isnat(div_date[:, j]))
        if first.size:
            div_amount[: first[0], j] = 28.0
            div_date[: first[0], j] = np.datetime64("2018-06-15", "ns")
    tr = close * growth
    volume = np.where(traded, rng.integers(10, 2000, (T, N)), 0).astype(float)
    value = volume * close
    status = np.where(traded, "traded", "not_traded").astype(object)
    status[300:320, 3] = "suspended"
    volume[300:320, 3] = 0.0
    value[300:320, 3] = 0.0
    # Le dernier titre est introduit à la séance 150.
    for arr in (close, tr, volume, value):
        arr[:150, N - 1] = np.nan
    status[:150, N - 1] = None
    change = np.vstack([np.full((1, N), np.nan), np.diff(close, axis=0) / close[:-1]]) * 100
    per = np.where(rng.random((T, N)) < 0.1, -4.0, rng.uniform(4, 25, (T, N)))
    net_yield = np.where(np.isnan(div_amount), 0.0, div_amount / close * 100)

    def frame(a: np.ndarray) -> pd.DataFrame:
        return pd.DataFrame(a, index=dates, columns=syms)

    return {
        "close_adj": frame(close),
        "tr_index": frame(tr),
        "volume": frame(volume),
        "value": frame(value),
        "status": frame(status),
        "change_pct": frame(change),
        "per": frame(per),
        "net_yield_pct": frame(net_yield),
        "last_div_net": frame(div_amount),
        "last_div_date": frame(div_date),
        "ref_price": frame(np.vstack([close[:1], close[:-1]])),
    }


def market_level(panels: dict[str, pd.DataFrame]) -> pd.Series:
    r = panels["tr_index"].pct_change(fill_method=None).mean(axis=1).fillna(0.0)
    return 100.0 * (1.0 + r).cumprod()


def perturb_future(panels: dict[str, pd.DataFrame], t0: int, seed: int = 99) -> dict[str, pd.DataFrame]:
    """Copie de ``panels`` où toutes les lignes ``>= t0`` sont remplacées par du bruit."""
    rng = np.random.default_rng(seed)
    out: dict[str, pd.DataFrame] = {}
    for key, df in panels.items():
        new = df.copy()
        fut = new.index[t0:]
        if key in ("close_adj", "tr_index", "ref_price"):
            new.loc[fut] = df.loc[fut].to_numpy() * rng.uniform(0.5, 1.5, df.loc[fut].shape)
        elif key in ("volume", "value"):
            new.loc[fut] = rng.uniform(0, 1e6, df.loc[fut].shape)
        elif key == "status":
            new.loc[fut] = rng.choice(["traded", "not_traded", "suspended"], df.loc[fut].shape)
        elif key == "last_div_date":
            new.loc[fut] = np.datetime64("2030-01-01", "ns")
        else:
            new.loc[fut] = rng.normal(0, 20, df.loc[fut].shape)
        out[key] = new
    return out


@pytest.fixture(scope="module")
def panels() -> dict[str, pd.DataFrame]:
    return make_panels()


def _geometric_panels(T: int = 400, g: float = 1.001) -> dict[str, pd.DataFrame]:
    dates = pd.bdate_range("2020-01-01", periods=T)
    p = 100.0 * g ** np.arange(T)
    df = pd.DataFrame({"A": p, "B": 2 * p}, index=dates)
    return {"tr_index": df, "close_adj": df, "volume": pd.DataFrame(1.0, index=dates, columns=df.columns)}


# ---------------------------------------------------------------------------
# 1. Absence d'anticipation
# ---------------------------------------------------------------------------

FEATURE_CASES: dict[str, Callable[[dict[str, pd.DataFrame]], pd.DataFrame]] = {
    "returns_cal": lambda P: ft.returns(P),
    "returns_traded_log_gap": lambda P: ft.returns(P, kind="log", basis="traded", gap_adjust=True),
    "momentum_12_1": lambda P: ft.momentum(P, 252, 21, min_traded_fraction=0.3),
    "momentum_3_0": lambda P: ft.momentum_preset(P, "3-0"),
    "reversal_1w": lambda P: ft.short_term_reversal(P, 5),
    "volatility": lambda P: ft.volatility(P),
    "downside_vol": lambda P: ft.downside_vol(P),
    "beta_dimson": lambda P: ft.beta_dimson(P, market_level(P), window=120, lags=2, min_obs=40),
    "amihud": lambda P: ft.amihud_illiquidity(P),
    "zero_volume": lambda P: ft.zero_volume_fraction(P),
    "zero_return": lambda P: ft.zero_return_fraction(P),
    "median_value": lambda P: ft.median_value_traded(P),
    "adv": lambda P: ft.average_daily_value(P),
    "turnover_proxy": lambda P: ft.turnover_proxy(P),
    "limit_hits": lambda P: ft.limit_hits(P),
    "dist_high": lambda P: ft.distance_to_high(P),
    "div_yield": lambda P: ft.dividend_yield(P, max_dividend_age_days=500),
    "earn_yield": lambda P: ft.earnings_yield(P),
    "div_growth": lambda P: ft.dividend_growth(P),
    "div_stability": lambda P: ft.dividend_stability(P),
    "days_since_div": lambda P: ft.days_since_dividend(P),
    "seasonality": lambda P: ft.seasonality(P, min_years=1, month_offset=1),
}


@pytest.mark.parametrize("name", sorted(FEATURE_CASES))
def test_features_have_no_lookahead(panels: dict[str, pd.DataFrame], name: str) -> None:
    """Modifier toutes les données à partir de t0 ne change aucune valeur avant t0."""
    t0 = 520
    fn = FEATURE_CASES[name]
    base = fn(panels)
    pert = fn(perturb_future(panels, t0))
    assert base.shape == pert.shape
    pd.testing.assert_frame_equal(base.iloc[:t0], pert.iloc[:t0])
    # La caractéristique est effectivement calculée (pas un panel de NaN).
    assert base.iloc[:t0].notna().to_numpy().any()
    assert not np.isinf(base.to_numpy(dtype=float)).any()


def test_compute_features_library(panels: dict[str, pd.DataFrame]) -> None:
    lib = ft.compute_features(panels, market=market_level(panels))
    assert "beta_dimson_252" in lib and "mom_12_1" in lib and "seasonality" in lib
    for name, df in lib.items():
        assert df.shape == panels["close_adj"].shape, name
        assert not np.isinf(df.to_numpy(dtype=float)).any(), name
    sub = ft.compute_features({"tr_index": panels["tr_index"]})
    assert "mom_12_1" in sub and "amihud_63" not in sub and "dividend_yield" not in sub


def test_scores_and_regime_have_no_lookahead(panels: dict[str, pd.DataFrame]) -> None:
    t0 = 520
    pert = perturb_future(panels, t0)

    def pipeline(P: dict[str, pd.DataFrame]) -> pd.DataFrame:
        mom = sc.cross_sectional_zscore(ft.momentum(P, 126, 21))
        vol = sc.cross_sectional_zscore(-ft.volatility(P), method="zscore")
        groups = pd.Series(["A", "B"] * 5, index=P["close_adj"].columns)
        return sc.combine({"mom": sc.neutralize(mom, groups), "vol": vol}, {"mom": 0.6, "vol": 0.4})

    pd.testing.assert_frame_equal(pipeline(panels).iloc[:t0], pipeline(pert).iloc[:t0])

    # Régime (avec HMM) : trajectoire avec krach, coupée en t1 au milieu de la baisse.
    lvl = _regime_path()
    t1 = 700
    lvl_pert = lvl.copy()
    lvl_pert.iloc[t1:] = lvl.iloc[t1:] * np.linspace(1.0, 0.3, len(lvl) - t1)
    kw = {"vol_rank_window": 400, "hmm": True, "hmm_min_train": 250, "hmm_refit_every": 50, "confirm_days": 3}
    a = rg.market_regime(lvl, **kw)  # type: ignore[arg-type]
    b = rg.market_regime(lvl_pert, **kw)  # type: ignore[arg-type]
    pd.testing.assert_frame_equal(a.iloc[:t1], b.iloc[:t1])
    assert a["p_turbulent"].iloc[:t1].notna().any()
    assert not a.iloc[t1:].equals(b.iloc[t1:])


# ---------------------------------------------------------------------------
# 2. Caractéristiques : propriétés connues et calculs à la main
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("lookback", "skip"), [(252, 21), (126, 21), (63, 0)])
def test_momentum_geometric_series(lookback: int, skip: int) -> None:
    g = 1.001
    P = _geometric_panels(g=g)
    mom = ft.momentum(P, lookback, skip)
    expected = g ** (lookback - skip) - 1.0
    assert mom.iloc[:lookback].isna().all().all()
    np.testing.assert_allclose(mom.iloc[lookback:].to_numpy(), expected, rtol=1e-10)


def test_momentum_presets_and_validation() -> None:
    P = _geometric_panels()
    pd.testing.assert_frame_equal(ft.momentum_preset(P, "12-1"), ft.momentum(P, 252, 21))
    with pytest.raises(ValueError):
        ft.momentum(P, 21, 21)
    with pytest.raises(KeyError):
        ft.momentum_preset(P, "24-1")
    with pytest.raises(KeyError):
        ft.momentum({"close_adj": P["close_adj"]})


def test_momentum_min_traded_fraction() -> None:
    P = _geometric_panels(T=300)
    vol = P["volume"].copy()
    vol.iloc[:, 1] = 0.0
    vol.iloc[::10, 1] = 1.0  # B échangé une séance sur dix
    P = {**P, "volume": vol}
    mom = ft.momentum(P, 63, 0, min_traded_fraction=0.5)
    assert mom["A"].iloc[63:].notna().all()
    assert mom["B"].isna().all()


def test_returns_calendar_and_trade_to_trade() -> None:
    dates = pd.bdate_range("2021-01-04", periods=6)
    price = pd.DataFrame({"X": [100.0, 100.0, 100.0, 121.0, 121.0, 110.0]}, index=dates)
    status = pd.DataFrame({"X": ["traded", "not_traded", "not_traded", "traded", "not_traded", "traded"]}, index=dates)
    P = {"tr_index": price, "status": status}
    cal = ft.returns(P)["X"].to_numpy()
    np.testing.assert_allclose(cal[1:], [0.0, 0.0, 0.21, 0.0, 110 / 121 - 1])
    tt = ft.returns(P, basis="traded")["X"]
    assert tt.iloc[[0, 1, 2, 4]].isna().all()
    assert tt.iloc[3] == pytest.approx(0.21)
    assert tt.iloc[5] == pytest.approx(110 / 121 - 1)
    tl = ft.returns(P, kind="log", basis="traded", gap_adjust=True)["X"]
    assert tl.iloc[3] == pytest.approx(math.log(1.21) / math.sqrt(3))
    assert tl.iloc[5] == pytest.approx(math.log(110 / 121) / math.sqrt(2))
    assert ft.returns(P, basis="traded", max_gap=2)["X"].iloc[3] != ft.returns(P, basis="traded", max_gap=2)["X"].iloc[3]


def test_traded_mask_falls_back_to_volume() -> None:
    dates = pd.bdate_range("2021-01-04", periods=3)
    status = pd.DataFrame({"X": ["traded", None, "suspended"]}, index=dates)
    volume = pd.DataFrame({"X": [5.0, 3.0, 7.0]}, index=dates)
    m = ft.traded_mask({"status": status, "volume": volume})
    assert m["X"].tolist() == [True, True, False]
    assert ft.traded_mask({"volume": volume})["X"].all()
    with pytest.raises(KeyError):
        ft.traded_mask({})


def test_volatility_matches_numpy_and_gap_adjustment() -> None:
    rng = np.random.default_rng(1)
    T = 200
    dates = pd.bdate_range("2020-01-01", periods=T)
    r = rng.normal(0, 0.01, T)
    price = pd.DataFrame({"X": 100 * np.exp(np.cumsum(r))}, index=dates)
    P = {"tr_index": price, "volume": pd.DataFrame({"X": np.ones(T)}, index=dates)}
    vol = ft.volatility(P, window=60, min_obs=60)
    expected = np.std(r[T - 60 :], ddof=1) * math.sqrt(252)
    assert vol["X"].iloc[-1] == pytest.approx(expected, rel=1e-10)
    assert vol["X"].iloc[:60].isna().all()  # première rendement manquant -> 60 obs à la ligne 60

    # Titre échangé une séance sur 4 : la normalisation par sqrt(écart) corrige
    # le biais des rendements d'échange à échange (vol d'une marche aléatoire).
    T2 = 4000
    d2 = pd.bdate_range("2000-01-03", periods=T2)
    r2 = rng.normal(0, 0.01, T2)
    p2 = pd.DataFrame({"X": 100 * np.exp(np.cumsum(r2))}, index=d2)
    v2 = pd.DataFrame({"X": (np.arange(T2) % 4 == 0).astype(float)}, index=d2)
    P2 = {"tr_index": p2, "volume": v2}
    raw = ft.volatility(P2, window=T2, min_obs=100, gap_adjust=False)["X"].iloc[-1]
    adj = ft.volatility(P2, window=T2, min_obs=100, gap_adjust=True)["X"].iloc[-1]
    true = 0.01 * math.sqrt(252)
    assert adj == pytest.approx(true, rel=0.06)
    assert raw == pytest.approx(2 * true, rel=0.06)


def test_downside_vol_by_hand() -> None:
    dates = pd.bdate_range("2021-01-04", periods=6)
    r = np.array([np.nan, 0.02, -0.01, 0.03, -0.04, 0.01])
    price = pd.DataFrame({"X": 100 * np.exp(np.nancumsum(r))}, index=dates)
    P = {"tr_index": price, "volume": pd.DataFrame({"X": np.ones(6)}, index=dates)}
    dv = ft.downside_vol(P, window=5, min_obs=5, annualize=False)["X"].iloc[-1]
    neg = np.minimum(r[1:], 0.0)
    assert dv == pytest.approx(math.sqrt(np.mean(neg**2)), rel=1e-10)


def test_beta_dimson_matches_stats_module(panels: dict[str, pd.DataFrame]) -> None:
    mkt = market_level(panels)
    window, lags = 120, 2
    beta = ft.beta_dimson(panels, mkt, window=window, lags=lags, min_obs=40)
    r = panels["tr_index"] / panels["tr_index"].shift(1) - 1
    m = mkt / mkt.shift(1) - 1
    t = 400
    end = t - lags  # fenêtre de la régression publiée en t
    for sym in ["S00", "S03", "S09"]:
        a = r[sym].copy()
        keep = np.zeros(len(a), dtype=bool)
        keep[end - window + 1 : end + 1] = True
        a[~keep] = np.nan
        assert beta[sym].iloc[t] == pytest.approx(st.dimson_beta(a, m, lags=lags), rel=1e-8, abs=1e-10)


def test_beta_dimson_recovers_true_beta() -> None:
    rng = np.random.default_rng(3)
    T = 800
    dates = pd.bdate_range("2018-01-01", periods=T)
    m = rng.normal(0, 0.01, T)
    # Le titre réagit à 60 % le jour même et 40 % le lendemain : bêta total 1,5.
    a = 1.5 * (0.6 * m + 0.4 * np.concatenate([[0.0], m[:-1]])) + rng.normal(0, 0.004, T)
    price = pd.DataFrame({"X": 100 * np.cumprod(1 + a)}, index=dates)
    level = pd.Series(100 * np.cumprod(1 + m), index=dates)
    b_dimson = ft.beta_dimson({"tr_index": price}, level, window=500, lags=1, min_obs=200)["X"].iloc[-1]
    b_ols = ft.beta_dimson({"tr_index": price}, level, window=500, lags=0, min_obs=200)["X"].iloc[-1]
    assert b_dimson == pytest.approx(1.5, abs=0.08)
    assert b_ols == pytest.approx(0.9, abs=0.08)  # biais vers zéro du MCO
    with pytest.raises(ValueError):
        ft.beta_dimson({"tr_index": price}, level, window=10, min_obs=60)


def test_amihud_zero_volume_median_value_by_hand() -> None:
    dates = pd.bdate_range("2021-01-04", periods=6)
    price = pd.DataFrame({"X": [100.0, 110.0, 110.0, 99.0, 99.0, 99.0]}, index=dates)
    volume = pd.DataFrame({"X": [10.0, 10.0, 0.0, 20.0, 0.0, 5.0]}, index=dates)
    value = price * volume
    status = pd.DataFrame({"X": ["traded", "traded", "not_traded", "traded", "suspended", "traded"]}, index=dates)
    P = {"tr_index": price, "close_adj": price, "volume": volume, "value": value, "status": status}
    ill = ft.amihud_illiquidity(P, window=6, min_obs=2, unit=1.0)["X"].iloc[-1]
    expected = np.mean([0.10 / 1100.0, 0.10 / 1980.0, 0.0 / 495.0])
    assert ill == pytest.approx(expected, rel=1e-12)
    zv = ft.zero_volume_fraction(P, window=6, min_obs=6)["X"].iloc[-1]
    assert zv == pytest.approx(2 / 6)
    mv = ft.median_value_traded(P, window=6, min_obs=6)["X"].iloc[-1]
    assert mv == pytest.approx(np.median(value["X"].to_numpy()))
    mv_traded = ft.median_value_traded(P, window=6, min_obs=1, include_zero=False)["X"].iloc[-1]
    assert mv_traded == pytest.approx(np.median([1000.0, 1100.0, 1980.0, 495.0]))
    adv = ft.average_daily_value(P, window=6, min_obs=6)["X"].iloc[-1]
    assert adv == pytest.approx(value["X"].mean())
    zr = ft.zero_return_fraction(P, window=5, min_obs=5)["X"].iloc[-1]
    assert zr == pytest.approx(3 / 5)


def test_turnover_measures() -> None:
    dates = pd.bdate_range("2021-01-04", periods=40)
    vol = pd.DataFrame({"X": [10.0] * 30 + [40.0] * 10}, index=dates)
    P = {"volume": vol}
    rel = ft.turnover_proxy(P, window=10, base_window=40, min_obs=40)["X"].iloc[-1]
    assert rel == pytest.approx(40.0 / ((30 * 10 + 10 * 40) / 40))
    to = ft.turnover(P, pd.Series({"X": 1000.0}), window=10, min_obs=10)["X"].iloc[-1]
    assert to == pytest.approx(0.04)


def test_limit_hits_counts_and_sign() -> None:
    dates = pd.bdate_range("2021-01-04", periods=6)
    change = pd.DataFrame({"X": [np.nan, 7.5, 7.4, -7.5, 7.5, 2.0], "Y": [np.nan, -7.5, -7.5, 0.0, 0.0, 7.0]}, index=dates)
    P = {"change_pct": change}
    up = ft.limit_hits(P, window=5, side="up")
    down = ft.limit_hits(P, window=5, side="down")
    net = ft.limit_hits(P, window=5, side="net")
    both = ft.limit_hits(P, window=5, side="both")
    assert up["X"].iloc[-1] == 3 and down["X"].iloc[-1] == 1  # 7,4 % >= 7,3 % compte
    assert net["X"].iloc[-1] == 2 and both["X"].iloc[-1] == 4
    assert net["Y"].iloc[-1] == -2  # 7,0 % < 7,3 % ne compte pas
    custom = ft.limit_hits(P, window=5, side="up", threshold=0.0745)
    assert custom["X"].iloc[-1] == 2


def test_distance_to_high() -> None:
    dates = pd.bdate_range("2021-01-04", periods=6)
    price = pd.DataFrame({"X": [100.0, 120.0, 110.0, 90.0, 130.0, 117.0]}, index=dates)
    d = ft.distance_to_high({"close_adj": price}, window=3, min_obs=1)["X"].to_numpy()
    np.testing.assert_allclose(d, [0.0, 0.0, 110 / 120 - 1, 90 / 120 - 1, 0.0, 117 / 130 - 1])


def test_valuation_features() -> None:
    dates = pd.bdate_range("2021-01-04", periods=3)
    per = pd.DataFrame({"X": [10.0, -5.0, 0.0]}, index=dates)
    ny = pd.DataFrame({"X": [6.5, -1.0, np.nan]}, index=dates)
    ey = ft.earnings_yield({"per": per})["X"]
    assert ey.iloc[0] == pytest.approx(0.1) and ey.iloc[1:].isna().all()
    dy = ft.dividend_yield({"net_yield_pct": ny})["X"]
    assert dy.iloc[0] == pytest.approx(0.065) and dy.iloc[1:].isna().all()
    dd = pd.DataFrame({"X": pd.to_datetime(["2019-01-01", "2019-01-01", "2020-12-01"])}, index=dates)
    dy_age = ft.dividend_yield({"net_yield_pct": ny.fillna(5.0), "last_div_date": dd}, max_dividend_age_days=365)["X"]
    assert dy_age.iloc[0] == 0.0 and dy_age.iloc[2] == pytest.approx(0.05)


def _dividend_panels() -> dict[str, pd.DataFrame]:
    dates = pd.bdate_range("2019-01-01", "2023-06-30")
    n = len(dates)
    amount = np.full(n, np.nan)
    pay = np.full(n, np.datetime64("NaT", "ns"), dtype="datetime64[ns]")
    schedule = [("2019-03-01", "2018-07-01", 100.0), ("2019-07-10", "2019-07-10", 110.0),
                ("2020-07-08", "2020-07-08", 121.0), ("2021-07-07", "2021-07-07", 0.0)]
    for seen, paid, amt in schedule:
        k = int(np.searchsorted(dates, pd.Timestamp(seen)))
        amount[k:] = amt
        pay[k:] = np.datetime64(pd.Timestamp(paid), "ns")
    close = pd.DataFrame({"X": np.full(n, 1000.0)}, index=dates)
    return {
        "close_adj": close,
        "last_div_net": pd.DataFrame({"X": amount}, index=dates),
        "last_div_date": pd.DataFrame({"X": pay}, index=dates),
    }


def test_dividend_growth_stability_and_age() -> None:
    P = _dividend_panels()
    idx = P["close_adj"].index
    loc = lambda d: int(np.searchsorted(idx, pd.Timestamp(d)))
    g = ft.dividend_growth(P)["X"]
    assert g.iloc[: loc("2019-07-10")].isna().all()
    assert g.iloc[loc("2019-07-10")] == pytest.approx(0.10)
    assert g.iloc[loc("2020-07-08") - 1] == pytest.approx(0.10)
    assert g.iloc[loc("2020-07-08")] == pytest.approx(0.10)  # 121 / 110 - 1
    assert g.iloc[loc("2021-07-07")] == pytest.approx(-1.0)  # dividend supprimé
    # Correction d'un split (facteur 0,5 avant juillet 2020) : 121 / (110 × 0,5) - 1.
    factor = pd.DataFrame({"X": np.where(idx < pd.Timestamp("2020-07-01"), 0.5, 1.0)}, index=idx)
    g_split = ft.dividend_growth(P, split_factor=factor)["X"]
    assert g_split.iloc[loc("2020-07-08")] == pytest.approx(121.0 / 55.0 - 1)

    s = ft.dividend_stability(P, grace_days=550)["X"]
    assert s.iloc[0] == 0.0  # coté, aucun dividende connu
    assert s.iloc[loc("2019-03-01")] == 1.0  # 2018
    assert s.iloc[loc("2019-07-10")] == 2.0  # 2018, 2019
    assert s.iloc[loc("2020-07-08")] == 3.0  # 2018-2020
    assert s.iloc[loc("2021-07-07")] == 3.0  # dividende nul : pas d'année ajoutée
    assert s.iloc[loc("2022-01-03")] == 3.0  # 2020-07-08 + 550 j = 2022-01-09
    assert s.iloc[loc("2022-02-01")] == 0.0  # série rompue

    days = ft.days_since_dividend(P)["X"]
    assert days.iloc[0] != days.iloc[0]  # NaN
    assert days.iloc[loc("2019-07-15")] == 5.0


def test_seasonality_recovers_january_effect() -> None:
    dates = pd.bdate_range("2015-01-01", "2020-12-31")
    month = dates.month
    daily = np.where(month == 1, 0.002, 0.0)
    daily_b = np.zeros(len(dates))
    price = pd.DataFrame({"A": 100 * np.cumprod(1 + daily), "B": 100 * np.cumprod(1 + daily_b)}, index=dates)
    P = {"tr_index": price}
    seas = ft.seasonality(P, min_years=2, max_years=None)
    jan_ret = (1.002 ** pd.Series(month == 1, index=dates).groupby(dates.to_period("M")).sum()) - 1
    jan = lambda *years: np.mean([jan_ret[pd.Period(f"{y}-01")] for y in years])
    # Janvier 2018 : moyenne de janvier 2016 et 2017 (janvier 2015 n'a pas de mois précédent).
    assert seas.loc["2018-01-15", "A"] == pytest.approx(jan(2016, 2017), rel=1e-10)
    assert seas.loc["2018-02-15", "A"] == pytest.approx(0.0, abs=1e-12)
    assert seas.loc["2017-01-16", "A"] != seas.loc["2017-01-16", "A"]  # une seule année : NaN
    assert seas["B"].dropna().abs().max() < 1e-12
    # month_offset=1 : fin décembre, on regarde les janviers passés.
    nxt = ft.seasonality(P, min_years=2, month_offset=1)
    assert nxt.loc["2018-12-28", "A"] == pytest.approx(jan(2016, 2017, 2018), rel=1e-10)
    assert nxt.loc["2017-12-28", "A"] == pytest.approx(jan(2016, 2017), rel=1e-10)
    capped = ft.seasonality(P, min_years=2, max_years=2)
    assert capped.loc["2019-01-15", "A"] == pytest.approx(jan(2017, 2018), rel=1e-10)
    with pytest.raises(ValueError):
        ft.seasonality(P, month_offset=12)


# ---------------------------------------------------------------------------
# 3. Scores transversaux
# ---------------------------------------------------------------------------


def _cross_section(seed: int = 0, T: int = 30, N: int = 40) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    x = pd.DataFrame(rng.lognormal(0, 1, (T, N)), index=pd.bdate_range("2022-01-03", periods=T),
                     columns=[f"S{i:02d}" for i in range(N)])
    x.iloc[3, 5] = np.nan
    x.iloc[4, :] = np.nan
    return x


def test_rank_gauss_blom_scores() -> None:
    x = _cross_section()
    z = sc.cross_sectional_zscore(x, method="rank_gauss", winsor=None)
    row = x.iloc[0]
    n = row.notna().sum()
    expected = norm.ppf(((row.rank() - 3 / 8) / (n + 1 / 4)).to_numpy())
    np.testing.assert_allclose(z.iloc[0].to_numpy(), expected, rtol=1e-12)
    assert z.iloc[4].isna().all() and np.isnan(z.iloc[3, 5])
    assert abs(z.iloc[0].mean()) < 1e-12  # symétrique
    # Monotone et invariant aux transformations croissantes.
    pd.testing.assert_frame_equal(z, sc.cross_sectional_zscore(np.log(x), winsor=None))
    # Ex aequo -> même score ; ligne constante -> 0.
    ties = pd.Series([1.0, 1.0, 2.0, 3.0])
    zt = sc.cross_sectional_zscore(ties)
    assert zt.iloc[0] == zt.iloc[1]
    assert (sc.cross_sectional_zscore(pd.Series([2.0] * 5)) == 0).all()
    assert sc.cross_sectional_zscore(pd.Series([1.0, np.nan, 2.0]), min_obs=3).isna().all()


def test_winsorized_zscore_properties() -> None:
    x = _cross_section(seed=1)
    x.iloc[0, 0] = 1e6  # valeur aberrante
    z = sc.cross_sectional_zscore(x, method="zscore", winsor=3.0)
    row = z.iloc[0]
    assert row.mean() == pytest.approx(0.0, abs=1e-12)
    assert row.std(ddof=1) == pytest.approx(1.0, rel=1e-12)
    assert row.iloc[0] <= 3.0 + 1e-6
    # Sans valeur aberrante et sans winsorisation : z-score classique.
    z0 = sc.cross_sectional_zscore(x.iloc[1:3], method="zscore", winsor=None)
    r = x.iloc[1]
    np.testing.assert_allclose(z0.iloc[0], (r - r.mean()) / r.std(ddof=1), rtol=1e-12)
    zr = sc.cross_sectional_zscore(x, method="robust", winsor=3.0)
    assert zr.abs().max().max() <= 3.0
    with pytest.raises(ValueError):
        sc.cross_sectional_zscore(x, method="minmax")  # type: ignore[arg-type]


def test_neutralize_zero_group_means_and_regression() -> None:
    x = _cross_section(seed=2)
    groups = pd.Series(["FIN"] * 15 + ["TEL"] * 5 + ["IND"] * 19 + [None], index=x.columns)
    out = sc.neutralize(x, groups)
    labels = groups.fillna("__sans_groupe__")
    for g in labels.unique():
        cols = labels.index[labels == g]
        means = out[cols].mean(axis=1).dropna()
        np.testing.assert_allclose(means.to_numpy(), 0.0, atol=1e-10)
    assert out.isna().equals(x.isna())
    # Régression sur indicatrices seules = soustraction de la moyenne.
    reg = sc.neutralize(x, groups, method="regress")
    np.testing.assert_allclose(reg.to_numpy(), out.to_numpy(), atol=1e-10)
    # Avec une exposition continue : résidus orthogonaux à l'exposition.
    rng = np.random.default_rng(5)
    expo = pd.Series(rng.normal(size=x.shape[1]), index=x.columns)
    res = sc.neutralize(x, groups, method="regress", exposures={"size": expo})
    for t in [0, 10]:
        ok = res.iloc[t].notna()
        assert float(res.iloc[t][ok] @ expo[ok]) == pytest.approx(0.0, abs=1e-8)
    # Regroupement des petits groupes : TEL (5 titres) rejoint __autres__ avec le titre sans groupe.
    pooled = sc.neutralize(x, groups, min_group_size=6)
    small = list(groups.index[groups == "TEL"]) + [groups.index[-1]]
    np.testing.assert_allclose(pooled[small].mean(axis=1).dropna().to_numpy(), 0.0, atol=1e-10)
    # Groupes variables dans le temps (DataFrame) et coupe unique (Series).
    gdf = pd.DataFrame(np.broadcast_to(groups.to_numpy(dtype=object), x.shape), index=x.index, columns=x.columns)
    pd.testing.assert_frame_equal(sc.neutralize(x, gdf), out)
    single = sc.neutralize(x.iloc[0], groups)
    pd.testing.assert_series_equal(single, out.iloc[0], check_names=False)


def test_combine_renormalizes_available_weights() -> None:
    idx = pd.bdate_range("2022-01-03", periods=2)
    a = pd.DataFrame({"X": [1.0, 1.0], "Y": [np.nan, -1.0], "Z": [np.nan, 0.5]}, index=idx)
    b = pd.DataFrame({"X": [-1.0, 0.0], "Y": [2.0, 1.0], "Z": [np.nan, np.nan]}, index=idx)
    out = sc.combine({"a": a, "b": b, "unused": a * 100}, {"a": 0.75, "b": 0.25})
    assert out.loc[idx[0], "X"] == pytest.approx(0.75 * 1 - 0.25 * 1)
    assert out.loc[idx[0], "Y"] == pytest.approx(2.0)  # seul b disponible
    assert np.isnan(out.loc[idx[0], "Z"])
    assert out.loc[idx[1], "Z"] == pytest.approx(0.5)
    cov = sc.combine({"a": a, "b": b}, {"a": 0.75, "b": 0.25}, min_coverage=0.5)
    assert np.isnan(cov.loc[idx[0], "Y"]) and cov.loc[idx[1], "Z"] == pytest.approx(0.5)
    neg = sc.combine({"a": a, "b": b}, {"a": 1.0, "b": -1.0})
    assert neg.loc[idx[1], "X"] == pytest.approx(0.5)
    s = sc.combine({"a": a.iloc[1].rename("m"), "b": b.iloc[1].rename("v")}, {"a": 1.0, "b": 1.0})
    assert isinstance(s, pd.Series) and s["Y"] == pytest.approx(0.0)
    with pytest.raises(KeyError):
        sc.combine({"a": a}, {"a": 1.0, "c": 1.0})


def test_information_coefficient_perfect_signal() -> None:
    rng = np.random.default_rng(7)
    fwd = pd.DataFrame(rng.normal(size=(20, 30)), index=pd.bdate_range("2022-01-03", periods=20))
    fwd.iloc[2, :25] = np.nan
    ic = sc.information_coefficient(fwd, fwd)
    np.testing.assert_allclose(ic.drop(fwd.index[2]).to_numpy(), 1.0)
    assert np.isnan(ic.iloc[2])  # 5 titres < min_obs
    np.testing.assert_allclose(sc.information_coefficient(np.exp(fwd), fwd).dropna(), 1.0)
    np.testing.assert_allclose(sc.information_coefficient(-fwd, fwd).dropna(), -1.0)
    noisy = fwd + rng.normal(size=fwd.shape)
    ic_n = sc.information_coefficient(noisy, fwd)
    t = 0
    assert ic_n.iloc[t] == pytest.approx(spearmanr(noisy.iloc[t], fwd.iloc[t]).statistic, rel=1e-12)
    ic_p = sc.information_coefficient(noisy, fwd, method="pearson")
    assert ic_p.iloc[t] == pytest.approx(np.corrcoef(noisy.iloc[t], fwd.iloc[t])[0, 1], rel=1e-12)


def test_quantile_returns_ordering() -> None:
    rng = np.random.default_rng(8)
    fwd = pd.DataFrame(rng.normal(size=(15, 40)), index=pd.bdate_range("2022-01-03", periods=15))
    q = sc.quantile_returns(fwd, fwd, n=5, add_spread=True)
    assert list(q.columns[:5]) == [1, 2, 3, 4, 5]
    assert (q[[1, 2, 3, 4, 5]].diff(axis=1).iloc[:, 1:] > 0).all().all()
    row = fwd.iloc[0].sort_values()
    assert q.iloc[0][1] == pytest.approx(row.iloc[:8].mean())
    assert q.iloc[0]["spread"] == pytest.approx(row.iloc[-8:].mean() - row.iloc[:8].mean())
    small = sc.quantile_returns(fwd.iloc[:, :6], fwd.iloc[:, :6], n=5)
    assert small.isna().all().all()


def test_forward_returns_alignment() -> None:
    P = _geometric_panels(T=50, g=1.01)
    fwd = sc.forward_returns(P["tr_index"], horizon=5, lag=1)
    np.testing.assert_allclose(fwd.iloc[:-6].to_numpy(), 1.01**5 - 1, rtol=1e-12)
    assert fwd.iloc[-6:].isna().all().all()
    f0 = sc.forward_returns(P["tr_index"]["A"], horizon=3, lag=0)
    assert f0.iloc[0] == pytest.approx(P["tr_index"]["A"].iloc[3] / P["tr_index"]["A"].iloc[0] - 1)


def test_shrunk_ic_weights() -> None:
    rng = np.random.default_rng(9)
    idx = pd.bdate_range("2020-01-01", periods=60)
    ic = pd.DataFrame(
        {"mom": rng.normal(0.05, 0.10, 60), "val": rng.normal(0.02, 0.05, 60), "bad": rng.normal(-0.05, 0.1, 60)},
        index=idx,
    )
    prior = {"mom": 0.2, "val": 0.5, "low_vol": 0.3}
    w_prior = sc.shrunk_ic_weights(ic, prior, shrinkage=1.0)
    assert w_prior["val"] == pytest.approx(0.5) and w_prior["bad"] == 0.0
    w0 = sc.shrunk_ic_weights(ic, prior, shrinkage=0.0)
    ir = (ic.mean() / ic.std(ddof=1)).clip(lower=0)
    np.testing.assert_allclose(w0[["mom", "val"]].to_numpy(), (ir / ir.sum())[["mom", "val"]].to_numpy())
    assert w0["bad"] == 0.0 and w0["low_vol"] == 0.0
    w = sc.shrunk_ic_weights(ic, prior, shrinkage=0.3)
    np.testing.assert_allclose(w.to_numpy(), (0.7 * w0 + 0.3 * w_prior).to_numpy(), rtol=1e-12)
    assert w.sum() == pytest.approx(1.0) and (w >= 0).all()
    # Historique trop court : a priori seul.
    w_short = sc.shrunk_ic_weights(ic.iloc[:5], prior, shrinkage=0.3, min_periods=12)
    pd.testing.assert_series_equal(w_short, w_prior)
    # Embargo / asof : ne dépend que des IC observables.
    w_emb = sc.shrunk_ic_weights(ic, prior, 0.3, asof=idx[40], embargo=5)
    pd.testing.assert_series_equal(w_emb, sc.shrunk_ic_weights(ic.iloc[:36], prior, 0.3))
    roll = sc.rolling_ic_weights(ic, prior, 0.3, embargo=5)
    pd.testing.assert_series_equal(roll.loc[idx[40]], w_emb, check_names=False)
    np.testing.assert_allclose(roll.sum(axis=1), 1.0)
    pd.testing.assert_series_equal(roll.iloc[0], w_prior, check_names=False)
    with pytest.raises(ValueError):
        sc.shrunk_ic_weights(ic, prior, shrinkage=1.5)


# ---------------------------------------------------------------------------
# 4. Régime de marché et HMM
# ---------------------------------------------------------------------------


def _simulate_hmm(T: int = 1500, seed: int = 11) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    A = np.array([[0.98, 0.02], [0.05, 0.95]])
    mu = np.array([0.0005, -0.001])
    sig = np.array([0.005, 0.02])
    s = np.zeros(T, dtype=int)
    for t in range(1, T):
        s[t] = int(rng.random() < A[s[t - 1], 1])
    return rng.normal(mu[s], sig[s]), s


def test_hmm_scan_filter_matches_naive_recursion() -> None:
    x, _ = _simulate_hmm(T=600)
    m = rg.GaussianHMM().fit(x)
    assert m.variances_ is not None and m.transmat_ is not None and m.means_ is not None
    b = norm.pdf(x[:, None], m.means_[None, :], np.sqrt(m.variances_)[None, :])
    alpha = np.zeros_like(b)
    a = m.startprob_ * b[0]
    ll = math.log(a.sum())
    alpha[0] = a / a.sum()
    for t in range(1, len(x)):
        a = (alpha[t - 1] @ m.transmat_) * b[t]
        ll += math.log(a.sum())
        alpha[t] = a / a.sum()
    np.testing.assert_allclose(m.filter(x), alpha, atol=1e-12)
    assert m.score(x) == pytest.approx(ll, rel=1e-10)
    sm = m.smooth(x)
    np.testing.assert_allclose(sm.sum(axis=1), 1.0)
    np.testing.assert_allclose(sm[-1], alpha[-1], atol=1e-12)  # lissé = filtré au dernier point


def test_hmm_recovers_parameters_and_matches_statsmodels() -> None:
    x, s = _simulate_hmm()
    m = rg.GaussianHMM().fit(x)
    assert m.variances_ is not None and m.transmat_ is not None
    np.testing.assert_allclose(np.sqrt(m.variances_), [0.005, 0.02], rtol=0.1)
    assert ((m.filter(x)[:, 1] > 0.5) == s.astype(bool)).mean() > 0.9
    sm = pytest.importorskip("statsmodels.api")
    res = sm.tsa.MarkovRegression(x, k_regimes=2, trend="c", switching_variance=True).fit(disp=False)
    sig_sm = np.sort(np.sqrt([res.params[-2], res.params[-1]]))
    np.testing.assert_allclose(np.sqrt(m.variances_), sig_sm, rtol=0.02)
    assert m.loglik_ >= res.llf - 1.0  # π libre : vraisemblance au moins comparable


def test_hmm_filtered_probabilities_rolling_refit() -> None:
    x, s = _simulate_hmm(T=1200)
    idx = pd.bdate_range("2015-01-01", periods=len(x))
    hp = rg.hmm_filtered_probabilities(pd.Series(x, index=idx), refit_every=100, train_window=600, min_train=300)
    assert hp.iloc[:299].isna().all().all()
    ok = hp["p_1"].notna()
    np.testing.assert_allclose(hp.loc[ok, ["p_0", "p_1"]].sum(axis=1), 1.0)
    acc = ((hp.loc[ok, "p_1"] > 0.5).to_numpy() == s[ok.to_numpy()].astype(bool)).mean()
    assert acc > 0.88
    assert (hp.loc[ok, "sigma_1"] > hp.loc[ok, "sigma_0"]).all()
    late = hp.iloc[-1]
    np.testing.assert_allclose([late["sigma_0"], late["sigma_1"]], np.array([0.005, 0.02]) * math.sqrt(252), rtol=0.1)
    # Dates sans rendement : dernière valeur connue ; NaN internes non propagés à tort.
    xs = pd.Series(x, index=idx)
    xs.iloc[700] = np.nan
    hp2 = rg.hmm_filtered_probabilities(xs, refit_every=100, train_window=600, min_train=300)
    pd.testing.assert_series_equal(hp2.iloc[700], hp2.iloc[699], check_names=False)
    m = rg.GaussianHMM().fit(x)
    assert m.bic_gain(x) > 0
    calm = np.random.default_rng(0).normal(0, 0.01, 800)
    assert rg.GaussianHMM().fit(calm).bic_gain(calm) < 0


def _regime_path() -> pd.Series:
    rng = np.random.default_rng(12)
    up = rng.normal(0.001, 0.005, 400)
    crash = rng.normal(-0.006, 0.03, 80)
    down = rng.normal(-0.0015, 0.004, 300)
    flat = rng.normal(0.0, 0.002, 250)
    r = np.concatenate([up, crash, down, flat])
    return pd.Series(100 * np.exp(np.cumsum(r)), index=pd.bdate_range("2012-01-02", periods=len(r)))


def test_market_regime_states_and_columns() -> None:
    lvl = _regime_path()
    reg = rg.market_regime(lvl, vol_rank_window=400)
    expected_cols = {"level", "ma", "trend", "ma_slope", "realized_vol", "vol_percentile", "drawdown", "state"}
    assert expected_cols <= set(reg.columns)
    assert reg["state"].iloc[:219].isna().all()
    assert set(reg["state"].dropna().unique()) <= set(rg.REGIME_STATES)
    assert (reg["state"].iloc[300:400] == "haussier").mean() > 0.9
    assert (reg["state"].iloc[420:480] == "stress").mean() > 0.6
    assert (reg["state"].iloc[600:780] == "baissier").mean() > 0.6
    np.testing.assert_allclose(reg["drawdown"], lvl / lvl.cummax() - 1)
    np.testing.assert_allclose(reg["recent_drawdown"], lvl / lvl.rolling(63, min_periods=1).max() - 1)
    assert (reg["drawdown"] <= 0).all() and (reg["recent_drawdown"] >= reg["drawdown"] - 1e-12).all()
    np.testing.assert_allclose(reg["ma"].iloc[250], lvl.iloc[51:251].mean())
    # Dates manquantes : état de la veille, niveau NaN.
    holes = lvl.copy()
    holes.iloc[500] = np.nan
    reg_h = rg.market_regime(holes, vol_rank_window=400)
    assert np.isnan(reg_h["level"].iloc[500])
    assert reg_h["state"].iloc[500] == reg_h["state"].iloc[499]
    # Hystérésis : moins de changements d'état.
    conf = rg.market_regime(lvl, vol_rank_window=400, confirm_days=5)
    changes = lambda s: int((s.dropna() != s.dropna().shift()).sum())
    assert changes(conf["state"]) <= changes(reg["state"])


def test_market_regime_with_hmm_columns() -> None:
    lvl = _regime_path()
    reg = rg.market_regime(lvl, vol_rank_window=400, hmm=True, hmm_min_train=250, hmm_refit_every=50)
    for c in ("p_turbulent", "hmm_state", "hmm_sigma_calm", "hmm_sigma_turbulent"):
        assert c in reg.columns
    p = reg["p_turbulent"]
    assert p.iloc[:249].isna().all()
    # Fenêtres d'estimation entièrement calmes : le BIC préfère une loi unique,
    # les régimes ne sont pas discriminés -> NaN (et non un faux « turbulent »).
    assert p.iloc[300:449].isna().all()
    assert p.iloc[450:480].mean() > 0.8  # krach : état turbulent
    assert p.iloc[650:900].mean() < 0.2  # baisse lente et calme
    assert (reg["hmm_sigma_turbulent"].dropna() > reg["hmm_sigma_calm"].dropna()).all()
    no_guard = rg.market_regime(lvl, vol_rank_window=400, hmm=True, hmm_min_train=250,
                                hmm_refit_every=50, hmm_bic_check=False, hmm_min_sigma_ratio=None)
    assert no_guard["p_turbulent"].iloc[300:449].notna().all()
    with pytest.raises(TypeError):
        rg.market_regime(lvl.to_frame())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 5. Intégration sur le panel réel (si disponible)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not PANEL.exists(), reason="data/panel/equities.parquet absent")
def test_smoke_on_real_panel() -> None:
    eq = pd.read_parquet(PANEL)
    eq["date"] = pd.to_datetime(eq["date"])
    wide = lambda col: eq.pivot_table(index="date", columns="symbol", values=col, aggfunc="last").sort_index()
    close = wide("close")
    panels = {
        "close_adj": close,
        "tr_index": close,
        "volume": wide("volume"),
        "value": wide("value"),
        "net_yield_pct": wide("net_yield_pct"),
        "per": wide("per"),
        "last_div_net": wide("last_div_net"),
        "change_pct": wide("change_pct"),
        "status": eq.pivot(index="date", columns="symbol", values="status").sort_index(),
        "last_div_date": eq.pivot(index="date", columns="symbol", values="last_div_date").sort_index(),
    }
    lib = ft.compute_features(panels)
    assert len(lib) >= 15
    for name, df in lib.items():
        assert df.shape == close.shape, name
        assert not np.isinf(df.to_numpy(dtype=float)).any(), name
    z = sc.combine(
        {k: sc.cross_sectional_zscore(lib[k]) for k in ("mom_6_1", "dividend_yield")},
        {"mom_6_1": 0.5, "dividend_yield": 0.5},
    )
    assert z.shape == close.shape

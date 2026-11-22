"""Tests de brvm_alpha.backtest (moteur quotidien, walk-forward, grilles).

Toutes les données sont synthétiques et générées avec une graine fixe ; chaque
propriété du moteur est vérifiée contre un calcul indépendant écrit à la main
(formules de coûts, quantités, dividendes). Un test « smoke » utilise le panel
réel ``data/panel/equities.parquet`` s'il existe.
"""

from __future__ import annotations

import math
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from brvm_alpha.backtest import engine as eng
from brvm_alpha.backtest.engine import (
    Backtester,
    BacktestResult,
    PanelView,
    limit_flags,
    panels_from_equities,
    rebalance_dates,
    trade_cost,
    truncate_asof,
)
from brvm_alpha.backtest.walkforward import (
    param_grid,
    run_param_grid,
    walk_forward,
    walk_forward_windows,
)
from brvm_alpha.config import Constraints, CostModel, ExecutionModel, PlatformConfig, TaxModel

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "data" / "panel" / "equities.parquet"

NO_IMPACT = CostModel(impact_coef=0.0)


# ---------------------------------------------------------------------------
# Données synthétiques
# ---------------------------------------------------------------------------


def _dates(n: int, start: str = "2021-01-04") -> pd.DatetimeIndex:
    return pd.bdate_range(start, periods=n)


def make_panels(
    close: pd.DataFrame,
    *,
    volume: pd.DataFrame | float = 1e9,
    vwap: pd.DataFrame | None = None,
    prev_close: pd.DataFrame | None = None,
    dividend: pd.DataFrame | None = None,
    status: pd.DataFrame | None = None,
) -> dict[str, object]:
    """Panels minimaux : value = VWAP × volume, prev_close = clôture de la veille."""
    vol = (
        volume
        if isinstance(volume, pd.DataFrame)
        else pd.DataFrame(float(volume), index=close.index, columns=close.columns)
    )
    px = close if vwap is None else vwap
    if prev_close is None:
        prev_close = close.shift(1).fillna(close)
    panels: dict[str, object] = {
        "close": close,
        "volume": vol,
        "value": px * vol,
        "prev_close": prev_close,
        "dividend_net": dividend
        if dividend is not None
        else pd.DataFrame(0.0, index=close.index, columns=close.columns),
        "status": status
        if status is not None
        else pd.DataFrame(np.where(vol > 0, "traded", "not_traded"), index=close.index, columns=close.columns),
    }
    return panels


def random_market(n: int = 160, n_sym: int = 6, seed: int = 7, zero_frac: float = 0.3) -> dict[str, object]:
    """Marché aléatoire à la BRVM : ±7,5 % max, nombreuses séances sans échange."""
    rng = np.random.default_rng(seed)
    dates = _dates(n)
    syms = [f"S{i}C" for i in range(n_sym)]
    r = np.clip(rng.standard_t(4, size=(n, n_sym)) * 0.02, -0.075, 0.075)
    close = pd.DataFrame(1000.0 * np.cumprod(1.0 + r, axis=0), index=dates, columns=syms)
    vol = rng.integers(1, 400, size=(n, n_sym)).astype(float)
    vol[rng.random((n, n_sym)) < zero_frac] = 0.0
    volume = pd.DataFrame(vol, index=dates, columns=syms)
    # cours inchangé les jours sans échange (comme au BOC)
    close = close.where(volume > 0).ffill().fillna(1000.0)
    vwap = close * (1.0 + rng.uniform(-0.01, 0.01, size=(n, n_sym)))
    return make_panels(close, volume=volume, vwap=vwap)


def const_strategy(weights: dict[str, float]):
    def strat(asof: pd.Timestamp, view: PanelView) -> pd.Series:
        return pd.Series(weights, dtype=float)

    return strat


# ---------------------------------------------------------------------------
# (a) Achat-conservation ≈ rendement du titre moins coûts
# ---------------------------------------------------------------------------


def test_buy_and_hold_matches_asset_return_minus_costs() -> None:
    rng = np.random.default_rng(0)
    n = 120
    dates = _dates(n)
    r = rng.normal(0.0005, 0.012, n)
    r[1] = 0.003  # la séance d'exécution monte : la contrainte de cash est active
    close = pd.DataFrame({"SNTS": 1000.0 * np.cumprod(1.0 + r)}, index=dates)
    vwap = close * (1.0 + rng.uniform(-0.002, 0.002, size=(n, 1)))
    vwap.iloc[1] = close.iloc[1]
    panels = make_panels(close, vwap=vwap)
    capital = 1e8
    bt = Backtester(panels, NO_IMPACT, capital=capital)
    res = bt.run(const_strategy({"SNTS": 1.0}), rebalance=None)

    rate = NO_IMPACT.rate()
    assert len(res.trades) == 1
    tr = res.trades.iloc[0]
    assert tr["date"] == dates[1] and tr["decision_date"] == dates[0]  # exécution en t+1
    p1 = float(vwap.iloc[1, 0])
    assert tr["price"] == pytest.approx(p1, rel=1e-12)
    q = int(tr["qty"])
    # quantité maximale finançable : q·p·(1+τ) ≤ capital < (q+1)·p·(1+τ)
    assert q * p1 * (1 + rate) <= capital + 1e-6
    assert (q + 1) * p1 * (1 + rate) > capital
    assert tr["cost"] == pytest.approx(rate * q * p1, rel=1e-12)

    stock_ret = float(close.iloc[-1, 0]) / p1 - 1.0
    strat_ret = float(res.equity.iloc[-1]) / capital - 1.0
    expected = (1.0 + stock_ret) / (1.0 + rate) - 1.0
    assert strat_ret == pytest.approx(expected, abs=2e-5)
    # écart au rendement brut ≈ coût aller simple
    assert stock_ret - strat_ret == pytest.approx(rate * (1 + stock_ret) / (1 + rate), abs=2e-5)
    # identité comptable exacte
    assert float(res.equity.iloc[-1]) == pytest.approx(
        q * float(close.iloc[-1, 0]) + float(res.cash.iloc[-1]), rel=1e-12
    )
    # rendements composés = valeur finale
    assert float(np.prod(1.0 + res.returns)) * capital == pytest.approx(float(res.equity.iloc[-1]), rel=1e-10)
    # ordre dimensionné au cours de décision ; le reliquat (cash insuffisant) reste en attente
    target = math.floor(capital / float(close.iloc[0, 0]))
    assert int(res.orders["qty"].iloc[0]) == target
    assert res.fill_rate == pytest.approx(q / target)
    assert res.orders["status"].iloc[0] == "end_of_backtest"


def test_daily_valuation_uses_last_known_close() -> None:
    dates = _dates(8)
    close = pd.DataFrame({"AAAC": [100.0, 100.0, 110.0, np.nan, np.nan, 120.0, 120.0, 130.0]}, index=dates)
    vol = pd.DataFrame({"AAAC": [1e6, 1e6, 1e6, 0.0, 0.0, 1e6, 1e6, 1e6]}, index=dates)
    panels = make_panels(close, volume=vol, prev_close=close.ffill().shift(1).bfill())
    res = Backtester(panels, NO_IMPACT, capital=1e6).run(const_strategy({"AAAC": 0.5}), rebalance=None)
    q = int(res.positions.iloc[-1, 0])
    cash = float(res.cash.iloc[-1])
    # séances 3 et 4 : NaN -> dernier cours connu (110)
    assert float(res.equity.iloc[3]) == pytest.approx(cash + q * 110.0)
    assert float(res.equity.iloc[4]) == pytest.approx(cash + q * 110.0)
    assert float(res.weights.iloc[3, 0]) == pytest.approx(q * 110.0 / float(res.equity.iloc[3]))
    assert np.allclose(res.weights.sum(axis=1) + res.cash / res.equity, 1.0)


# ---------------------------------------------------------------------------
# (b) Aucune anticipation
# ---------------------------------------------------------------------------


def test_view_is_truncated_at_asof() -> None:
    panels = random_market(n=60)
    panels["country"] = pd.Series({s: "CI" for s in panels["close"].columns})  # type: ignore[union-attr]
    panels["index_level"] = pd.Series(np.arange(60.0), index=panels["close"].index)  # type: ignore[union-attr]
    seen: list[pd.Timestamp] = []

    def snoop(asof: pd.Timestamp, view: PanelView) -> pd.Series:
        seen.append(asof)
        assert view.asof == asof
        for key in view:
            obj = view[key]
            if isinstance(obj, (pd.DataFrame, pd.Series)) and isinstance(obj.index, pd.DatetimeIndex):
                assert obj.index.max() == asof, key
        nxt = asof + pd.offsets.BDay(1)
        with pytest.raises(KeyError):
            view["close"].loc[nxt]
        # lire « demain » via un décalage ne donne que des NaN
        assert view["close"].shift(-1).iloc[-1].isna().all()
        assert "country" in view and view["country"].iloc[0] == "CI"
        return pd.Series(1.0 / 6, index=view["close"].columns)

    res = Backtester(panels, capital=1e7).run(snoop, rebalance="D")
    assert len(seen) == 59  # toutes les séances sauf la dernière (pas de t+1)
    assert list(res.rebalance_dates) == seen


@pytest.mark.filterwarnings("ignore:.*variation\\(s\\) de clôture invraisemblable")
def test_future_data_cannot_change_the_past() -> None:
    """Perturber toutes les données après T ne modifie rien jusqu'à T."""
    panels = random_market(n=150, seed=11)
    cut = panels["close"].index[90]  # type: ignore[union-attr]
    rng = np.random.default_rng(99)
    altered = {}
    for k, v in panels.items():
        if isinstance(v, pd.DataFrame) and v.dtypes.iloc[0] != object and k != "status":
            w = v.copy()
            future = w.index > cut
            w.loc[future] = w.loc[future] * rng.uniform(0.5, 2.0, size=w.loc[future].shape)
            altered[k] = w
        else:
            altered[k] = v

    def momentum(asof: pd.Timestamp, view: PanelView) -> pd.Series:
        c = view["close"]
        if len(c) < 6:
            return pd.Series(dtype=float)
        mom = c.iloc[-1] / c.iloc[-6] - 1.0
        best = mom.nlargest(2).index
        return pd.Series(0.5, index=best)

    costs = CostModel(impact_coef=0.2)
    a = Backtester(panels, costs, capital=5e6).run(momentum, rebalance="D")
    b = Backtester(altered, costs, capital=5e6).run(momentum, rebalance="D")
    pd.testing.assert_series_equal(a.equity.loc[:cut], b.equity.loc[:cut])
    pd.testing.assert_frame_equal(a.positions.loc[:cut], b.positions.loc[:cut])
    ta = a.trades[a.trades["date"] <= cut].reset_index(drop=True)
    tb = b.trades[b.trades["date"] <= cut].reset_index(drop=True)
    pd.testing.assert_frame_equal(ta, tb)
    # ... et la perturbation a bien changé la suite
    assert not a.equity.loc[cut:].iloc[1:].equals(b.equity.loc[cut:].iloc[1:])


def test_strategy_mutating_the_view_does_not_touch_engine_data() -> None:
    panels = random_market(n=80, seed=3)

    def vandal(asof: pd.Timestamp, view: PanelView) -> pd.Series:
        c = view["close"]
        c.iloc[:, :] = 1e12  # copie à l'écriture : ne remonte pas au moteur
        view["volume"].iloc[-1] = 0.0
        return pd.Series(0.25, index=list(view["close"].columns[:4]))

    def clean(asof: pd.Timestamp, view: PanelView) -> pd.Series:
        return pd.Series(0.25, index=list(view["close"].columns[:4]))

    ra = Backtester(panels, capital=1e7).run(vandal, rebalance="W-FRI")
    rb = Backtester(panels, capital=1e7).run(clean, rebalance="W-FRI")
    pd.testing.assert_series_equal(ra.equity, rb.equity)
    assert float(panels["close"].to_numpy().max()) < 1e6  # type: ignore[union-attr]


def test_truncate_asof_unsorted_and_static_objects() -> None:
    idx = pd.DatetimeIndex(["2024-01-03", "2024-01-01", "2024-01-02"])
    s = pd.Series([3.0, 1.0, 2.0], index=idx)
    out = truncate_asof(s, pd.Timestamp("2024-01-02"))
    assert sorted(out.tolist()) == [1.0, 2.0]
    meta = pd.Series({"SNTS": "SN"})
    m2 = truncate_asof(meta, pd.Timestamp("2000-01-01"))
    m2["SNTS"] = "CI"
    assert meta["SNTS"] == "SN"
    assert truncate_asof(42, pd.Timestamp("2024-01-01")) == 42


def _leaky_formats(n: int = 30) -> dict[str, object]:
    """Panels dans tous les formats datés rencontrés (schémas ARCHITECTURE.md, CSV, MultiIndex…)."""
    dates = _dates(n)
    close = pd.DataFrame({"SNTS": np.linspace(1000.0, 1300.0, n)}, index=dates)
    vol_str = pd.DataFrame({"SNTS": 1e6}, index=dates.strftime("%Y-%m-%d"))  # CSV sans parse_dates
    indices_long = pd.DataFrame({"date": dates, "index": "BRVMC", "level": np.linspace(200.0, 260.0, n)})
    ca_long = pd.DataFrame(  # corporate_actions.parquet, dates en chaînes et non triées
        {"date": dates[::-1].strftime("%Y-%m-%d"), "symbol": "SNTS", "kind": "split", "ratio": 2.0}
    )
    mi = pd.DataFrame(
        {"close": np.repeat(close["SNTS"].to_numpy(), 2)},
        index=pd.MultiIndex.from_product([dates, ["SNTS", "ORAC"]], names=["date", "symbol"]),
    )
    mi_str = mi.set_axis(
        pd.MultiIndex.from_arrays(
            [mi.index.get_level_values(0).strftime("%Y-%m-%d"), mi.index.get_level_values(1)],
            names=["date", "symbol"],
        )
    ).iloc[::-1]
    monthly = pd.Series([1.0, 2.0, 3.0], index=pd.period_range("2020-12", periods=3, freq="M"))
    return {
        "close": close,
        "volume": vol_str,
        "value": close * 1e6,
        "indices": indices_long,
        "ca": ca_long,
        "eq_long": mi,
        "eq_str": mi_str,
        "monthly": monthly,
        "nested": {"a": close, "b": [indices_long, "x"]},
        "universe": ["SNTS"],
    }


def test_view_truncates_every_dated_format_and_hides_source() -> None:
    """Non-régression : table longue, index en chaînes, MultiIndex, PeriodIndex, objets imbriqués."""
    panels = _leaky_formats()
    seen: list[pd.Timestamp] = []

    def snoop(asof: pd.Timestamp, view: PanelView) -> pd.Series:
        seen.append(asof)
        assert not hasattr(view, "_source")  # panels complets inaccessibles
        assert view["indices"]["date"].max() == asof
        assert view["ca"]["date"].max() == asof
        assert view["volume"].index.max() == asof
        assert view["eq_long"].index.get_level_values("date").max() == asof
        assert view["eq_str"].index.get_level_values("date").max() == asof
        assert float(view["eq_long"]["close"].iloc[-1]) == float(view["close"].iloc[-1, 0])
        months = view["monthly"].index
        assert (months.end_time.normalize() <= asof).all()
        assert len(months) == (2 if asof >= pd.Timestamp("2021-01-31") else 1)  # janvier visible au 31/01
        assert view["nested"]["a"].index.max() == asof
        assert view["nested"]["b"][0]["date"].max() == asof and view["nested"]["b"][1] == "x"
        assert view["universe"] == ["SNTS"]
        return pd.Series({"SNTS": 0.5})

    Backtester(panels, capital=1e6).run(snoop, rebalance="D")
    assert len(seen) == 29


def test_future_rows_of_long_tables_cannot_change_the_past() -> None:
    """Une stratégie lisant une table longue est insensible aux lignes postérieures à T."""
    panels = _leaky_formats(n=60)
    dates = panels["close"].index  # type: ignore[union-attr]
    cut = dates[35]
    altered = dict(panels)
    idx = panels["indices"].copy()  # type: ignore[union-attr]
    idx.loc[idx["date"] > cut, "level"] *= 3.0
    altered["indices"] = idx
    mi = panels["eq_long"].copy()  # type: ignore[union-attr]
    mi.loc[mi.index.get_level_values("date") > cut, "close"] = 1.0
    altered["eq_long"] = mi

    def strat(asof: pd.Timestamp, view: PanelView) -> pd.Series:
        lvl = view["indices"]["level"]
        px = view["eq_long"].xs("SNTS", level="symbol")["close"]
        up = lvl.iloc[-1] >= lvl.iloc[max(0, len(lvl) - 5)] and px.iloc[-1] >= px.iloc[0]
        return pd.Series({"SNTS": 0.8 if up else 0.2})

    a = Backtester(panels, NO_IMPACT, capital=1e6).run(strat, rebalance="D")
    b = Backtester(altered, NO_IMPACT, capital=1e6).run(strat, rebalance="D")
    pd.testing.assert_series_equal(a.equity.loc[:cut], b.equity.loc[:cut])
    pd.testing.assert_frame_equal(a.positions.loc[:cut], b.positions.loc[:cut])


def test_untruncatable_dated_objects_are_rejected() -> None:
    dates = _dates(5)
    close = pd.DataFrame({"SNTS": 1000.0}, index=dates)
    vol = pd.DataFrame({"SNTS": 1e6}, index=dates)
    bad = {
        "numpy": np.arange(5.0),
        "date_scalar": pd.Timestamp("2030-01-01"),
        "dated_values": pd.Series(pd.to_datetime(["2030-01-01"]), index=["SNTS"]),
        "events_without_date": pd.DataFrame({"ex_date": dates, "amount": 1.0}),
        "transposed": close.T,
        "ambiguous_strings": pd.Series([1.0, 2.0], index=["01/12/2021", "02/12/2021"]),
    }
    for name, obj in bad.items():
        with pytest.raises(TypeError):
            truncate_asof(obj, dates[0])
        with pytest.raises(TypeError, match=name):
            Backtester({"close": close, "volume": vol, name: obj}, capital=1e6)
    # objets statiques et index de codes BRVM : acceptés
    ok = truncate_asof({"symbols": ("SNTS", "ORAC"), "n": 3, "meta": pd.Series({"S0C": "CI"})}, dates[0])
    assert ok["symbols"] == ("SNTS", "ORAC") and ok["meta"]["S0C"] == "CI"
    # dates en chaînes non ambiguës (jour > 12) et ISO
    s = pd.Series([1.0, 2.0, 3.0], index=["13/01/2021", "14/01/2021", "15/01/2021"])
    assert truncate_asof(s, "2021-01-14").tolist() == [1.0, 2.0]
    s_iso = pd.Series([3.0, 1.0], index=["2021-01-06", "2021-01-04"])
    assert truncate_asof(s_iso, "2021-01-05").tolist() == [1.0]


# ---------------------------------------------------------------------------
# (c) Limites de variation
# ---------------------------------------------------------------------------


def _limit_market(move_day1: float) -> dict[str, object]:
    dates = _dates(6)
    c = [1000.0, 1000.0 * (1 + move_day1), 1000.0 * (1 + move_day1) * 1.01, 1100.0, 1100.0, 1100.0]
    close = pd.DataFrame({"BOAC": c}, index=dates)
    return make_panels(close)


def test_limit_up_blocks_buy_then_carry_executes() -> None:
    panels = _limit_market(0.075)
    res = Backtester(panels, NO_IMPACT, capital=1e6).run(const_strategy({"BOAC": 0.5}), rebalance=None)
    dates = panels["close"].index  # type: ignore[union-attr]
    assert (res.trades["date"] == dates[1]).sum() == 0
    blk = res.blocked[res.blocked["date"] == dates[1]]
    assert list(blk["reason"]) == ["limit_up"]
    assert res.trades["date"].iloc[0] == dates[2]
    assert res.trades["reason"].iloc[0] == "carry"
    # sans report, l'ordre expire à t+1
    ex = ExecutionModel(carry_unfilled=False)
    res2 = Backtester(panels, NO_IMPACT, ex, capital=1e6).run(const_strategy({"BOAC": 0.5}), rebalance=None)
    assert res2.trades.empty
    assert res2.orders["status"].tolist() == ["expired"]
    assert math.isclose(res2.fill_rate, 0.0)


def test_close_just_below_limit_tolerance_is_treated_as_limit() -> None:
    # +7,35 % ≥ 7,5 % − 0,2 % : considéré à la limite
    panels = _limit_market(0.0735)
    res = Backtester(panels, NO_IMPACT, capital=1e6).run(const_strategy({"BOAC": 0.5}), rebalance=None)
    assert res.trades["date"].iloc[0] == panels["close"].index[2]  # type: ignore[union-attr]
    # +7,0 % : exécutable
    panels = _limit_market(0.07)
    res = Backtester(panels, NO_IMPACT, capital=1e6).run(const_strategy({"BOAC": 0.5}), rebalance=None)
    assert res.trades["date"].iloc[0] == panels["close"].index[1]  # type: ignore[union-attr]


def test_limit_down_blocks_sell() -> None:
    dates = _dates(8)
    c = [1000.0, 1000.0, 1000.0, 925.0, 930.0, 930.0, 930.0, 930.0]  # séance 3 : −7,5 %
    close = pd.DataFrame({"SGBC": c}, index=dates)
    panels = make_panels(close)

    def strat(asof: pd.Timestamp, view: PanelView) -> pd.Series:
        return pd.Series({"SGBC": 0.9 if asof == dates[0] else 0.0})

    res = Backtester(panels, NO_IMPACT, capital=1e6).run(strat, rebalance=[dates[0], dates[2]])
    sells = res.trades[res.trades["qty"] < 0]
    assert sells["date"].tolist() == [dates[4]]
    assert res.blocked.loc[res.blocked["date"] == dates[3], "reason"].tolist() == ["limit_down"]
    assert int(res.positions.iloc[-1, 0]) == 0


def test_limit_flags_reference_and_implausible_moves() -> None:
    up, down = limit_flags(np.array([0.075, 0.074, -0.075, 0.0, -0.5, np.nan]), 0.075, 0.002, 0.2)
    assert up.tolist() == [True, True, False, False, False, False]
    assert down.tolist() == [False, False, True, False, False, False]


def test_change_pct_has_priority_and_ex_dividend_reference() -> None:
    dates = _dates(5)
    close = pd.DataFrame({"SNTS": [1000.0, 1000.0, 920.0, 920.0, 920.0]}, index=dates)
    div = pd.DataFrame({"SNTS": [0.0, 0.0, 80.0, 0.0, 0.0]}, index=dates)
    panels = make_panels(close, dividend=div)
    # prev_close brut = 1000 et dividende de 80 : référence 920 => variation nulle
    bt = Backtester(panels, NO_IMPACT, capital=1e6)
    assert not bt._lim_down[2, 0]
    # variation publiée prioritaire
    panels["change_pct"] = pd.DataFrame({"SNTS": [0.0, 0.0, -7.5, 0.0, 0.0]}, index=dates)
    assert Backtester(panels, NO_IMPACT, capital=1e6)._lim_down[2, 0]


# ---------------------------------------------------------------------------
# (d) Participation au volume et report du reliquat
# ---------------------------------------------------------------------------


def test_volume_participation_caps_quantities_and_carries_remainder() -> None:
    dates = _dates(10)
    close = pd.DataFrame({"ORAC": 1000.0}, index=dates)
    vol = pd.DataFrame({"ORAC": [100.0, 100.0, 100.0, 0.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]}, index=dates)
    panels = make_panels(close, volume=vol)
    ex = ExecutionModel(max_volume_participation=0.2)
    res = Backtester(panels, NO_IMPACT, ex, capital=1e6).run(const_strategy({"ORAC": 0.1}), rebalance=None)
    # cible 0,1 × 1e6 / 1000 = 100 titres, au plus 20 par séance, rien le jour sans échange
    assert res.trades["qty"].tolist() == [20, 20, 20, 20, 20]
    assert res.trades["date"].tolist() == [dates[1], dates[2], dates[4], dates[5], dates[6]]
    assert res.trades["reason"].tolist() == ["rebalance", "carry", "carry", "carry", "carry"]
    assert np.allclose(res.trades["participation"], 0.2)
    assert res.blocked.loc[res.blocked["date"] == dates[3], "reason"].tolist() == ["not_traded"]
    assert set(res.blocked.loc[res.blocked["date"] == dates[1], "reason"]) == {"volume_cap"}
    assert res.orders["status"].tolist() == ["filled"]
    assert res.fill_rate == pytest.approx(1.0)
    # sans report : 20 titres seulement
    ex2 = ExecutionModel(max_volume_participation=0.2, carry_unfilled=False)
    res2 = Backtester(panels, NO_IMPACT, ex2, capital=1e6).run(const_strategy({"ORAC": 0.1}), rebalance=None)
    assert res2.trades["qty"].tolist() == [20]
    assert res2.fill_rate == pytest.approx(0.2)
    # durée de vie maximale d'un ordre reporté
    res3 = Backtester(panels, NO_IMPACT, ex, capital=1e6, max_order_age=3).run(
        const_strategy({"ORAC": 0.1}), rebalance=None
    )
    assert res3.trades["qty"].sum() == 40  # séances 1, 2, puis 3 (sans échange) et expiration
    assert res3.orders["status"].tolist() == ["expired"]


def test_suspended_status_blocks_execution() -> None:
    dates = _dates(5)
    close = pd.DataFrame({"SIVC": 500.0}, index=dates)
    status = pd.DataFrame({"SIVC": ["traded", "suspended", "traded", "traded", None]}, index=dates)
    panels = make_panels(close, status=status)
    res = Backtester(panels, NO_IMPACT, capital=1e5).run(const_strategy({"SIVC": 0.5}), rebalance=None)
    assert res.trades["date"].tolist() == [dates[2]]


# ---------------------------------------------------------------------------
# (e) Dividendes
# ---------------------------------------------------------------------------


def test_dividends_credited_on_ex_date() -> None:
    dates = _dates(10)
    close = pd.DataFrame({"SNTS": [1000.0] * 5 + [950.0] * 5}, index=dates)
    div = pd.DataFrame({"SNTS": [0.0] * 5 + [50.0] + [0.0] * 4}, index=dates)
    panels = make_panels(close, dividend=div)
    res = Backtester(panels, NO_IMPACT, capital=1e6).run(const_strategy({"SNTS": 0.5}), rebalance=None)
    q = int(res.positions.iloc[4, 0])
    assert q == 500
    assert float(res.dividends.iloc[5]) == pytest.approx(q * 50.0)
    assert float(res.dividends.sum()) == pytest.approx(q * 50.0)
    assert float(res.cash.iloc[5] - res.cash.iloc[4]) == pytest.approx(q * 50.0)
    # rendement total : la baisse du cours est compensée par le dividende
    assert float(res.equity.iloc[5]) == pytest.approx(float(res.equity.iloc[4]))


def test_dividend_not_credited_to_shares_bought_on_ex_date() -> None:
    dates = _dates(8)
    close = pd.DataFrame({"SNTS": 1000.0}, index=dates)
    div = pd.DataFrame({"SNTS": [0.0, 0.0, 0.0, 40.0, 0.0, 0.0, 0.0, 0.0]}, index=dates)
    panels = make_panels(close, dividend=div)
    res = Backtester(panels, NO_IMPACT, capital=1e6).run(const_strategy({"SNTS": 0.5}), rebalance=[dates[2]])
    assert res.trades["date"].tolist() == [dates[3]]
    assert float(res.dividends.sum()) == 0.0


def test_dividend_withholding_when_amounts_are_gross() -> None:
    dates = _dates(6)
    close = pd.DataFrame({"SNTS": 1000.0, "BOAB": 1000.0}, index=dates)
    div = pd.DataFrame({"SNTS": [0, 0, 0, 100.0, 0, 0], "BOAB": [0, 0, 0, 100.0, 0, 0]}, index=dates, dtype=float)
    panels = make_panels(close, dividend=div)
    panels["country"] = pd.Series({"SNTS": "SN"})  # BOAB : déduit du suffixe (B -> BJ)
    taxes = TaxModel(dividend_withholding={"SN": 0.10, "BJ": 0.05}, dividends_reported_net=False)
    res = Backtester(panels, NO_IMPACT, taxes, capital=1e6).run(
        const_strategy({"SNTS": 0.4, "BOAB": 0.4}), rebalance=None
    )
    q = res.positions.iloc[2]
    expected = q["SNTS"] * 100 * 0.90 + q["BOAB"] * 100 * 0.95
    assert float(res.dividends.iloc[3]) == pytest.approx(expected)
    assert float(res.taxes.iloc[3]) == pytest.approx(q["SNTS"] * 10 + q["BOAB"] * 5)


# ---------------------------------------------------------------------------
# (f) Cash jamais négatif
# ---------------------------------------------------------------------------


@pytest.mark.filterwarnings("ignore:exposition brute")
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_cash_never_negative_under_stress(seed: int) -> None:
    panels = random_market(n=200, n_sym=8, seed=seed, zero_frac=0.4)
    rng = np.random.default_rng(seed + 100)
    costs = CostModel(impact_coef=0.8, min_ticket_fcfa=2500.0, annual_custody=0.05)

    def chaos(asof: pd.Timestamp, view: PanelView) -> pd.Series:
        cols = view["close"].columns
        w = rng.random(len(cols)) * (rng.random(len(cols)) < 0.7)
        return pd.Series(w / max(w.sum(), 1e-9) * rng.uniform(0.8, 1.6), index=cols)

    ex = ExecutionModel(max_volume_participation=1.0)
    res = Backtester(panels, costs, ex, capital=3e5).run(chaos, rebalance=3)
    assert (res.cash >= 0.0).all()
    assert (res.positions.to_numpy() >= 0).all()
    assert (res.equity > 0).all()
    assert len(res.trades) > 20
    assert (res.blocked["reason"] == "cash").any()  # la contrainte de cash a mordu


def test_sells_fund_same_day_buys() -> None:
    dates = _dates(6)
    close = pd.DataFrame({"AAAC": 1000.0, "BBBS": 1000.0}, index=dates)
    panels = make_panels(close)

    def switch(asof: pd.Timestamp, view: PanelView) -> pd.Series:
        return pd.Series({"AAAC": 0.98}) if asof == dates[0] else pd.Series({"BBBS": 0.97})

    res = Backtester(panels, NO_IMPACT, capital=1e6).run(switch, rebalance=[dates[0], dates[2]])
    day = res.trades[res.trades["date"] == dates[3]]
    assert day["symbol"].tolist() == ["AAAC", "BBBS"]  # vente puis achat
    # cible dimensionnée sur la NAV de décision (nette des frais du premier achat)
    target = math.floor(0.97 * float(res.equity.iloc[2]) / 1000.0)
    assert int(res.positions.iloc[-1]["BBBS"]) == target
    # l'achat n'aurait pas été finançable sans le produit de la vente du jour
    assert float(res.cash.iloc[2]) < target * 1000.0
    assert (res.cash >= 0).all()


@pytest.mark.filterwarnings("ignore:exposition brute")
def test_leverage_and_short_weights_are_neutralised() -> None:
    dates = _dates(5)
    close = pd.DataFrame({"AAAC": 1000.0, "BBBS": 1000.0}, index=dates)
    panels = make_panels(close)
    with pytest.warns(UserWarning, match="négatifs"):
        res = Backtester(panels, NO_IMPACT, capital=1e6).run(
            const_strategy({"AAAC": 1.5, "BBBS": -0.5}), rebalance=None
        )
    assert int(res.positions.iloc[-1]["BBBS"]) == 0
    assert float(res.weights.iloc[-1].sum()) <= 1.0
    assert (res.cash >= 0).all()


# ---------------------------------------------------------------------------
# (g) Coûts conformes au CostModel
# ---------------------------------------------------------------------------


def test_costs_match_cost_model_trade_by_trade() -> None:
    panels = random_market(n=120, n_sym=5, seed=5, zero_frac=0.2)
    costs = CostModel(
        sgi_commission=0.007,
        brvm_fee=0.002,
        dcbr_fee=0.0012,
        regulator_fee=0.0007,
        vat_on_commission=0.18,
        min_ticket_fcfa=1500.0,
        impact_coef=0.35,
    )
    ex = ExecutionModel(max_volume_participation=0.25)
    res = Backtester(panels, costs, ex, capital=4e6).run(
        const_strategy({"S0C": 0.3, "S1C": 0.3, "S2C": 0.3}), rebalance="M"
    )
    tr = res.trades
    assert len(tr) > 5
    vol = panels["volume"]
    value = panels["value"]
    rate = 0.007 * 1.18 + 0.002 + 0.0012 + 0.0007
    assert costs.rate() == pytest.approx(rate)
    for _, row in tr.iterrows():
        v_day = float(vol.loc[row["date"], row["symbol"]])  # type: ignore[union-attr]
        vwap = float(value.loc[row["date"], row["symbol"]]) / v_day  # type: ignore[union-attr]
        assert row["price"] == pytest.approx(vwap, rel=1e-12)
        assert abs(row["qty"]) <= math.floor(0.25 * v_day + 1e-9)
        amount = abs(row["qty"]) * vwap
        part = abs(row["qty"]) / v_day
        expected = max(rate * amount, 1500.0) + 0.35 * math.sqrt(part) * amount
        assert row["value"] == pytest.approx(amount, rel=1e-12)
        assert row["participation"] == pytest.approx(part, rel=1e-12)
        assert row["cost"] == pytest.approx(expected, rel=1e-12)
    assert res.total_costs == pytest.approx(float(tr["cost"].sum()), rel=1e-12)
    assert res.costs.is_monotonic_increasing
    # comptabilité : capital − coûts + P&L = NAV finale
    q_end = res.positions.iloc[-1]
    px_end = panels["close"].iloc[-1]  # type: ignore[union-attr]
    flows = float((-tr["qty"] * tr["price"]).sum()) - float(tr["cost"].sum())
    assert float(res.equity.iloc[-1]) == pytest.approx(4e6 + flows + float((q_end * px_end).sum()), rel=1e-10)


def test_trade_cost_function() -> None:
    c = CostModel(min_ticket_fcfa=1000.0, impact_coef=0.1)
    got = trade_cost(np.array([0.0, 10_000.0, 1e7]), np.array([0.0, 0.04, 0.16]), c)
    assert got[0] == 0.0
    assert got[1] == pytest.approx(1000.0 + 0.1 * 0.2 * 10_000.0)
    assert got[2] == pytest.approx(c.rate() * 1e7 + 0.1 * 0.4 * 1e7)


def test_turnover_and_capital_gains_tax_and_custody() -> None:
    dates = _dates(21)
    close = pd.DataFrame({"AAAC": [1000.0] * 10 + [1100.0] * 11}, index=dates)
    panels = make_panels(close)
    taxes = TaxModel(capital_gains_tax=0.10)

    def strat(asof: pd.Timestamp, view: PanelView) -> pd.Series:
        return pd.Series({"AAAC": 0.5 if asof == dates[0] else 0.0})

    res = Backtester(panels, NO_IMPACT, taxes, capital=1e6).run(strat, rebalance=[dates[0], dates[14]])
    buy, sell = res.trades.iloc[0], res.trades.iloc[1]
    basis = buy["value"] + buy["cost"]
    gain = sell["value"] - sell["cost"] - basis
    assert float(res.taxes.sum()) == pytest.approx(0.10 * gain)
    expected_to = (buy["value"] / (2 * 1e6) + sell["value"] / (2 * float(res.equity.iloc[14]))) * 252 / 21
    assert res.turnover == pytest.approx(expected_to)

    # droits de garde : payés même investi à 100 %, sans découvert
    costs = CostModel(impact_coef=0.0, annual_custody=0.252)
    r2 = Backtester(panels, costs, capital=1e6).run(const_strategy({"AAAC": 1.0}), rebalance=None)
    assert (r2.cash >= 0).all()
    q = int(r2.positions.iloc[-1, 0])
    fee_day5 = 0.001 * q * 1000.0
    assert float(r2.costs_daily.iloc[5]) == pytest.approx(fee_day5)


# ---------------------------------------------------------------------------
# Calendrier, configuration, synthèse
# ---------------------------------------------------------------------------


def test_rebalance_dates_rules() -> None:
    cal = pd.bdate_range("2024-01-01", "2024-07-31")
    cal = cal.drop(pd.Timestamp("2024-03-29"))  # vendredi férié
    w = rebalance_dates(cal, "W-FRI")
    assert pd.Timestamp("2024-03-28") in w and pd.Timestamp("2024-03-29") not in w
    assert all(d.dayofweek == 4 for d in w if d != pd.Timestamp("2024-03-28") and d != cal[-1])
    m = rebalance_dates(cal, "M")
    assert list(m[:3]) == [pd.Timestamp("2024-01-31"), pd.Timestamp("2024-02-29"), pd.Timestamp("2024-03-28")]
    assert list(rebalance_dates(cal, "ME")) == list(m)
    q = rebalance_dates(cal, "Q")
    assert list(q) == [pd.Timestamp("2024-03-28"), pd.Timestamp("2024-06-28"), pd.Timestamp("2024-07-31")]
    first = rebalance_dates(cal, "M", anchor="first")
    assert first[0] == pd.Timestamp("2024-01-01") and first[1] == pd.Timestamp("2024-02-01")
    lst = rebalance_dates(cal, ["2024-03-30", "2024-03-29", "2023-01-01", "2024-02-15"])
    assert list(lst) == [pd.Timestamp("2024-02-15"), pd.Timestamp("2024-03-28")]
    assert len(rebalance_dates(cal, "D")) == len(cal)
    assert list(rebalance_dates(cal, 50)) == list(cal[::50])
    assert list(rebalance_dates(cal, None)) == [cal[0]]
    with pytest.raises(ValueError):
        rebalance_dates(cal, "X")


def test_argument_orders_and_config() -> None:
    panels = random_market(n=30)
    c, k, e, t = CostModel(), Constraints(), ExecutionModel(), TaxModel()
    b1 = Backtester(panels, c, k, 2e6)  # contrat ARCHITECTURE.md
    b2 = Backtester(panels, c, e, t, 2e6)  # contrat de la spécification du module
    assert b1.capital == b2.capital == 2e6
    assert b1.constraints is k and b2.execution is e and b2.taxes is t
    with pytest.raises(TypeError):
        Backtester(panels, c, c)
    with pytest.raises(TypeError):
        Backtester(panels, "pas un modèle")
    cfg = PlatformConfig(capital_fcfa=3e6)
    assert Backtester.from_config(panels, cfg).capital == 3e6
    with pytest.raises(KeyError):
        Backtester({"close": panels["close"]})


def test_constraints_cash_buffer_and_no_trade_band() -> None:
    dates = _dates(12)
    close = pd.DataFrame({"AAAC": 1000.0, "BBBS": 1000.0}, index=dates)
    panels = make_panels(close)
    k = Constraints(cash_buffer=0.10, no_trade_band=0.05)
    weights = iter([{"AAAC": 0.5, "BBBS": 0.5}, {"AAAC": 0.53, "BBBS": 0.47}, {"AAAC": 0.0, "BBBS": 0.9}])

    def strat(asof: pd.Timestamp, view: PanelView) -> pd.Series:
        return pd.Series(next(weights))

    res = Backtester(panels, NO_IMPACT, k, capital=1e6).run(strat, rebalance=[dates[0], dates[3], dates[6]])
    invested = float((res.positions.iloc[2] * 1000.0).sum())
    assert invested <= 0.90 * 1e6 + 1e-6  # exposition plafonnée à 1 − cash_buffer (NAV de décision)
    assert invested == pytest.approx(0.90 * 1e6)
    assert res.trades[res.trades["decision_date"] == dates[3]].empty  # |Δw| < bande
    assert int(res.positions.iloc[-1]["AAAC"]) == 0  # sortie totale malgré la bande


def test_strategy_object_with_target_weights_and_none() -> None:
    panels = random_market(n=40)

    class Model:
        calls = 0

        def target_weights(self, asof: pd.Timestamp, view: PanelView) -> pd.Series | None:
            Model.calls += 1
            return pd.Series({"S0C": 0.5}) if Model.calls == 1 else None

    res = Backtester(panels, capital=1e6).run(Model(), rebalance="W-FRI")
    assert Model.calls == len(res.rebalance_dates)
    assert len(res.orders) == 1


def test_view_exposes_portfolio_state() -> None:
    panels = random_market(n=40, zero_frac=0.0)
    states: list[tuple[float, float, int]] = []

    def strat(asof: pd.Timestamp, view: PanelView) -> pd.Series:
        states.append((float(view.nav), float(view.weights.sum()), int(view.positions.sum())))
        return pd.Series({"S0C": 0.3})

    Backtester(panels, capital=1e6).run(strat, rebalance="W-FRI")
    assert states[0] == (1e6, 0.0, 0)
    assert states[-1][2] > 0 and 0.0 < states[-1][1] <= 1.0


def test_summary_uses_stats_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    panels = random_market(n=150, seed=4)
    res = Backtester(panels, capital=1e7).run(const_strategy({"S0C": 0.4, "S1C": 0.4}), rebalance="M")
    assert isinstance(res, BacktestResult)
    bench_level = pd.Series(100.0 * np.cumprod(1 + np.full(150, 0.0002)), index=panels["close"].index)  # type: ignore[union-attr]
    full = res.summary(bench_level)
    for key in ("cagr", "sharpe", "max_drawdown", "information_ratio", "turnover", "fill_rate", "total_costs", "psr"):
        assert key in full
    assert full["benchmark_cagr"] == pytest.approx(1.0002**252 - 1, rel=1e-6)
    monkeypatch.setitem(sys.modules, "brvm_alpha.quant.stats", None)  # import impossible -> repli
    mini = res.summary(bench_level)
    assert "psr" not in mini
    assert mini["cagr"] == pytest.approx(full["cagr"], rel=1e-12)
    assert mini["max_drawdown"] == pytest.approx(full["max_drawdown"], rel=1e-12)
    assert mini["benchmark_cagr"] == pytest.approx(full["benchmark_cagr"], rel=1e-9)


def test_summary_benchmark_level_normalised_to_one_is_detected() -> None:
    """Non-régression : un indice total return base 1 n'est pas pris pour des rendements."""
    rng = np.random.default_rng(0)
    dates = _dates(252)
    close = pd.DataFrame({"SNTS": 1000.0 * np.cumprod(1.0 + rng.normal(0.0004, 0.01, 252))}, index=dates)
    res = Backtester(make_panels(close), capital=1e7).run(const_strategy({"SNTS": 0.9}), rebalance=None)
    level = close["SNTS"] / close["SNTS"].iloc[0]  # niveaux ≈ 0,9-1,3 (médiane < 1,5)
    auto = res.summary(level)
    explicit = res.summary(level, benchmark_is_level=True)
    rets = res.summary(level.pct_change())  # la même référence donnée en rendements
    expected_cagr = (level.iloc[-1] / level.iloc[0]) ** (252 / 251) - 1.0
    for key in ("benchmark_cagr", "excess_cagr", "information_ratio", "beta", "tracking_error"):
        assert auto[key] == pytest.approx(explicit[key], rel=1e-12), key
        assert rets[key] == pytest.approx(explicit[key], rel=1e-9), key
    assert abs(auto["benchmark_cagr"] - expected_cagr) < 0.02
    assert 0.5 < auto["beta"] < 1.5
    b = eng._benchmark_returns(level, pd.DatetimeIndex(res.returns.index), None)
    assert abs(float(b.mean())) < 0.01
    # rendements en % (ambigus) : erreur explicite plutôt que des métriques fausses
    with pytest.raises(ValueError, match="benchmark_is_level"):
        res.summary(level.pct_change() * 100.0)
    with pytest.warns(UserWarning, match="invraisemblable"):
        res.summary(level.pct_change() * 100.0, benchmark_is_level=False)


def test_lot_size_and_adj_factor() -> None:
    dates = _dates(6)
    close = pd.DataFrame({"SNTS": 100.0}, index=dates)  # cours ajusté (division par 10)
    raw_vol = pd.DataFrame({"SNTS": 50.0}, index=dates)  # volume brut
    panels = make_panels(close, volume=raw_vol)
    panels["value"] = raw_vol * 1000.0  # valeur au cours brut 1000
    panels["prev_close"] = pd.DataFrame({"SNTS": 1000.0}, index=dates)
    panels["adj_factor"] = pd.DataFrame({"SNTS": 0.1}, index=dates)
    ex = ExecutionModel(max_volume_participation=0.2)
    res = Backtester(panels, NO_IMPACT, ex, capital=1e5, lot_size=10).run(const_strategy({"SNTS": 0.5}), rebalance=None)
    # VWAP ajusté = 1000 × 0,1 ; volume ajusté 500 -> au plus 100 titres par séance
    assert np.allclose(res.trades["price"], 100.0)
    assert (res.trades["qty"] % 10 == 0).all() and (res.trades["qty"] <= 100).all()
    assert res.blocked[res.blocked["reason"].isin(["limit_up", "limit_down"])].empty


# ---------------------------------------------------------------------------
# Conversion depuis le panel long
# ---------------------------------------------------------------------------


def test_panels_from_equities_and_dividend_inference() -> None:
    dates = _dates(6)
    rows = []
    for i, d in enumerate(dates):
        for sym in ("SNTS", "ORAC"):
            new_div = sym == "SNTS" and i >= 3
            rows.append(
                {
                    "date": d,
                    "symbol": sym,
                    "close": 1000.0,
                    "prev_close": 1000.0,
                    "volume": 10.0 * (i + 1),
                    "value": 10_000.0 * (i + 1),
                    "status": "traded",
                    "sector": "TEL",
                    "last_div_net": 900.0 if new_div else 800.0,
                    "last_div_date": pd.Timestamp("2026-06-01") if new_div else pd.Timestamp("2025-06-01"),
                }
            )
    long = pd.DataFrame(rows)
    p = panels_from_equities(long)
    assert p["close"].shape == (6, 2)  # type: ignore[union-attr]
    div = p["dividend_net"]
    assert float(div.loc[dates[3], "SNTS"]) == 900.0  # type: ignore[union-attr]
    assert float(div.to_numpy().sum()) == 900.0  # type: ignore[union-attr]
    assert p["country"]["SNTS"] == "SN" and p["country"]["ORAC"] == "CI"  # type: ignore[index]
    res = Backtester(p, capital=1e6).run(const_strategy({"SNTS": 0.5}), rebalance=None)
    assert float(res.dividends.sum()) > 0


def _split_long(n: int = 60, k: float = 10.0, split_i: int = 40) -> pd.DataFrame:
    """Titre fictif : division 1:k à la séance ``split_i`` sans variation économique.

    Comme au BOC, le « cours précédent » publié le jour de la division est
    ajusté (``P_{t-1} / k``).
    """
    dates = _dates(n)
    raw_close = np.where(np.arange(n) < split_i, 20000.0, 20000.0 / k)
    raw_vol = np.where(np.arange(n) < split_i, 1000.0, 1000.0 * k)
    prev = np.r_[raw_close[0], raw_close[:-1]]
    prev[split_i] = raw_close[split_i - 1] / k
    return pd.DataFrame(
        {
            "date": dates,
            "symbol": "SNTS",
            "close": raw_close,
            "volume": raw_vol,
            "value": raw_close * raw_vol,
            "prev_close": prev,
            "change_pct": 0.0,
            "status": "traded",
        }
    )


def test_panels_from_equities_split_builds_adj_factor() -> None:
    """Non-régression : close ajusté ⇒ adj_factor (dividende, VWAP et plafond en unités ajustées)."""
    k = 10.0
    eq = _split_long(k=k)
    dates = pd.DatetimeIndex(eq["date"])
    raw = eq.set_index("date")[["close"]].rename(columns={"close": "SNTS"})
    adj = pd.DataFrame({"SNTS": np.where(np.arange(60) < 40, raw["SNTS"] / k, raw["SNTS"])}, index=dates)
    div_raw = pd.DataFrame(0.0, index=dates, columns=["SNTS"])
    div_raw.iloc[20, 0] = 1000.0  # dividende brut par titre AVANT division (5 % de 20 000)
    panels = panels_from_equities(eq, close=adj, dividend_net=div_raw)
    assert "adj_factor" in panels
    af = panels["adj_factor"]["SNTS"]  # type: ignore[index]
    assert np.allclose(af.iloc[:40], 1.0 / k) and np.allclose(af.iloc[40:], 1.0)

    bt = Backtester(panels, NO_IMPACT, capital=1e7)
    res = bt.run(const_strategy({"SNTS": 0.5}), rebalance=None)
    q = int(res.positions.iloc[19, 0])  # titres « ajustés »
    assert float(res.dividends.sum()) == pytest.approx(q / k * 1000.0)  # et non q × 1000
    assert bt.n_vwap_fallback == 0
    assert int(res.trades["qty"].iloc[0]) == int(0.2 * 1000.0 * k)  # 20 % du volume ajusté
    assert np.allclose(res.trades["price"], 2000.0)
    assert bt.price_jumps.empty


def test_panels_from_equities_adjusts_raw_prices_by_default_and_view_is_point_in_time() -> None:
    """Sans ``close`` : cours ajustés par le store (plus de krach à la division) ; vue en unités du jour."""
    k = 10.0
    eq = _split_long(k=k)
    dates = pd.DatetimeIndex(eq["date"])
    panels = panels_from_equities(eq)
    assert "adj_factor" in panels
    obs: dict[pd.Timestamp, tuple[float, float, float]] = {}

    def strat(asof: pd.Timestamp, view: PanelView) -> pd.Series:
        c = view["close"]["SNTS"]
        obs[asof] = (float(c.iloc[-1]), float(view["adj_factor"]["SNTS"].iloc[-1]), float(view.positions["SNTS"]))
        if asof == dates[20]:
            # cours de la veille de décision = cours publié, aucune trace de la division future
            assert np.allclose(c, 20000.0)
        return pd.Series({"SNTS": 0.9})

    res = Backtester(panels, capital=1e7).run(strat, rebalance="D")
    assert abs(float(res.returns.iloc[40])) < 1e-9  # jour de la division : rendement nul
    assert float(res.equity.iloc[-1]) > 0.9e7
    for day, (last_close, factor, _) in obs.items():
        raw_close = float(eq.loc[eq["date"] == day, "close"].iloc[0])
        assert last_close == pytest.approx(raw_close) and factor == pytest.approx(1.0)
    q_before = obs[dates[38]][2]
    q_after = obs[dates[41]][2]
    assert q_after == pytest.approx(q_before * k, rel=0.02)  # titres réels multipliés par k
    # chemin explicite sans ajustement : avertissement + détection du saut par le moteur
    with pytest.warns(UserWarning, match="BRUTS"):
        raw_panels = panels_from_equities(eq, adjust=False)
    with pytest.warns(UserWarning, match="invraisemblable"):
        bt = Backtester(raw_panels, capital=1e7)
    assert list(bt.price_jumps["date"]) == [dates[40]]


D_SNTS = 1740.0  # SNTS 2026 : dividende net 1 740 FCFA


def _dividend_long(div_dates: list[pd.Timestamp | None], ex_i: int, n: int = 40) -> pd.DataFrame:
    """Détachement à la séance ``ex_i`` (marqueur (d) et référence abaissée la veille)."""
    dates = pd.bdate_range("2026-05-04", periods=n)
    close = np.where(np.arange(n) < ex_i, 28900.0, 28900.0 - D_SNTS)
    rows = []
    for i, d in enumerate(dates):
        rows.append(
            {
                "date": d,
                "symbol": "SNTS",
                "close": close[i],
                "prev_close": close[i - 1] if i else close[0],
                "change_pct": 0.0,
                "volume": 1e5,
                "value": close[i] * 1e5,
                "status": "traded",
                "ref_price": close[i] - D_SNTS if i == ex_i - 1 else close[i],
                "ex_div": i == ex_i - 1,
                "flags": "",
                "last_div_net": 1655.0 if div_dates[i] is None else D_SNTS,
                "last_div_date": pd.Timestamp("2025-05-20") if div_dates[i] is None else div_dates[i],
            }
        )
    return pd.DataFrame(rows)


def test_dividend_credited_at_ex_date_not_at_late_boc_update() -> None:
    """Non-régression : colonne « dernier dividende » mise à jour 15 séances après le détachement."""
    n, ex_i, seen_i = 40, 14, 29
    eq = _dividend_long([None] * seen_i + [pd.Timestamp("2026-05-26")] * (n - seen_i), ex_i, n)
    dates = pd.DatetimeIndex(eq["date"])
    p = panels_from_equities(eq)
    div = p["dividend_net"]["SNTS"]  # type: ignore[index]
    assert div[div > 0].index.tolist() == [dates[ex_i]] and float(div.sum()) == D_SNTS
    # achat APRÈS le détachement (cours déjà ex-dividende) : aucun droit
    late = Backtester(p, NO_IMPACT, capital=1e8).run(const_strategy({"SNTS": 0.9}), rebalance=[dates[ex_i + 1]])
    assert len(late.trades) == 1 and float(late.dividends.sum()) == 0.0
    # détenteur au détachement, vendu AVANT la mise à jour du BOC : il touche le dividende
    def hold_then_sell(asof: pd.Timestamp, view: PanelView) -> pd.Series:
        return pd.Series({"SNTS": 0.9 if asof < dates[ex_i] else 0.0})

    early = Backtester(p, NO_IMPACT, capital=1e8).run(hold_then_sell, rebalance=[dates[0], dates[ex_i + 2]])
    q = int(early.positions.iloc[ex_i - 1, 0])
    assert q > 0 and int(early.positions.iloc[-1, 0]) == 0
    assert float(early.dividends.iloc[ex_i]) == pytest.approx(q * D_SNTS)
    assert float(early.dividends.sum()) == pytest.approx(q * D_SNTS)


def test_dividend_date_correction_is_credited_once() -> None:
    """Non-régression : correction de date à montant identique ⇒ un seul dividende."""
    n, ex_i = 40, 14
    dl: list[pd.Timestamp | None] = [None] * 10 + [pd.Timestamp("2026-05-20")] * 5
    dl += [pd.Timestamp("2026-05-26")] * (n - 15)
    eq = _dividend_long(dl, ex_i, n)
    dates = pd.DatetimeIndex(eq["date"])
    p = panels_from_equities(eq)
    div = p["dividend_net"]["SNTS"]  # type: ignore[index]
    assert div[div > 0].index.tolist() == [dates[ex_i]]
    res = Backtester(p, NO_IMPACT, capital=1e8).run(const_strategy({"SNTS": 0.9}), rebalance=None)
    q = int(res.positions.iloc[-1, 0])
    assert float(res.dividends.sum()) == pytest.approx(q * D_SNTS)
    # repli explicite « last_div » : avertissement, fusion de la correction
    with pytest.warns(UserWarning, match="last_div"):
        p2 = panels_from_equities(eq, dividend_method="last_div")
    d2 = p2["dividend_net"]["SNTS"]  # type: ignore[index]
    assert d2[d2 > 0].index.tolist() == [dates[10]] and float(d2.sum()) == D_SNTS
    # table d'événements fournie (dividends.parquet) : utilisée telle quelle
    table = pd.DataFrame({"symbol": ["SNTS"], "ex_date": [dates[ex_i]], "amount": [D_SNTS]})
    p3 = panels_from_equities(eq, dividends=table)
    pd.testing.assert_frame_equal(p3["dividend_net"], p["dividend_net"])  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        panels_from_equities(eq, dividend_method="nope")


def test_dividend_on_missing_session_is_credited_next_session() -> None:
    dates = _dates(10)
    cal = dates.delete(5)  # séance du détachement absente du panel (BOC manquant)
    close = pd.DataFrame({"SNTS": [1000.0] * 5 + [950.0] * 4}, index=cal)
    div = pd.DataFrame({"SNTS": [30.0, 50.0]}, index=[dates[0] - pd.Timedelta(days=3), dates[5]])
    panels = make_panels(close, dividend=div)
    bt = Backtester(panels, NO_IMPACT, capital=1e6)
    res = bt.run(const_strategy({"SNTS": 0.5}), rebalance=None)
    q = int(res.positions.iloc[4, 0])
    assert float(res.dividends.loc[dates[6]]) == pytest.approx(q * 50.0)
    assert float(res.dividends.sum()) == pytest.approx(q * 50.0)  # dividende antérieur ignoré
    assert res.meta["n_dividend_dates_off_calendar"] == 2


@pytest.mark.skipif(not PANEL.exists(), reason="panel réel absent")
def test_smoke_real_panel() -> None:
    eq = pd.read_parquet(PANEL)
    eq = eq[pd.to_datetime(eq["date"]) >= pd.to_datetime(eq["date"]).max() - pd.DateOffset(years=2)]
    panels = panels_from_equities(eq)

    def equal_liquid(asof: pd.Timestamp, view: PanelView) -> pd.Series:
        v = view["value"].iloc[-60:].median()
        top = v.nlargest(10).index
        return pd.Series(0.098, index=top)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # ruptures inexpliquées éventuelles du panel réel
        bt = Backtester(panels, capital=1e7)
    res = bt.run(equal_liquid, rebalance="M")
    assert np.isfinite(res.equity).all() and (res.cash >= 0).all()
    assert len(res.trades) > 0
    assert "adj_factor" in panels and res.meta["adj_factor"]
    s = res.summary()
    assert np.isfinite(s["cagr"])


# ---------------------------------------------------------------------------
# Walk-forward
# ---------------------------------------------------------------------------


def test_walk_forward_windows_expanding_and_embargo() -> None:
    cal = pd.bdate_range("2018-01-01", "2023-12-31")
    wins = walk_forward_windows(cal, train_years=2, test_months=6, embargo_days=5)
    assert len(wins) == 8  # 2020-01 → 2023-12 par semestres
    pos = {d: i for i, d in enumerate(cal)}
    prev_end = None
    for w in wins:
        assert w.train_start == cal[0]  # expansif
        assert w.train_end < w.test_start
        assert pos[w.test_start] - pos[w.train_end] - 1 == 5 == len(w.embargo)
        if prev_end is not None:
            assert pos[w.test_start] == pos[prev_end] + 1  # tests contigus, disjoints
        prev_end = w.test_end
    assert wins[0].test_start == pd.Timestamp("2020-01-01")
    assert wins[-1].test_end == cal[-1]
    assert len(set().union(*[set(w.test) for w in wins])) == sum(len(w.test) for w in wins)


def test_walk_forward_windows_rolling_and_partial() -> None:
    cal = pd.bdate_range("2018-01-01", "2022-03-15")
    wins = walk_forward_windows(cal, train_years=1.5, test_months=12, embargo_days=0, expanding=False)
    for w in wins:
        assert w.train_start >= w.test_start - pd.DateOffset(months=18)
        assert w.train_start < w.test_start - pd.DateOffset(months=17)
        assert len(w.embargo) == 0
    assert wins[-1].test_end == cal[-1]  # dernière fenêtre partielle conservée
    full = walk_forward_windows(cal, 1.5, 12, expanding=False, allow_partial=False)
    assert len(full) == len(wins) - 1
    with pytest.raises(ValueError):
        walk_forward_windows(cal, 0, 6)


def test_walk_forward_no_information_overlap() -> None:
    """Étiquettes à horizon h : avec embargo h, aucune n'utilise une séance de test."""
    rng = np.random.default_rng(1)
    cal = pd.bdate_range("2019-01-01", "2023-06-30")
    rets = pd.Series(rng.normal(0, 0.01, len(cal)), index=cal)
    h = 10
    pos = pd.Series(np.arange(len(cal)), index=cal)
    seen_train: list[pd.DatetimeIndex] = []

    def fit(train: pd.DatetimeIndex) -> float:
        seen_train.append(train)
        return float(rets.loc[train].mean())

    def apply(model: float, test: pd.DatetimeIndex) -> pd.Series:
        out = rets.reindex(test.union(test - pd.offsets.BDay(3)))  # déborde volontairement
        return out * np.sign(model)

    res = walk_forward(fit, apply, cal, train_years=2, test_months=3, embargo_days=h)
    for w, tr in zip(res.windows, seen_train, strict=True):
        last_label_pos = int(pos[tr[-1]]) + h  # l'étiquette en s utilise ]s, s+h]
        assert last_label_pos < int(pos[w.test_start])
    oos = res.oos
    assert isinstance(oos, pd.Series)
    assert not oos.index.has_duplicates  # sorties recadrées sur les fenêtres de test
    assert oos.index.min() == res.windows[0].test_start
    assert len(oos) == sum(len(w.test) for w in res.windows)
    tab = res.summary()
    assert list(tab["n_embargo"].unique()) == [h]


def test_run_param_grid_feeds_pbo() -> None:
    panels = random_market(n=260, n_sym=6, seed=21, zero_frac=0.2)

    def backtest(lookback: int, top: int) -> BacktestResult:
        def strat(asof: pd.Timestamp, view: PanelView) -> pd.Series:
            c = view["close"]
            if len(c) <= lookback:
                return pd.Series(dtype=float)
            mom = c.iloc[-1] / c.iloc[-1 - lookback] - 1.0
            return pd.Series(0.95 / top, index=mom.nlargest(top).index)

        return Backtester(panels, capital=1e7).run(strat, rebalance="W-FRI")

    grid = {"lookback": [5, 20], "top": [2, 3]}
    assert param_grid(grid) == [
        {"lookback": 5, "top": 2},
        {"lookback": 5, "top": 3},
        {"lookback": 20, "top": 2},
        {"lookback": 20, "top": 3},
    ]
    frame = run_param_grid(backtest, grid)
    assert frame.shape == (260, 4)
    assert list(frame.columns) == ["lookback=5|top=2", "lookback=5|top=3", "lookback=20|top=2", "lookback=20|top=3"]
    assert frame.attrs["n_trials"] == 4
    assert frame.attrs["params"]["lookback=20|top=3"] == {"lookback": 20, "top": 3}
    # déterminisme
    again = run_param_grid(backtest, [{"lookback": 5, "top": 2}], labels=["a"])
    np.testing.assert_allclose(again["a"].to_numpy(), frame.iloc[:, 0].to_numpy())
    stats = pytest.importorskip("brvm_alpha.quant.stats")
    out = stats.pbo_cscv(frame, n_splits=4)
    assert 0.0 <= out["pbo"] <= 1.0


def test_run_param_grid_rejects_bad_outputs() -> None:
    with pytest.raises(TypeError):
        run_param_grid(lambda x: 3.0, {"x": [1]})
    with pytest.raises(ValueError):
        run_param_grid(lambda x: pd.Series([np.inf], index=_dates(1)), {"x": [1]})
    s = pd.Series([0.01, 0.02], index=_dates(2))
    f = run_param_grid(lambda x: s * x, {"x": [1, 1]})
    assert list(f.columns) == ["x=1", "x=1#1"]


def test_module_exports() -> None:
    for name in eng.__all__:
        assert hasattr(eng, name)

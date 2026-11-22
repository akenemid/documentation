"""Tests de brvm_alpha.backtest (moteur quotidien, walk-forward, grilles).

Toutes les données sont synthétiques et générées avec une graine fixe ; chaque
propriété du moteur est vérifiée contre un calcul indépendant écrit à la main
(formules de coûts, quantités, dividendes). Un test « smoke » utilise le panel
réel ``data/panel/equities.parquet`` s'il existe.
"""

from __future__ import annotations

import math
import sys
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


@pytest.mark.skipif(not PANEL.exists(), reason="panel réel absent")
def test_smoke_real_panel() -> None:
    eq = pd.read_parquet(PANEL)
    eq = eq[pd.to_datetime(eq["date"]) >= pd.to_datetime(eq["date"]).max() - pd.DateOffset(years=2)]
    panels = panels_from_equities(eq)

    def equal_liquid(asof: pd.Timestamp, view: PanelView) -> pd.Series:
        v = view["value"].iloc[-60:].median()
        top = v.nlargest(10).index
        return pd.Series(0.098, index=top)

    res = Backtester(panels, capital=1e7).run(equal_liquid, rebalance="M")
    assert np.isfinite(res.equity).all() and (res.cash >= 0).all()
    assert len(res.trades) > 0
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

"""Tests de non-régression des corrections du moteur (revue du moteur v1, 22/11/2026).

Chaque test échouait avant la correction correspondante de ``brvm_alpha/backtest/engine.py``.
Données **synthétiques** uniquement : aucun backtest, aucune performance sur l'échantillon
vierge S1.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

from brvm_alpha.backtest.engine import Backtester, PanelView, band_flags
from brvm_alpha.config import Constraints, CostModel

ZERO = CostModel(
    sgi_commission=0.0,
    brvm_fee=0.0,
    dcbr_fee=0.0,
    regulator_fee=0.0,
    impact_coef=0.0,
    annual_custody=0.0,
    half_spread_mult=0.0,
    account_fee_per_line_fcfa=0.0,
)


def _dates(n: int, start: str = "2030-01-07") -> pd.DatetimeIndex:
    return pd.bdate_range(start, periods=n)


def _panels(close: pd.DataFrame, volume: float | pd.DataFrame = 1e6) -> dict[str, object]:
    vol = volume if isinstance(volume, pd.DataFrame) else pd.DataFrame(float(volume), index=close.index,
                                                                         columns=close.columns)
    return {
        "close": close,
        "volume": vol,
        "value": close * vol,
        "ref_price": close.copy(),
        "status": pd.DataFrame(np.where(vol > 0, "traded", "not_traded"), index=close.index, columns=close.columns),
    }


def _at(weights: dict[pd.Timestamp, dict[str, float]]):
    def strat(asof: pd.Timestamp, view: object) -> pd.Series | None:
        w = weights.get(pd.Timestamp(asof))
        return None if w is None else pd.Series(w, dtype=float)

    return strat


# ---------------------------------------------------------------------------
# §6 : bande de non-transaction, sauf entrée ou sortie complète
# ---------------------------------------------------------------------------


def test_no_trade_band_exempts_new_entries() -> None:
    """Une ENTRÉE visée à 1,5 % (< bande de 2 points) est exécutée (§6) ; un ajustement < 2 points non."""
    dates = _dates(6)
    close = pd.DataFrame({"X": 1000.0, "Y": 1000.0}, index=dates)
    bt = Backtester(_panels(close), ZERO, Constraints(no_trade_band=0.02, cash_buffer=0.0), capital=1e7)
    res = bt.run(_at({dates[0]: {"X": 0.015, "Y": 0.30}, dates[2]: {"X": 0.015, "Y": 0.31}}), rebalance=[dates[0],
                                                                                                         dates[2]])
    bought = res.trades.groupby("symbol")["qty"].sum()
    assert bought["X"] == 150  # 1,5 % de 10 M à 1 000 FCFA : l'entrée n'est plus ignorée
    # ajustement de Y de 30 % à 31 % (< 2 points) : aucun ordre à la seconde décision
    assert len(res.trades[(res.trades["symbol"] == "Y")]) == 1


# ---------------------------------------------------------------------------
# §7.1.1 : report au plus 10 séances, contrôlé AVANT l'exécution
# ---------------------------------------------------------------------------


def test_order_expires_before_execution_after_boc_gap() -> None:
    """Séances 1, 2, 34, 35 : l'ordre décidé en séance 1 a 33 séances en séance 34 : il expire sans exécution."""
    dates = _dates(4)
    close = pd.DataFrame({"X": 1300.0}, index=dates)
    vol = pd.DataFrame({"X": [1e6, 0.0, 1e6, 1e6]}, index=dates)
    panels = _panels(close, vol)
    panels["session_no"] = pd.Series([1, 2, 34, 35], index=dates)
    res = Backtester(panels, ZERO, capital=1e7).run(_at({dates[0]: {"X": 0.5}}), rebalance=[dates[0]])
    assert res.trades.empty
    assert res.orders["status"].tolist() == ["expired"]
    assert "expiration_report_maximal" in set(res.events["event"])


# ---------------------------------------------------------------------------
# §6 : quotité de 1 titre RÉEL (arrondi en titres bruts du jour)
# ---------------------------------------------------------------------------


def _split_panels(future_split: bool) -> dict[str, object]:
    """Cours brut 1 000 ; avec ``future_split``, division 10:1 trois séances plus tard."""
    dates = _dates(8)
    raw = np.array([1000.0] * 4 + [100.0] * 4) if future_split else np.array([1000.0] * 8)
    f = np.where(np.arange(8) < 4, 0.1, 1.0) if future_split else np.ones(8)
    adj = raw * f
    close = pd.DataFrame({"X": adj}, index=dates)
    vol_raw = pd.DataFrame({"X": 1e6}, index=dates)
    return {
        "close": close,
        "adj_factor": pd.DataFrame({"X": f}, index=dates),
        "volume": vol_raw,
        "value": vol_raw * pd.DataFrame({"X": raw}, index=dates),
        "status": pd.DataFrame("traded", index=dates, columns=["X"]),
    }


@pytest.mark.parametrize("future_split", [False, True])
def test_lots_are_whole_real_shares_whatever_future_split(future_split: bool) -> None:
    panels = _split_panels(future_split)
    dates = panels["close"].index  # type: ignore[union-attr]
    res = Backtester(panels, ZERO, capital=10_000.0).run(_at({dates[0]: {"X": 0.99}}), rebalance=[dates[0]])
    buy = res.trades.iloc[0]
    assert int(buy["raw_qty"]) == 9  # ⌊9 900 / 1 000⌋ titres réels, identique avec ou sans division future
    f = panels["adj_factor"]["X"]  # type: ignore[index]
    real = res.positions["X"] * f.reindex(res.positions.index)
    assert np.allclose(real, np.round(real))  # positions entières en titres réels à chaque séance


def test_view_close_adj_and_split_factor_are_point_in_time() -> None:
    """``close_adj`` et ``split_factor`` (panels de la stratégie) ne révèlent pas une division future."""
    panels = _split_panels(True)
    dates = panels["close"].index  # type: ignore[union-attr]
    panels["close_adj"] = panels["close"]
    panels["split_factor"] = 1.0 / panels["adj_factor"]  # type: ignore[operator]
    seen: dict[str, float] = {}

    def strat(asof: pd.Timestamp, view: PanelView) -> None:
        seen["split_factor"] = float(view["split_factor"]["X"].iloc[-1])
        seen["close_adj"] = float(view["close_adj"]["X"].iloc[-1])
        return None

    Backtester(panels, ZERO, capital=1e6).run(strat, rebalance=[dates[1]])
    assert seen == {"split_factor": 1.0, "close_adj": 1000.0}


# ---------------------------------------------------------------------------
# §4.3 / §7.1.8 / ST4 : choc pays sévère de plusieurs séances
# ---------------------------------------------------------------------------


def _shock_bt(close: pd.DataFrame, sessions: int, **kw: object) -> Backtester:
    panels = _panels(close)
    panels["country"] = pd.Series({"X": "NE"})
    return Backtester(panels, ZERO, capital=1e7, country_shocks=[("NE", close.index[1], sessions)], **kw)


def test_multi_session_country_shock_cumulates_floors_without_rebound() -> None:
    dates = _dates(8)
    close = pd.DataFrame({"X": 1000.0}, index=dates)
    bt = _shock_bt(close, 3)
    val = bt._px_val[:, 0]
    # planchers en chaîne, arrondis au pas à chaque séance : 925, 860, 800 (≈ 1 000 × 0,925³)
    assert val[2:5].tolist() == [925.0, 860.0, 800.0]
    assert val[5:].tolist() == [800.0] * 3  # aucun rebond artificiel vers la clôture réelle
    res = bt.run(_at({dates[0]: {"X": 0.5}}), rebalance=[dates[0]])
    r = res.returns.to_numpy()
    assert np.all(r[5:] == 0.0) and float(res.equity.iloc[-1]) < float(res.equity.iloc[1])


def test_country_shock_floor_not_carried_over_nan_closes_in_shock_only_mode() -> None:
    dates = _dates(6)
    close = pd.DataFrame({"X": [1000.0, 1000.0, 1000.0, np.nan, np.nan, 1000.0]}, index=dates)
    bt = _shock_bt(close, 1, params={"country_shock_recovery": "shock_only"})
    assert bt._px_val[:, 0].tolist() == [1000.0, 1000.0, 925.0, 1000.0, 1000.0, 1000.0]
    bt = _shock_bt(close, 1)  # défaut « persistent » : niveau choqué conservé, cohérent ensuite
    assert bt._px_val[:, 0].tolist() == [1000.0, 1000.0, 925.0, 925.0, 925.0, 925.0]


# ---------------------------------------------------------------------------
# §7.1.3 : règle de tolérance sur la référence AJUSTÉE (jour ex)
# ---------------------------------------------------------------------------


def test_tolerance_rule_uses_adjusted_reference_on_ex_day() -> None:
    """SOGC 19/07/2018 : variation publiée −7,89 % (clôture non ajustée), +3,86 % contre la référence ajustée."""
    dates = _dates(4)
    close = pd.DataFrame({"X": [3620.0, 3620.0, 3500.0, 3500.0]}, index=dates)
    panels = _panels(close)
    panels["dividend_net"] = pd.DataFrame({"X": [0.0, 0.0, 250.0, 0.0]}, index=dates)
    panels["ref_price"] = pd.DataFrame({"X": [3620.0, 3370.0, 3500.0, 3500.0]}, index=dates)
    panels["prev_close"] = pd.DataFrame({"X": [3620.0, 3620.0, 3620.0, 3500.0]}, index=dates)
    panels["change_pct"] = pd.DataFrame({"X": [0.0, 0.0, -7.89, 0.0]}, index=dates)
    bt = Backtester(panels, ZERO, capital=1e7)
    assert not bt._lim_down[2, 0]
    res = bt.run(_at({dates[0]: {"X": 0.5}, dates[1]: {"X": 0.0}}), rebalance=[dates[0], dates[1]])
    assert (res.trades["qty"] < 0).any() and res.trades.loc[res.trades["qty"] < 0, "date"].iloc[0] == dates[2]


# ---------------------------------------------------------------------------
# Cours < 100 FCFA : bande dégénérée vers le bas
# ---------------------------------------------------------------------------


def test_unchanged_close_at_low_price_is_not_limit_down() -> None:
    up, down = band_flags(np.array([13.0, 12.0]), np.array([13.0, 13.0]))
    assert down.tolist() == [False, False]  # 12 < plancher 13 : signalé par la tolérance, pas par la bande
    dates = _dates(12)
    close = pd.DataFrame({"X": [14.0] + [13.0] * 11}, index=dates)
    panels = _panels(close, 5e6)
    res = Backtester(panels, ZERO, capital=1e6).run(_at({dates[0]: {"X": 0.5}, dates[2]: {"X": 0.0}}),
                                                    rebalance=[dates[0], dates[2]])
    assert int(res.positions["X"].iloc[-1]) == 0
    assert "limit_down" not in set(res.blocked["reason"])


# ---------------------------------------------------------------------------
# Radiation : position bloquée, suivie pour le risque
# ---------------------------------------------------------------------------


def test_delisted_position_is_tracked_and_blocked() -> None:
    dates = _dates(30)
    close = pd.DataFrame({"X": [1000.0] * 15 + [np.nan] * 15, "Y": 1000.0}, index=dates)
    panels = _panels(close)
    panels["volume"] = panels["volume"].where(close.notna(), 0.0)  # type: ignore[union-attr]
    with pytest.warns(UserWarning, match="radiation"):
        res = Backtester(panels, ZERO, capital=1e7).run(_at({dates[0]: {"X": 0.5}, dates[20]: {"X": 0.0}}),
                                                        rebalance=[dates[0], dates[20]])
    assert float(res.suspended_value.iloc[-1]) == pytest.approx(5e6)
    assert "delisted" in set(res.blocked["reason"])
    assert res.meta["delisted_positions"][0]["symbol"] == "X"
    with pytest.warns(UserWarning, match="radiation"):
        res2 = Backtester(panels, ZERO, capital=1e7, params={"delisted_writedown": 0.30}).run(
            _at({dates[0]: {"X": 0.5}}), rebalance=[dates[0]])
    assert float(res2.equity.iloc[-1]) == pytest.approx(1e7 - 0.30 * 5e6)


# ---------------------------------------------------------------------------
# Valeur liquidative ≤ 0 (frais fixes supérieurs au capital)
# ---------------------------------------------------------------------------


def test_non_positive_nav_stops_returns_and_is_reported() -> None:
    dates = _dates(300)
    close = pd.DataFrame({"A": 100.0, "B": 100.0, "C": 100.0}, index=dates)
    costs = CostModel(sgi_commission=0.0, brvm_fee=0.0, dcbr_fee=0.0, impact_coef=0.0, annual_custody=0.0,
                      half_spread_mult=0.0, account_fee_per_line_fcfa=10_000.0)
    with pytest.warns(UserWarning, match="valeur liquidative ≤ 0"):
        res = Backtester(_panels(close), costs, capital=20_000.0).run(
            _at({dates[0]: {"A": 0.3, "B": 0.3, "C": 0.3}}), rebalance=[dates[0]])
    k0 = res.meta["nav_non_positive_from"]
    assert k0 is not None
    r = res.returns
    assert r.loc[k0] == -1.0 and r.loc[r.index > k0].isna().all()
    assert np.nanmin(r.to_numpy()) >= -1.0
    with pytest.warns(UserWarning, match="non fini"):
        s = res.summary()
    assert s["n_obs_excluded"] > 0 and s["n_obs_total"] == 300


def test_unknown_execution_key_in_full_config_is_rejected() -> None:
    dates = _dates(3)
    panels = _panels(pd.DataFrame({"X": 1000.0}, index=dates))
    with pytest.raises(KeyError, match="carry_unfilled_max_session"):
        Backtester(panels, ZERO, capital=1e6, params={"execution": {"carry_unfilled_max_session": 3}})
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        bt = Backtester(panels, ZERO, capital=1e6, params={"execution": {"carry_unfilled_max_sessions": 3}})
    assert bt.max_order_age == 4

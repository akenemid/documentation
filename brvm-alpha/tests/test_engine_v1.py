"""Tests du moteur de backtest v1 (spécification §7.1, §7.2 et §12.3 n° 3 et n° 7).

Cas synthétiques **exacts** (chaque grandeur est recalculée à la main) :
bornes de prix au pas, borne haute qui bloque l'achat et borne basse qui bloque
la vente, règlement J+3 / J+2, annulation et ressaisie des ordres le jour ex et
le jour de division, report des ordres au plus 10 séances, frais de tenue de
compte par ligne, droits de garde, demi-spread par titre, dividende crédité à
la date de paiement, suspension, choc pays sévère. Le rejeu réel de BOAN
(03 → 08/08/2023, échantillon S0) vérifie que les ventes ne sont pas servies
aux séances au plancher. Aucun calcul de performance n'est fait sur
l'échantillon vierge S1.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from brvm_alpha.backtest.engine import (
    ENGINE_DEFAULTS,
    Backtester,
    band_flags,
    panels_from_equities,
    price_band_limits,
    quoted_half_spread,
    settlement_lag_sessions,
    tick_size,
    trade_cost,
)
from brvm_alpha.backtest.metrics import overlaps_s1
from brvm_alpha.config import CostModel, ExecutionModel

ROOT = Path(__file__).resolve().parents[1]
PANEL_DIR = ROOT / "data" / "panel"

#: Aucun coût : isole la mécanique d'exécution.
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


def _dates(n: int, start: str = "2024-03-04") -> pd.DatetimeIndex:
    return pd.bdate_range(start, periods=n)


def mk(
    close: pd.DataFrame,
    *,
    volume: pd.DataFrame | float = 1e6,
    vwap: pd.DataFrame | None = None,
    ref: bool = True,
    status: pd.DataFrame | None = None,
    dividend: pd.DataFrame | None = None,
) -> dict[str, object]:
    """Panels minimaux ; ``ref_price`` publié = clôture du jour (référence de la séance suivante)."""
    vol = (
        volume
        if isinstance(volume, pd.DataFrame)
        else pd.DataFrame(float(volume), index=close.index, columns=close.columns)
    )
    px = close if vwap is None else vwap
    panels: dict[str, object] = {
        "close": close,
        "volume": vol,
        "value": px * vol,
        "prev_close": close.shift(1).fillna(close),
        "dividend_net": dividend
        if dividend is not None
        else pd.DataFrame(0.0, index=close.index, columns=close.columns),
        "status": status
        if status is not None
        else pd.DataFrame(np.where(vol > 0, "traded", "not_traded"), index=close.index, columns=close.columns),
    }
    if ref:
        panels["ref_price"] = close.copy()
    return panels


def hold_then(weights_by_date: dict[pd.Timestamp, dict[str, float]]):
    def strat(asof: pd.Timestamp, view: object) -> pd.Series | None:
        w = weights_by_date.get(pd.Timestamp(asof))
        return None if w is None else pd.Series(w, dtype=float)

    return strat


# ---------------------------------------------------------------------------
# Bornes de prix exactes (§7.1.3, §12.3 n° 3)
# ---------------------------------------------------------------------------


def test_price_band_non_regression_values() -> None:
    assert price_band_limits(4385) == (4060.0, 4710.0)
    assert price_band_limits(13)[1] == 14.0  # ETIT : au moins un pas vers le haut
    assert price_band_limits(13)[0] == 13.0  # ceil(12,025) = 13
    assert tick_size(99.0) == 1.0 and tick_size(100.0) == 5.0
    # BOAN 2023 : planchers successifs
    lows = price_band_limits(np.array([5495.0, 5085.0, 4705.0]))[0]
    assert lows.tolist() == [5085.0, 4705.0, 4355.0]
    try:
        from brvm_alpha.quant.macro import price_band
    except ImportError:  # pragma: no cover - module d'un autre agent
        return
    for r in (13.0, 22.0, 99.0, 100.0, 1003.0, 4385.0, 98900.0):
        assert price_band_limits(r) == pytest.approx(price_band(r))


def test_band_flags_exact_versus_tolerance() -> None:
    # référence 1003 : borne haute 1075 (+7,18 %, sous la tolérance de 7,3 %)
    up, down = band_flags(np.array([1075.0, 1070.0, 930.0, 935.0]), np.array([1003.0] * 4))
    assert up.tolist() == [True, False, False, False]
    assert down.tolist() == [False, False, True, False]
    # référence invraisemblable (division non ajustée) : aucun drapeau
    up, down = band_flags(np.array([100.0]), np.array([1000.0]))
    assert not up[0] and not down[0]


def test_buy_blocked_when_close_at_exact_upper_band() -> None:
    dates = _dates(6)
    close = pd.DataFrame({"BOAC": [1003.0, 1075.0, 1075.0, 1075.0, 1075.0, 1075.0]}, index=dates)
    panels = mk(close)
    strat = hold_then({dates[0]: {"BOAC": 0.5}})
    res = Backtester(panels, ZERO, capital=1e6).run(strat, rebalance=[dates[0]])
    blk = res.blocked[res.blocked["date"] == dates[1]]
    assert blk["reason"].tolist() == ["limit_up"]
    assert res.trades["date"].tolist() == [dates[2]]  # reporté puis exécuté
    assert res.trades["reason"].tolist() == ["carry"]
    # règle « tolérance » seule (+7,18 % < 7,3 %) : achat exécuté dès t+1
    res2 = Backtester(panels, ZERO, capital=1e6, band_rule="tolerance").run(strat, rebalance=[dates[0]])
    assert res2.trades["date"].tolist() == [dates[1]]


def test_sell_blocked_when_close_at_exact_lower_band() -> None:
    dates = _dates(7)
    close = pd.DataFrame({"SGBC": [1003.0, 1003.0, 1003.0, 930.0, 930.0, 930.0, 930.0]}, index=dates)
    panels = mk(close)
    strat = hold_then({dates[0]: {"SGBC": 0.5}, dates[2]: {"SGBC": 0.0}})
    res = Backtester(panels, ZERO, capital=1e6).run(strat, rebalance=[dates[0], dates[2]])
    sells = res.trades[res.trades["qty"] < 0]
    assert sells["date"].tolist() == [dates[4]]
    assert res.blocked.loc[res.blocked["date"] == dates[3], "reason"].tolist() == ["limit_down"]
    assert int(res.positions.iloc[-1, 0]) == 0


# ---------------------------------------------------------------------------
# Règlement J+3 / J+2 (§7.1.5)
# ---------------------------------------------------------------------------


def test_settlement_lag_switch_date() -> None:
    assert settlement_lag_sessions("2025-12-03") == 3
    assert settlement_lag_sessions("2025-12-04") == 2
    assert settlement_lag_sessions(pd.Timestamp("2017-01-02")) == 3


@pytest.mark.parametrize(("start", "lag"), [("2025-11-26", 3), ("2025-12-08", 2)])
def test_sale_proceeds_finance_buys_only_after_settlement(start: str, lag: int) -> None:
    dates = _dates(10, start)
    close = pd.DataFrame({"AAAC": 1000.0, "BBBS": 1000.0}, index=dates)
    panels = mk(close)
    strat = hold_then({dates[0]: {"AAAC": 0.98}, dates[2]: {"BBBS": 0.97}})
    res = Backtester(panels, ZERO, capital=1e6).run(strat, rebalance=[dates[0], dates[2]])
    sell = res.trades[res.trades["symbol"] == "AAAC"]
    buy = res.trades[res.trades["symbol"] == "BBBS"]
    assert sell["qty"].tolist() == [980, -980] and sell["date"].tolist() == [dates[1], dates[3]]
    # cible 970 BBBS : le jour de la vente, seuls les 20 000 FCFA déjà réglés financent
    # 20 titres ; le reste attend la date de règlement de la vente (J+lag)
    assert buy["date"].tolist() == [dates[3], dates[3 + lag]]
    assert buy["qty"].tolist() == [20, 950]
    blocked = res.blocked[(res.blocked["symbol"] == "BBBS")]
    assert blocked["date"].tolist() == list(dates[3 : 3 + lag]) and set(blocked["reason"]) == {"cash"}
    assert blocked["qty"].tolist() == [950] * lag
    # entre la vente et le règlement, le produit est une créance comptée dans la NAV
    for i in range(3, 3 + lag):
        assert float(res.receivables.iloc[i]) == pytest.approx(980_000.0)
        assert float(res.cash.iloc[i]) == pytest.approx(0.0)
        assert float(res.equity.iloc[i]) == pytest.approx(1e6)
    assert float(res.receivables.iloc[3 + lag]) == 0.0
    assert float(res.cash.iloc[3 + lag]) == pytest.approx(30_000.0)
    # règlement immédiat (option historique) : achat complet le jour même de la vente
    res0 = Backtester(panels, ZERO, capital=1e6, settlement=0).run(strat, rebalance=[dates[0], dates[2]])
    b0 = res0.trades[res0.trades["symbol"] == "BBBS"]
    assert b0["date"].tolist() == [dates[3]] and b0["qty"].tolist() == [970]


def test_settlement_counts_missing_sessions() -> None:
    """Un BOC manquant (2021) compte comme une séance pour le règlement."""
    dates = _dates(8, "2024-03-04")
    close = pd.DataFrame({"AAAC": 1000.0, "BBBS": 1000.0}, index=dates)
    panels = mk(close)
    sess = pd.Series([1, 2, 3, 4, 6, 7, 8, 9], index=dates)  # une séance sans BOC entre les lignes 3 et 4
    panels["session_no"] = sess
    strat = hold_then({dates[0]: {"AAAC": 0.98}, dates[2]: {"BBBS": 0.97}})
    res = Backtester(panels, ZERO, capital=1e6).run(strat, rebalance=[dates[0], dates[2]])
    # vente en ligne 3 (séance 4) : règlement J+3 = séance 7 = ligne 5 (et non la ligne 6)
    assert res.trades.loc[res.trades["symbol"] == "BBBS", "date"].tolist() == [dates[3], dates[5]]


# ---------------------------------------------------------------------------
# Jour ex et jour de division : annulation et ressaisie (§7.1.4)
# ---------------------------------------------------------------------------


def test_pending_orders_cancelled_and_reentered_on_ex_date() -> None:
    dates = _dates(8)
    close = pd.DataFrame({"SNTS": [1000.0] * 3 + [990.0] * 5}, index=dates)
    div = pd.DataFrame({"SNTS": [0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 0.0]}, index=dates)
    panels = mk(close, volume=1000.0, dividend=div)
    strat = hold_then({dates[0]: {"SNTS": 0.5}})
    res = Backtester(panels, ZERO, capital=1e6, dividend_payment_lag=0).run(strat, rebalance=[dates[0]])
    # 500 titres voulus, 10 % de 1 000 titres par séance : 100 par séance de t+1 à t+5
    assert res.trades["qty"].tolist() == [100] * 5
    assert res.trades["date"].tolist() == list(dates[1:6])
    od = res.orders
    assert od["status"].tolist() == ["cancelled_ex", "filled"]
    assert od["parent"].iloc[1] == od["oid"].iloc[0]
    assert od["entered"].tolist() == [dates[1], dates[3]]
    assert int(od["qty"].iloc[1]) == 300  # reliquat ressaisi le jour ex
    assert int(od["filled"].iloc[0]) == 200 and int(od["filled"].iloc[1]) == 300
    assert res.fill_rate == pytest.approx(1.0)
    ev = res.events
    assert ev["event"].tolist() == ["annulation_ressaisie_jour_ex"] and ev["date"].tolist() == [dates[3]]
    # dividende reconnu sur les 200 titres détenus à l'ouverture du jour ex
    assert float(res.dividends.iloc[3]) == pytest.approx(200 * 10.0)
    # sans la règle : aucune annulation, mêmes exécutions
    res2 = Backtester(panels, ZERO, capital=1e6, cancel_on_corporate_events=False).run(strat, rebalance=[dates[0]])
    assert res2.orders["status"].tolist() == ["filled"] and res2.events.empty


def test_order_entered_on_ex_date_is_not_cancelled() -> None:
    dates = _dates(5)
    close = pd.DataFrame({"SNTS": [1000.0, 990.0, 990.0, 990.0, 990.0]}, index=dates)
    div = pd.DataFrame({"SNTS": [0.0, 10.0, 0.0, 0.0, 0.0]}, index=dates)
    panels = mk(close, dividend=div)
    res = Backtester(panels, ZERO, capital=1e6).run(hold_then({dates[0]: {"SNTS": 0.5}}), rebalance=[dates[0]])
    assert res.orders["status"].tolist() == ["filled"] and res.events.empty
    assert res.trades["date"].tolist() == [dates[1]]


def test_pending_orders_cancelled_and_reentered_on_split_day() -> None:
    dates = _dates(8)
    raw = np.array([2000.0] * 3 + [1000.0] * 5)  # division 2:1 à la ligne 3
    af = np.array([0.5] * 3 + [1.0] * 5)
    vol_raw = np.array([500.0] * 3 + [1000.0] * 5)  # 1 000 titres ajustés par séance
    panels = {
        "close": pd.DataFrame({"SLBC": raw * af}, index=dates),
        "adj_factor": pd.DataFrame({"SLBC": af}, index=dates),
        "volume": pd.DataFrame({"SLBC": vol_raw}, index=dates),
        "value": pd.DataFrame({"SLBC": vol_raw * raw}, index=dates),
        "status": pd.DataFrame({"SLBC": ["traded"] * 8}, index=dates),
    }
    res = Backtester(panels, ZERO, capital=1e6).run(hold_then({dates[0]: {"SLBC": 0.5}}), rebalance=[dates[0]])
    assert res.trades["qty"].tolist() == [100] * 5  # titres ajustés
    assert res.orders["status"].tolist() == ["cancelled_split", "filled"]
    assert res.events["event"].tolist() == ["annulation_ressaisie_division"]
    assert res.events["date"].tolist() == [dates[3]]
    assert int(res.positions.iloc[-1, 0]) == 500


# ---------------------------------------------------------------------------
# Report des ordres au plus 10 séances (§7.1.1)
# ---------------------------------------------------------------------------


def _carry_market(first_trading_row: int, n: int = 16) -> dict[str, object]:
    dates = _dates(n)
    vol = np.zeros(n)
    vol[0] = 1e6
    vol[first_trading_row:] = 1e6
    close = pd.DataFrame({"ORAC": 1000.0}, index=dates)
    return mk(close, volume=pd.DataFrame({"ORAC": vol}, index=dates))


def test_order_carried_ten_sessions_then_cancelled() -> None:
    assert ExecutionModel().max_carry_sessions == 10
    # titre échangé à t+11 (10ᵉ séance de report) : exécuté
    p = _carry_market(11)
    dates = p["close"].index  # type: ignore[union-attr]
    strat = hold_then({dates[0]: {"ORAC": 0.1}})
    res = Backtester(p, ZERO, capital=1e6).run(strat, rebalance=[dates[0]])
    assert res.trades["date"].tolist() == [dates[11]]
    assert res.trades["reason"].tolist() == ["carry"]
    assert res.orders["status"].tolist() == ["filled"]
    assert (res.blocked["reason"] == "not_traded").sum() == 10
    # échangé seulement à t+12 : l'ordre a été annulé après la 10ᵉ séance de report
    p2 = _carry_market(12)
    res2 = Backtester(p2, ZERO, capital=1e6).run(strat, rebalance=[dates[0]])
    assert res2.trades.empty
    assert res2.orders["status"].tolist() == ["expired"]
    assert res2.meta["max_order_age_sessions"] == 11
    # paramètre explicite : 3 reports au plus
    res3 = Backtester(p, ZERO, ExecutionModel(max_carry_sessions=3), capital=1e6).run(strat, rebalance=[dates[0]])
    assert res3.trades.empty and res3.orders["status"].tolist() == ["expired"]


def test_carry_counts_sessions_without_boc() -> None:
    p = _carry_market(5, n=8)
    dates = p["close"].index  # type: ignore[union-attr]
    strat = hold_then({dates[0]: {"ORAC": 0.1}})
    assert not Backtester(p, ZERO, capital=1e6).run(strat, rebalance=[dates[0]]).trades.empty
    # 8 séances sans BOC entre les lignes 1 et 2 : la ligne 5 est la 13ᵉ séance après la décision
    p["session_no"] = pd.Series([100, 101, 110, 111, 112, 113, 114, 115], index=dates)
    res = Backtester(p, ZERO, capital=1e6).run(strat, rebalance=[dates[0]])
    assert res.trades.empty and res.orders["status"].tolist() == ["expired"]


# ---------------------------------------------------------------------------
# Frais fixes : tenue de compte par ligne et droits de garde (§7.2)
# ---------------------------------------------------------------------------


def test_account_fee_per_line_held_prorated_by_session() -> None:
    dates = _dates(8)
    close = pd.DataFrame({"AAAC": 1000.0, "BBBS": 500.0, "CCCC": 2000.0}, index=dates)
    panels = mk(close)
    costs = CostModel(
        sgi_commission=0.0,
        brvm_fee=0.0,
        dcbr_fee=0.0,
        impact_coef=0.0,
        half_spread_mult=0.0,
        annual_custody=0.0,
        account_fee_per_line_fcfa=5040.0,  # 20 FCFA par séance (252 séances par an)
    )
    strat = hold_then({dates[0]: {"AAAC": 0.4, "BBBS": 0.4}, dates[4]: {"AAAC": 0.4}})
    res = Backtester(panels, costs, capital=1e6, settlement=0).run(strat, rebalance=[dates[0], dates[4]])
    fees = res.cost_breakdown["account_fees"]
    assert float(fees.iloc[1]) == 0.0  # positions d'ouverture vides le jour de l'achat
    for i in (2, 3, 4, 5):
        assert float(fees.iloc[i]) == pytest.approx(2 * 20.0)  # deux lignes détenues à l'ouverture
    assert float(fees.iloc[6]) == pytest.approx(20.0)  # BBBS vendue en ligne 5
    assert float(res.costs_daily.iloc[3]) == pytest.approx(40.0)
    # une séance sans BOC entre deux lignes : frais de deux séances
    panels["session_no"] = pd.Series([1, 2, 3, 5, 6, 7, 8, 9], index=dates)
    res2 = Backtester(panels, costs, capital=1e6, settlement=0).run(strat, rebalance=[dates[0], dates[4]])
    assert float(res2.cost_breakdown["account_fees"].iloc[3]) == pytest.approx(2 * 2 * 20.0)


def test_custody_fee_on_previous_close_value() -> None:
    dates = _dates(5)
    close = pd.DataFrame({"AAAC": [1000.0, 1000.0, 1100.0, 1100.0, 1100.0]}, index=dates)
    costs = CostModel(
        sgi_commission=0.0, brvm_fee=0.0, dcbr_fee=0.0, impact_coef=0.0, half_spread_mult=0.0,
        annual_custody=0.0252, account_fee_per_line_fcfa=0.0,
    )
    res = Backtester(mk(close), costs, capital=1e6).run(hold_then({dates[0]: {"AAAC": 0.5}}), rebalance=[dates[0]])
    q = int(res.positions.iloc[-1, 0])
    assert float(res.cost_breakdown["custody"].iloc[3]) == pytest.approx(0.0001 * q * 1100.0)
    assert float(res.cost_breakdown["custody"].iloc[2]) == pytest.approx(0.0001 * q * 1000.0)


# ---------------------------------------------------------------------------
# Demi-spread propre au titre (§7.2)
# ---------------------------------------------------------------------------


def test_quoted_half_spread_median_window_and_lag() -> None:
    dates = _dates(6)
    bid = pd.DataFrame({"X": [990.0, 980.0, np.nan, 995.0, 1010.0, 990.0]}, index=dates)
    ask = pd.DataFrame({"X": [1010.0, 1020.0, 1000.0, 1005.0, 1000.0, 1010.0]}, index=dates)
    hs = quoted_half_spread(bid, ask, window=3, min_obs=2, lag=1)["X"]
    s = np.array([20 / 1000, 40 / 1000, np.nan, 10 / 1000, np.nan, 20 / 1000])  # (ask−bid)/milieu ; croisé exclu
    assert math.isnan(hs.iloc[0]) and math.isnan(hs.iloc[1])  # moins de 2 observations avant t
    assert hs.iloc[2] == pytest.approx(0.5 * np.median(s[0:2]))
    assert hs.iloc[3] == pytest.approx(0.5 * np.median(s[0:2]))  # fenêtre [0, 2] : 2 observations
    assert hs.iloc[4] == pytest.approx(0.5 * np.median(s[[1, 3]]))
    assert math.isnan(hs.iloc[5])  # fenêtre [2, 4] : une seule observation valide


def test_engine_adds_title_half_spread_with_tick_floor_and_default() -> None:
    dates = _dates(4)
    close = pd.DataFrame({"AAAC": 1000.0, "BBBS": 150.0, "CCCC": 1000.0}, index=dates)
    panels = mk(close)
    panels["bid"] = pd.DataFrame({"AAAC": 990.0, "BBBS": 149.0, "CCCC": np.nan}, index=dates)
    panels["ask"] = pd.DataFrame({"AAAC": 1010.0, "BBBS": 151.0, "CCCC": np.nan}, index=dates)
    costs = CostModel(impact_coef=0.0, annual_custody=0.0, account_fee_per_line_fcfa=0.0)
    strat = hold_then({dates[0]: {"AAAC": 0.3, "BBBS": 0.3, "CCCC": 0.3}})
    res = Backtester(panels, costs, capital=1e6, spread_min_obs=1).run(strat, rebalance=[dates[0]])
    tr = res.trades.set_index("symbol")
    # AAAC : ½ × 2 % = 1 % ; BBBS : mesure 0,67 % < plancher 5/(2×150) = 1,67 % ; CCCC : défaut 0,35 %
    assert tr.loc["AAAC", "half_spread"] == pytest.approx(0.01)
    assert tr.loc["BBBS", "half_spread"] == pytest.approx(5.0 / 300.0)
    assert tr.loc["CCCC", "half_spread"] == pytest.approx(0.0035)
    for sym in ("AAAC", "BBBS", "CCCC"):
        a = float(tr.loc[sym, "value"])
        assert float(tr.loc[sym, "cost"]) == pytest.approx(costs.rate() * a + float(tr.loc[sym, "half_spread"]) * a)
        assert float(tr.loc[sym, "spread_cost"]) == pytest.approx(float(tr.loc[sym, "half_spread"]) * a)
    # scénario de stress : demi-spread × 1,5
    stress = CostModel(impact_coef=0.0, annual_custody=0.0, account_fee_per_line_fcfa=0.0, half_spread_mult=1.5)
    res2 = Backtester(panels, stress, capital=1e6, spread_min_obs=1).run(strat, rebalance=[dates[0]])
    assert res2.trades.set_index("symbol").loc["AAAC", "half_spread"] == pytest.approx(0.015)
    assert res.cost_breakdown["spread"].sum() == pytest.approx(float(tr["spread_cost"].sum()))


def test_trade_cost_with_half_spread_matches_spec_formula() -> None:
    c = CostModel()  # central : 0,8 % × 1,18 + 0,2 % + 0,1 % = 1,244 %
    assert c.rate() == pytest.approx(0.01244)
    got = float(trade_cost(1e6, 0.01, c, half_spread=0.0035))
    assert got == pytest.approx(1e6 * (0.01244 + 0.0035 + 0.016 * 0.1))  # ≈ 1,75 % (§7.2)
    assert float(trade_cost(1e6, 0.01, c)) == pytest.approx(1e6 * (0.01244 + 0.0016))


# ---------------------------------------------------------------------------
# Dividendes à la date de paiement, laissés en cash (§7.1.6)
# ---------------------------------------------------------------------------


def test_dividend_credited_on_payment_date_and_kept_in_cash() -> None:
    dates = _dates(10)
    close = pd.DataFrame({"SNTS": [1000.0] * 5 + [950.0] * 5}, index=dates)
    div = pd.DataFrame({"SNTS": [0.0] * 5 + [50.0] + [0.0] * 4}, index=dates)
    panels = mk(close, dividend=div)
    res = Backtester(panels, ZERO, capital=1e6).run(hold_then({dates[0]: {"SNTS": 0.5}}), rebalance=[dates[0]])
    q = 500
    assert float(res.dividends.iloc[5]) == pytest.approx(q * 50.0)  # reconnu le jour ex
    assert float(res.dividends_paid.iloc[5]) == 0.0
    assert float(res.receivables.iloc[5]) == pytest.approx(q * 50.0)
    assert float(res.equity.iloc[5]) == pytest.approx(float(res.equity.iloc[4]))  # pas de faux creux
    assert float(res.dividends_paid.iloc[7]) == pytest.approx(q * 50.0)  # date ex + 2 séances
    assert float(res.cash.iloc[7] - res.cash.iloc[6]) == pytest.approx(q * 50.0)
    assert float(res.receivables.iloc[7]) == 0.0
    assert (res.positions["SNTS"].iloc[2:] == q).all()  # aucun réinvestissement automatique
    # date de paiement publiée : versement ce jour-là
    panels["dividend_payment_date"] = pd.DataFrame({"SNTS": pd.NaT}, index=dates, dtype="datetime64[ns]")
    panels["dividend_payment_date"].iloc[5, 0] = dates[8]  # type: ignore[union-attr]
    res2 = Backtester(panels, ZERO, capital=1e6).run(hold_then({dates[0]: {"SNTS": 0.5}}), rebalance=[dates[0]])
    assert res2.dividends_paid.iloc[8] == pytest.approx(q * 50.0) and float(res2.dividends_paid.sum()) == q * 50.0


# ---------------------------------------------------------------------------
# Suspension et choc pays sévère (§7.1.7, §7.1.8)
# ---------------------------------------------------------------------------


def test_suspended_position_is_blocked_and_tracked() -> None:
    dates = _dates(8)
    close = pd.DataFrame({"SIVC": 500.0}, index=dates)
    status = pd.DataFrame({"SIVC": ["traded"] * 3 + ["suspended"] * 3 + ["traded"] * 2}, index=dates)
    vol = pd.DataFrame({"SIVC": [1e5] * 3 + [0.0] * 3 + [1e5] * 2}, index=dates)
    panels = mk(close, volume=vol, status=status)
    strat = hold_then({dates[0]: {"SIVC": 0.5}, dates[2]: {"SIVC": 0.0}})
    res = Backtester(panels, ZERO, capital=1e6).run(strat, rebalance=[dates[0], dates[2]])
    assert res.blocked.loc[res.blocked["reason"] == "suspended", "date"].tolist() == list(dates[3:6])
    assert res.trades.loc[res.trades["qty"] < 0, "date"].tolist() == [dates[6]]
    assert float(res.suspended_value.iloc[4]) == pytest.approx(1000 * 500.0)
    assert float(res.suspended_value.iloc[6]) == 0.0
    assert res.meta["suspended_risk_haircut"] == pytest.approx(0.10)


def test_severe_country_shock_first_session_at_floor_without_sellers() -> None:
    dates = _dates(6)
    close = pd.DataFrame({"SNTS": 1000.0, "BOAC": 1000.0}, index=dates)
    panels = mk(close)
    strat = hold_then({dates[0]: {"SNTS": 0.4, "BOAC": 0.4}, dates[2]: {"SNTS": 0.0, "BOAC": 0.0}})
    res = Backtester(panels, ZERO, capital=1e6, country_shocks=[("SN", dates[2])]).run(
        strat, rebalance=[dates[0], dates[2]]
    )
    # séance qui suit l'annonce : SNTS (Sénégal) au plancher 925, aucun vendeur servi
    assert res.blocked.loc[res.blocked["date"] == dates[3], ["symbol", "reason"]].values.tolist() == [
        ["SNTS", "country_shock"]
    ]
    sells = res.trades[res.trades["qty"] < 0].set_index("symbol")["date"]
    assert sells["BOAC"] == dates[3] and sells["SNTS"] == dates[4]
    assert float(res.weights["SNTS"].iloc[3] * res.equity.iloc[3]) == pytest.approx(400 * 925.0)
    assert res.events["event"].tolist() == ["choc_pays_plancher"]
    # avec un DataFrame et deux séances de choc
    shocks = pd.DataFrame({"country": ["SN"], "date": [dates[2]], "sessions": [2]})
    res2 = Backtester(panels, ZERO, capital=1e6, country_shocks=shocks).run(strat, rebalance=[dates[0], dates[2]])
    assert res2.trades[(res2.trades["qty"] < 0) & (res2.trades["symbol"] == "SNTS")]["date"].tolist() == [dates[5]]


# ---------------------------------------------------------------------------
# Paramètres et comptabilité
# ---------------------------------------------------------------------------


def test_params_dict_and_strategy_config() -> None:
    dates = _dates(6)
    panels = mk(pd.DataFrame({"AAAC": 1000.0}, index=dates))
    assert ENGINE_DEFAULTS["settlement"] == "brvm" and ENGINE_DEFAULTS["dividend_payment_lag"] == 2
    bt = Backtester(panels, ZERO, capital=1e6, params={"settlement": 0, "dividend_payment_lag": 0})
    assert bt.settlement == 0 and bt.dividend_payment_lag == 0
    # le mot-clé explicite l'emporte sur le dictionnaire
    bt = Backtester(panels, ZERO, capital=1e6, params={"settlement": 0}, settlement=2)
    assert bt.settlement == 2
    with pytest.raises(KeyError):
        Backtester(panels, ZERO, capital=1e6, params={"inconnu": 1})
    try:
        from brvm_alpha import settings

        cfg = settings.load_strategy_config()
    except Exception:  # pragma: no cover - fichier de paramètres d'un autre agent
        return
    bt = Backtester(panels, ZERO, capital=1e6, params=cfg)
    assert bt.settlement == "brvm" and bt.max_order_age == 11 and bt.cancel_on_corporate_events


@pytest.mark.parametrize("seed", [0, 1])
def test_accounting_identity_with_settlement_and_fees(seed: int) -> None:
    rng = np.random.default_rng(seed)
    n, syms = 120, ["S0C", "S1C", "S2C", "S3C"]
    dates = _dates(n, "2025-09-01")  # traverse le passage J+3 → J+2
    r = np.clip(rng.normal(0.0, 0.02, size=(n, len(syms))), -0.07, 0.07)
    close = pd.DataFrame(1000.0 * np.cumprod(1.0 + r, axis=0), index=dates, columns=syms).round()
    vol = pd.DataFrame(rng.integers(0, 3000, size=(n, len(syms))).astype(float), index=dates, columns=syms)
    panels = mk(close, volume=vol)

    def chaos(asof: pd.Timestamp, view: object) -> pd.Series:
        w = rng.random(len(syms))
        return pd.Series(0.95 * w / w.sum(), index=syms)

    res = Backtester(panels, CostModel(), capital=5e6).run(chaos, rebalance=7)
    assert (res.cash >= -1e-6).all() and (res.receivables >= 0).all()
    stock = (res.positions * close.ffill()).sum(axis=1)
    assert np.allclose(res.equity, res.cash - res.payables + res.receivables + stock, rtol=1e-9, atol=1e-3)
    assert res.costs.iloc[-1] == pytest.approx(float(res.cost_breakdown.to_numpy().sum()))
    assert float(res.cost_breakdown["account_fees"].sum()) > 0 and float(res.cost_breakdown["spread"].sum()) > 0


# ---------------------------------------------------------------------------
# §12.3 n° 7 : rejeu réel de BOAN du 03 au 08/08/2023 (échantillon S0)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not (PANEL_DIR / "equities.parquet").exists(), reason="panel réel absent")
def test_boan_replay_august_2023_sells_not_served_at_floor() -> None:
    start, end = pd.Timestamp("2023-06-01"), pd.Timestamp("2023-08-31")
    assert not overlaps_s1(start, end)  # S0 uniquement : l'échantillon vierge n'est pas touché
    eq = pd.read_parquet(PANEL_DIR / "equities.parquet")
    eq = eq[(eq["symbol"] == "BOAN") & (eq["date"] >= start) & (eq["date"] <= end)]
    book = None
    if (PANEL_DIR / "order_book.parquet").exists():
        ob = pd.read_parquet(PANEL_DIR / "order_book.parquet")
        book = ob[(ob["symbol"] == "BOAN") & (ob["date"] >= start) & (ob["date"] <= end)]
    raw_close = eq.pivot(index="date", columns="symbol", values="close")  # aucune division sur la fenêtre
    panels = panels_from_equities(eq, close=raw_close, infer_dividends=False, order_book=book)
    d = pd.Timestamp
    floor_days = [d("2023-08-03"), d("2023-08-04"), d("2023-08-08")]
    strat = hold_then({d("2023-07-31"): {"BOAN": 0.2}, d("2023-08-02"): {"BOAN": 0.0}})
    bt = Backtester(panels, capital=1e6)
    res = bt.run(strat, rebalance=[d("2023-07-31"), d("2023-08-02")], start="2023-07-03")
    j = list(bt.symbols).index("BOAN")
    for day in floor_days:
        t = bt.dates.get_loc(day)
        low = price_band_limits(bt._ref_raw[t, j])[0]
        close_t = float(eq.loc[eq["date"] == day, "close"].iloc[0])
        assert close_t == low  # clôture exactement au plancher (5 085, 4 705, 4 355)
        assert float(eq.loc[eq["date"] == day, "volume"].iloc[0]) > 0  # des titres ont été échangés…
    blk = res.blocked[(res.blocked["side"] == "sell")]
    assert blk["date"].tolist() == floor_days  # … mais nos ventes n'ont pas été servies
    assert set(blk["reason"]) == {"limit_down"}
    sells = res.trades[res.trades["qty"] < 0]
    assert sells["date"].tolist() == [d("2023-08-09")]  # première séance hors plancher
    assert int(res.positions["BOAN"].iloc[-1]) == 0

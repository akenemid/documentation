"""Backtest réaliste (moteur quotidien) et validation walk-forward / grilles."""

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
    WalkForwardFold,
    WalkForwardResult,
    WalkForwardWindow,
    param_grid,
    run_param_grid,
    walk_forward,
    walk_forward_windows,
)

__all__ = [
    "BacktestResult",
    "Backtester",
    "PanelView",
    "WalkForwardFold",
    "WalkForwardResult",
    "WalkForwardWindow",
    "limit_flags",
    "panels_from_equities",
    "param_grid",
    "rebalance_dates",
    "run_param_grid",
    "trade_cost",
    "truncate_asof",
    "walk_forward",
    "walk_forward_windows",
]

"""Backtest performance metrics."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List


@dataclass
class BacktestMetrics:
    total_return_pct: float
    cagr_pct: float
    sharpe: float
    sortino: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    num_trades: int
    avg_hold_minutes: float

    def as_dict(self) -> dict:
        return self.__dict__


def compute_metrics(
    equity_curve: List[float],
    trade_pnls: List[float],
    hold_minutes: List[float],
    bars_per_year: int = 365 * 24 * 60,
    bar_minutes: int = 1,
) -> BacktestMetrics:
    n_trades = len(trade_pnls)
    if not equity_curve or equity_curve[0] <= 0:
        return BacktestMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0)
    total_ret = (equity_curve[-1] - equity_curve[0]) / equity_curve[0]
    n_bars = max(1, len(equity_curve) - 1)
    years = (n_bars * bar_minutes) / (60 * 24 * 365)
    cagr = ((equity_curve[-1] / equity_curve[0]) ** (1 / years) - 1) if years > 0 else 0.0

    # Bar returns
    returns = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]
        if prev > 0:
            returns.append((equity_curve[i] - prev) / prev)
    if returns:
        mean = sum(returns) / len(returns)
        var = sum((r - mean) ** 2 for r in returns) / len(returns)
        std = math.sqrt(var)
        sharpe = (mean / std * math.sqrt(bars_per_year / bar_minutes)) if std > 0 else 0.0
        downside = [r for r in returns if r < 0]
        if downside:
            dmean = sum(downside) / len(downside)
            dstd = math.sqrt(sum((r - dmean) ** 2 for r in downside) / len(downside))
            sortino = (mean / dstd * math.sqrt(bars_per_year / bar_minutes)) if dstd > 0 else 0.0
        else:
            sortino = 0.0
    else:
        sharpe = 0.0
        sortino = 0.0

    # Drawdown
    peak = equity_curve[0]
    max_dd = 0.0
    for v in equity_curve:
        peak = max(peak, v)
        if peak > 0:
            dd = (v - peak) / peak
            if dd < max_dd:
                max_dd = dd

    wins = [p for p in trade_pnls if p > 0]
    losses = [p for p in trade_pnls if p <= 0]
    win_rate = len(wins) / n_trades if n_trades else 0.0
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    profit_factor = gross_win / gross_loss if gross_loss > 0 else float("inf") if gross_win > 0 else 0.0
    avg_hold = sum(hold_minutes) / len(hold_minutes) if hold_minutes else 0.0

    return BacktestMetrics(
        total_return_pct=total_ret * 100,
        cagr_pct=cagr * 100,
        sharpe=sharpe,
        sortino=sortino,
        max_drawdown_pct=max_dd * 100,
        win_rate=win_rate,
        profit_factor=profit_factor,
        num_trades=n_trades,
        avg_hold_minutes=avg_hold,
    )

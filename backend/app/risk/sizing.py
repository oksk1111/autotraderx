"""ATR-based position sizing: risk = equity * risk_per_trade.

  qty       = risk_per_trade_krw / stop_distance
  notional  = qty * price
  capped by max_position_ratio * equity.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings


@dataclass
class SizingResult:
    notional_krw: float
    qty: float
    risk_krw: float
    capped: bool
    reason: str = ""


MIN_UPBIT_ORDER_KRW = 6000.0  # Upbit min order ≈ 5,000; pad to 6,000


def compute_position_size(
    equity_krw: float,
    price: float,
    stop_price: float,
    risk_per_trade: float | None = None,
    max_position_ratio: float | None = None,
) -> SizingResult:
    s = get_settings()
    rpt = risk_per_trade if risk_per_trade is not None else s.risk_per_trade
    mpr = max_position_ratio if max_position_ratio is not None else s.max_position_ratio

    if equity_krw <= 0 or price <= 0:
        return SizingResult(0.0, 0.0, 0.0, capped=True, reason="non-positive equity/price")
    if stop_price <= 0 or stop_price >= price:
        return SizingResult(0.0, 0.0, 0.0, capped=True, reason="invalid stop_price")

    risk_krw = equity_krw * rpt
    stop_dist = price - stop_price
    qty = risk_krw / stop_dist
    notional = qty * price
    cap = equity_krw * mpr
    capped = False
    reason = ""
    if notional > cap:
        notional = cap
        qty = notional / price
        capped = True
        reason = f"capped to max_position_ratio={mpr:.0%}"
    if notional < MIN_UPBIT_ORDER_KRW:
        return SizingResult(0.0, 0.0, risk_krw, capped=True,
                            reason=f"notional {notional:.0f} < min {MIN_UPBIT_ORDER_KRW:.0f}")
    return SizingResult(notional, qty, risk_krw, capped=capped, reason=reason)

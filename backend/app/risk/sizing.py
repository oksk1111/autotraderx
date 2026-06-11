"""Position sizing optimized for small accounts.

v8.1 Changes:
- For small accounts (< 100K KRW): use minimum order amount
- For larger accounts: use risk-based sizing
- Always respect max_position_ratio cap
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
SMALL_ACCOUNT_THRESHOLD = 100_000.0  # Below this, use min-order sizing


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

    cap = equity_krw * mpr
    capped = False
    reason = ""
    
    # Small account mode: use minimum viable order
    if equity_krw < SMALL_ACCOUNT_THRESHOLD:
        # Use minimum order amount or 30% of equity (whichever is larger but capped)
        notional = max(MIN_UPBIT_ORDER_KRW, equity_krw * 0.3)
        if notional > cap:
            notional = cap
            capped = True
            reason = f"small account: capped to {mpr:.0%}"
        if notional < MIN_UPBIT_ORDER_KRW:
            return SizingResult(0.0, 0.0, 0.0, capped=True,
                                reason=f"equity too low: cap {cap:.0f} < min {MIN_UPBIT_ORDER_KRW:.0f}")
        qty = notional / price
        risk_krw = notional * 0.02  # Estimated 2% risk for small accounts
        return SizingResult(notional, qty, risk_krw, capped=capped, 
                            reason=reason or "small account mode")
    
    # Normal risk-based sizing for larger accounts
    risk_krw = equity_krw * rpt
    stop_dist = price - stop_price
    qty = risk_krw / stop_dist
    notional = qty * price
    
    if notional > cap:
        notional = cap
        qty = notional / price
        capped = True
        reason = f"capped to max_position_ratio={mpr:.0%}"
    if notional < MIN_UPBIT_ORDER_KRW:
        # Fallback: use minimum order for borderline cases
        notional = MIN_UPBIT_ORDER_KRW
        qty = notional / price
        reason = "using min order amount"
    return SizingResult(notional, qty, risk_krw, capped=capped, reason=reason)

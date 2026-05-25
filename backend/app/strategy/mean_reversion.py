"""Mean-Reversion strategy: oversold RSI + BB lower violation in a ranging regime."""
from __future__ import annotations

import math
from typing import List

from . import indicators as ind
from .base import Signal


class MeanReversionStrategy:
    name = "mean_reversion"

    def __init__(
        self,
        rsi_period: int = 14,
        rsi_oversold: float = 30.0,
        bb_period: int = 20,
        bb_mult: float = 2.0,
        stop_atr_mult: float = 1.5,
    ):
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.bb_period = bb_period
        self.bb_mult = bb_mult
        self.stop_atr_mult = stop_atr_mult

    def evaluate(self, market: str, candles_1m: List, candles_5m: List, candles_15m: List) -> Signal:
        candles = candles_5m if len(candles_5m) >= 60 else candles_1m
        if len(candles) < 60:
            return Signal(market=market, action="HOLD", price=0.0, strategy=self.name,
                          rationale="insufficient bars")
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        last_close = closes[-1]

        rsi_v = ind.rsi(closes, self.rsi_period)
        lower, mid, upper = ind.bollinger(closes, self.bb_period, self.bb_mult)
        atr_v = ind.atr(highs, lows, closes, 14)

        metrics = {
            "rsi": round(rsi_v, 2) if not math.isnan(rsi_v) else None,
            "bb_lower": round(lower, 2) if not math.isnan(lower) else None,
            "bb_mid": round(mid, 2) if not math.isnan(mid) else None,
            "atr": round(atr_v, 2) if not math.isnan(atr_v) else None,
        }
        if any(math.isnan(x) for x in (rsi_v, lower, mid, atr_v)):
            return Signal(market=market, action="HOLD", price=last_close, strategy=self.name,
                          rationale="indicator NaN", metrics=metrics)

        oversold = rsi_v < self.rsi_oversold
        below_bb = last_close < lower

        if oversold and below_bb and atr_v > 0:
            stop = last_close - atr_v * self.stop_atr_mult
            target = mid  # reversion to mean
            return Signal(
                market=market, action="BUY", price=last_close, atr=atr_v,
                stop_price=stop, target_price=target, strategy=self.name,
                rationale=f"rsi={rsi_v:.1f}<{self.rsi_oversold} close<bb_lower",
                confidence=0.6, metrics=metrics,
            )

        return Signal(market=market, action="HOLD", price=last_close, atr=atr_v,
                      strategy=self.name, metrics=metrics,
                      rationale=f"rsi={rsi_v:.1f} below_bb={below_bb}")

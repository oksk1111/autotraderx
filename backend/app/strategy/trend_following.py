"""Trend-Following strategy: Donchian breakout + EMA filter, ATR stops."""
from __future__ import annotations

import math
from typing import List

from . import indicators as ind
from .base import Signal


class TrendFollowingStrategy:
    name = "trend_following"

    def __init__(
        self,
        donchian_period: int = 20,
        ema_fast: int = 20,
        ema_slow: int = 60,
        volume_mult: float = 1.3,
        stop_atr_mult: float = 2.0,
        target_atr_mult: float = 4.0,
    ):
        self.donchian_period = donchian_period
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.volume_mult = volume_mult
        self.stop_atr_mult = stop_atr_mult
        self.target_atr_mult = target_atr_mult

    def evaluate(self, market: str, candles_1m: List, candles_5m: List, candles_15m: List) -> Signal:
        # Use 5m candles for trend signal (1m too noisy, 15m too slow)
        candles = candles_5m if len(candles_5m) >= self.ema_slow + 5 else candles_1m
        if len(candles) < self.ema_slow + 5:
            return Signal(market=market, action="HOLD", price=0.0, strategy=self.name,
                          rationale="insufficient bars")

        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]
        last_close = closes[-1]

        donchian_top = ind.donchian_high(highs[:-1], self.donchian_period)  # exclude current bar
        ema_f = ind.ema(closes, self.ema_fast)
        ema_s = ind.ema(closes, self.ema_slow)
        vol_ema = ind.ema(volumes, 20)
        atr_v = ind.atr(highs, lows, closes, 14)

        metrics = {
            "donchian_top": round(donchian_top, 2) if not math.isnan(donchian_top) else None,
            "ema_fast": round(ema_f, 2) if not math.isnan(ema_f) else None,
            "ema_slow": round(ema_s, 2) if not math.isnan(ema_s) else None,
            "atr": round(atr_v, 2) if not math.isnan(atr_v) else None,
            "last_volume": round(volumes[-1], 4),
            "vol_ema": round(vol_ema, 4) if not math.isnan(vol_ema) else None,
        }

        if any(math.isnan(x) for x in (donchian_top, ema_f, ema_s, vol_ema, atr_v)):
            return Signal(market=market, action="HOLD", price=last_close, strategy=self.name,
                          rationale="indicator NaN", metrics=metrics)

        breakout = last_close > donchian_top
        trend_up = ema_f > ema_s
        volume_ok = volumes[-1] > vol_ema * self.volume_mult

        if breakout and trend_up and volume_ok and atr_v > 0:
            stop = last_close - atr_v * self.stop_atr_mult
            target = last_close + atr_v * self.target_atr_mult
            return Signal(
                market=market, action="BUY", price=last_close, atr=atr_v,
                stop_price=stop, target_price=target, strategy=self.name,
                rationale=f"breakout>{donchian_top:.2f} ema_f>ema_s vol×{volumes[-1]/vol_ema:.2f}",
                confidence=0.65, metrics=metrics,
            )

        return Signal(market=market, action="HOLD", price=last_close, atr=atr_v,
                      strategy=self.name, metrics=metrics,
                      rationale=f"breakout={breakout} trend_up={trend_up} vol_ok={volume_ok}")

"""Regime classifier — TREND / RANGE / CHAOS / NEUTRAL.

Decision rule (priority):
  1) ATR% > 1.5% OR |vol_z| > 3            → CHAOS
  2) ADX(14) >= 25                          → TREND
  3) ADX(14) < 18 AND BB width compressed   → RANGE
  4) otherwise                              → NEUTRAL
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import List

from . import indicators as ind


class Regime(str, Enum):
    TREND = "TREND"
    RANGE = "RANGE"
    CHAOS = "CHAOS"
    NEUTRAL = "NEUTRAL"


@dataclass
class RegimeReading:
    regime: Regime
    adx: float
    atr_pct: float
    bb_width: float
    vol_z: float
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "regime": self.regime.value,
            "adx": round(self.adx, 2) if not math.isnan(self.adx) else None,
            "atr_pct": round(self.atr_pct, 4) if not math.isnan(self.atr_pct) else None,
            "bb_width": round(self.bb_width, 4) if not math.isnan(self.bb_width) else None,
            "vol_z": round(self.vol_z, 2) if not math.isnan(self.vol_z) else None,
            "note": self.note,
        }


class RegimeClassifier:
    def __init__(
        self,
        adx_trend_threshold: float = 25.0,
        adx_range_threshold: float = 18.0,
        atr_chaos_threshold: float = 0.015,
        vol_z_chaos_threshold: float = 3.0,
    ):
        self.adx_trend = adx_trend_threshold
        self.adx_range = adx_range_threshold
        self.atr_chaos = atr_chaos_threshold
        self.vol_z_chaos = vol_z_chaos_threshold

    def classify(self, candles_1m: List) -> RegimeReading:
        if len(candles_1m) < 60:
            return RegimeReading(Regime.NEUTRAL, float("nan"), float("nan"), float("nan"), float("nan"),
                                 note="insufficient bars")
        highs = [c.high for c in candles_1m]
        lows = [c.low for c in candles_1m]
        closes = [c.close for c in candles_1m]
        volumes = [c.volume for c in candles_1m]

        adx_v = ind.adx(highs, lows, closes, period=14)
        atr_v = ind.atr(highs, lows, closes, period=14)
        price = closes[-1]
        atr_pct = (atr_v / price) if price > 0 and not math.isnan(atr_v) else float("nan")
        lo, mid, up = ind.bollinger(closes, period=20, mult=2.0)
        bb_width = ((up - lo) / mid) if (mid and not math.isnan(mid) and mid > 0) else float("nan")
        vol_z = ind.volume_zscore(volumes, period=60)

        # 1) Chaos
        if (not math.isnan(atr_pct) and atr_pct > self.atr_chaos) or \
           (not math.isnan(vol_z) and abs(vol_z) > self.vol_z_chaos):
            return RegimeReading(Regime.CHAOS, adx_v, atr_pct, bb_width, vol_z,
                                 note=f"atr%={atr_pct:.3%} vol_z={vol_z:.2f}")
        # 2) Trend
        if not math.isnan(adx_v) and adx_v >= self.adx_trend:
            return RegimeReading(Regime.TREND, adx_v, atr_pct, bb_width, vol_z,
                                 note=f"adx={adx_v:.1f}")
        # 3) Range — ADX low AND BB compressed
        if not math.isnan(adx_v) and adx_v < self.adx_range:
            if not math.isnan(bb_width) and bb_width < 0.02:  # <2% bandwidth
                return RegimeReading(Regime.RANGE, adx_v, atr_pct, bb_width, vol_z,
                                     note=f"adx={adx_v:.1f} bb={bb_width:.3f}")
        return RegimeReading(Regime.NEUTRAL, adx_v, atr_pct, bb_width, vol_z, note="no regime match")

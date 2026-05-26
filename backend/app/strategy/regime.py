"""Regime classifier — TREND / RANGE / CHAOS / NEUTRAL.

Decision rule (priority):
  1) ATR% > 1.5% OR |vol_z| > 3            → CHAOS (거래 정지)
  2) ADX(14) >= 25                          → TREND  (Trend-Following)
  3) ADX(14) < 25                           → RANGE  (Mean-Reversion)
  4) indicator NaN / insufficient bars     → NEUTRAL

주의: v5.0 초기 버전은 "ADX < 18 AND BB compressed" 만 RANGE 로 두고
ADX 18~25 구간을 NEUTRAL 사각지대로 만들어, 대부분의 시간 어느 전략도
선택되지 않는 "거래 0건" 버그가 있었다. 횡보 강도(BB width) 는 진입 시
Mean-Reversion 전략 내부의 RSI/BB 조건이 다시 검증하므로, 분류기 단계
에서 이중으로 좁힐 필요가 없다.
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
        atr_chaos_threshold: float = 0.015,
        vol_z_chaos_threshold: float = 3.0,
    ):
        self.adx_trend = adx_trend_threshold
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
        # 3) Range — ADX 가 추세 임계 미만이면 무조건 RANGE.
        #    (Mean-Reversion 전략은 RSI<30 AND price<BB_lower 를 다시 요구하므로
        #     실제 진입 빈도는 안전하게 제한된다.)
        if not math.isnan(adx_v):
            return RegimeReading(Regime.RANGE, adx_v, atr_pct, bb_width, vol_z,
                                 note=f"adx={adx_v:.1f} bb={bb_width:.3f}")
        # 4) NEUTRAL — 지표 계산 실패 시에만
        return RegimeReading(Regime.NEUTRAL, adx_v, atr_pct, bb_width, vol_z, note="adx NaN")

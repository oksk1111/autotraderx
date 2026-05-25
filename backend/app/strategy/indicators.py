"""Pure-function technical indicators. Inputs are sequences of floats; outputs the
last computed value (or list if useful)."""
from __future__ import annotations

import math
from typing import List, Sequence, Tuple


def _nan() -> float:
    return float("nan")


def sma(values: Sequence[float], period: int) -> float:
    if len(values) < period or period <= 0:
        return _nan()
    return sum(values[-period:]) / period


def ema(values: Sequence[float], period: int) -> float:
    """Wilder/EMA over the full series (returns final EMA)."""
    if not values or period <= 0:
        return _nan()
    k = 2 / (period + 1)
    e = float(values[0])
    for v in values[1:]:
        e = float(v) * k + e * (1 - k)
    return e


def rsi(values: Sequence[float], period: int = 14) -> float:
    if len(values) <= period:
        return _nan()
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        d = values[i] - values[i - 1]
        if d >= 0:
            gains += d
        else:
            losses -= d
    avg_gain = gains / period
    avg_loss = losses / period
    for i in range(period + 1, len(values)):
        d = values[i] - values[i - 1]
        gain = max(d, 0.0)
        loss = -min(d, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14) -> float:
    n = len(closes)
    if n < period + 1:
        return _nan()
    trs: List[float] = []
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    # Wilder's smoothing
    atr_v = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr_v = (atr_v * (period - 1) + tr) / period
    return atr_v


def bollinger(values: Sequence[float], period: int = 20, mult: float = 2.0) -> Tuple[float, float, float]:
    """Returns (lower, middle, upper). NaNs if insufficient data."""
    if len(values) < period:
        return (_nan(), _nan(), _nan())
    window = values[-period:]
    mean = sum(window) / period
    var = sum((x - mean) ** 2 for x in window) / period
    sd = math.sqrt(var)
    return (mean - mult * sd, mean, mean + mult * sd)


def donchian_high(highs: Sequence[float], period: int = 20) -> float:
    if len(highs) < period:
        return _nan()
    return max(highs[-period:])


def donchian_low(lows: Sequence[float], period: int = 20) -> float:
    if len(lows) < period:
        return _nan()
    return min(lows[-period:])


def adx(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> float:
    """Wilder's ADX. Returns NaN if insufficient bars."""
    n = len(closes)
    if n < period * 2 + 1:
        return _nan()
    tr_list: List[float] = []
    plus_dm: List[float] = []
    minus_dm: List[float] = []
    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm.append(up_move if (up_move > down_move and up_move > 0) else 0.0)
        minus_dm.append(down_move if (down_move > up_move and down_move > 0) else 0.0)
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_list.append(tr)
    # Smoothed
    def smooth(x: List[float]) -> List[float]:
        out: List[float] = []
        s = sum(x[:period])
        out.append(s)
        for v in x[period:]:
            s = s - (s / period) + v
            out.append(s)
        return out

    tr_s = smooth(tr_list)
    plus_s = smooth(plus_dm)
    minus_s = smooth(minus_dm)
    if not tr_s:
        return _nan()
    plus_di = [100.0 * (p / t) if t > 0 else 0.0 for p, t in zip(plus_s, tr_s)]
    minus_di = [100.0 * (m / t) if t > 0 else 0.0 for m, t in zip(minus_s, tr_s)]
    dx = [
        (100.0 * abs(p - mi) / (p + mi)) if (p + mi) > 0 else 0.0
        for p, mi in zip(plus_di, minus_di)
    ]
    if len(dx) < period:
        return _nan()
    adx_v = sum(dx[:period]) / period
    for d in dx[period:]:
        adx_v = (adx_v * (period - 1) + d) / period
    return adx_v


def volume_zscore(volumes: Sequence[float], period: int = 60) -> float:
    if len(volumes) < period:
        return _nan()
    window = volumes[-period:]
    mean = sum(window) / period
    var = sum((x - mean) ** 2 for x in window) / period
    sd = math.sqrt(var) if var > 0 else 0.0
    if sd == 0:
        return 0.0
    return (volumes[-1] - mean) / sd

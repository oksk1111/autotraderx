from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import pandas as pd


@dataclass
class StrategyDecision:
    action: str
    confidence: float
    rationale: str
    stop_loss_pct: float
    take_profit_pct: float
    investment_ratio: float


class CapitalPreservationStrategy:
    """
    Capital-preservation-first strategy.

    Core ideas:
    - Do not chase vertical pumps.
    - Enter only on pullback in confirmed higher-timeframe uptrend.
    - Keep risk fixed and small.
    """

    def __init__(self) -> None:
        self.base_stop_loss_pct = 0.012
        self.base_take_profit_pct = 0.026

    def analyze(
        self,
        market: str,
        df_1h: pd.DataFrame,
        df_15m: pd.DataFrame,
        df_5m: pd.DataFrame,
        has_position: bool,
    ) -> StrategyDecision:
        if df_1h is None or df_15m is None or df_5m is None:
            return StrategyDecision("HOLD", 0.0, "missing data", 0.012, 0.026, 0.0)
        if len(df_1h) < 80 or len(df_15m) < 80 or len(df_5m) < 50:
            return StrategyDecision("HOLD", 0.0, "insufficient candles", 0.012, 0.026, 0.0)

        one_h = self._build_features(df_1h)
        m15 = self._build_features(df_15m)
        m5 = self._build_features(df_5m)

        trend_ok = self._is_uptrend(one_h, m15)
        overheat = self._is_pump_chasing(m5)

        if has_position:
            # Exit when trend degrades or intraday momentum breaks.
            if self._exit_signal(one_h, m15, m5):
                return StrategyDecision(
                    action="SELL",
                    confidence=0.82,
                    rationale=f"{market} trend/momentum breakdown",
                    stop_loss_pct=self.base_stop_loss_pct,
                    take_profit_pct=self.base_take_profit_pct,
                    investment_ratio=1.0,
                )
            return StrategyDecision("HOLD", 0.35, f"{market} keep position", 0.012, 0.026, 0.0)

        if not trend_ok:
            return StrategyDecision("HOLD", 0.25, f"{market} trend filter fail", 0.012, 0.026, 0.0)

        if overheat:
            return StrategyDecision("HOLD", 0.20, f"{market} vertical move detected", 0.012, 0.026, 0.0)

        if self._entry_signal(m15, m5):
            confidence = self._entry_confidence(m15, m5)
            return StrategyDecision(
                action="BUY",
                confidence=confidence,
                rationale=f"{market} pullback entry in uptrend",
                stop_loss_pct=self.base_stop_loss_pct,
                take_profit_pct=self.base_take_profit_pct,
                investment_ratio=self._position_size(confidence),
            )

        return StrategyDecision("HOLD", 0.30, f"{market} no clean setup", 0.012, 0.026, 0.0)

    def _build_features(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["ema20"] = out["close"].ewm(span=20, adjust=False).mean()
        out["ema50"] = out["close"].ewm(span=50, adjust=False).mean()
        out["vol_ma20"] = out["volume"].rolling(20).mean()

        delta = out["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta.where(delta < 0, 0.0))
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean().replace(0, 1e-12)
        rs = avg_gain / avg_loss
        out["rsi"] = 100 - (100 / (1 + rs))

        out["ret_3"] = out["close"].pct_change(3)
        out["ret_5"] = out["close"].pct_change(5)
        out = out.bfill().ffill()
        return out

    def _is_uptrend(self, one_h: pd.DataFrame, m15: pd.DataFrame) -> bool:
        h = one_h.iloc[-1]
        h_prev = one_h.iloc[-4]
        t = m15.iloc[-1]
        return bool(
            h["ema20"] > h["ema50"]
            and h["close"] > h["ema20"]
            and h["ema20"] > h_prev["ema20"]
            and t["ema20"] >= t["ema50"]
        )

    def _is_pump_chasing(self, m5: pd.DataFrame) -> bool:
        c = m5.iloc[-1]
        # Block fresh vertical candles and extreme RSI.
        return bool(c["ret_3"] >= 0.018 or c["ret_5"] >= 0.028 or c["rsi"] >= 74)

    def _entry_signal(self, m15: pd.DataFrame, m5: pd.DataFrame) -> bool:
        i15 = m15.iloc[-1]
        i5 = m5.iloc[-1]

        near_ema20 = abs(i5["close"] - i5["ema20"]) / max(i5["close"], 1e-12) <= 0.006
        rsi_ok = 46 <= i5["rsi"] <= 62
        vol_ok = i5["volume"] >= (i5["vol_ma20"] * 1.25)
        reclaim = i5["close"] >= i5["open"] and i15["close"] >= i15["ema20"]

        return bool(near_ema20 and rsi_ok and vol_ok and reclaim)

    def _exit_signal(self, one_h: pd.DataFrame, m15: pd.DataFrame, m5: pd.DataFrame) -> bool:
        h = one_h.iloc[-1]
        t = m15.iloc[-1]
        f = m5.iloc[-1]
        trend_break = (h["close"] < h["ema20"]) and (t["ema20"] < t["ema50"])
        momentum_break = (f["close"] < f["ema20"] and f["rsi"] < 42)
        return bool(trend_break or momentum_break)

    def _entry_confidence(self, m15: pd.DataFrame, m5: pd.DataFrame) -> float:
        i15 = m15.iloc[-1]
        i5 = m5.iloc[-1]
        conf = 0.72
        if i15["close"] > i15["ema20"] * 1.004:
            conf += 0.05
        if i5["volume"] > i5["vol_ma20"] * 1.8:
            conf += 0.05
        if 50 <= i5["rsi"] <= 58:
            conf += 0.04
        return min(conf, 0.92)

    def _position_size(self, confidence: float) -> float:
        if confidence >= 0.88:
            return 0.14
        if confidence >= 0.82:
            return 0.11
        if confidence >= 0.76:
            return 0.08
        return 0.06


_strategy: CapitalPreservationStrategy | None = None


def get_capital_preservation_strategy() -> CapitalPreservationStrategy:
    global _strategy
    if _strategy is None:
        _strategy = CapitalPreservationStrategy()
    return _strategy

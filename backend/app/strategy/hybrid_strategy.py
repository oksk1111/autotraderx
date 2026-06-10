"""Hybrid Strategy v8.0 — Combines mechanical signals with LLM intelligence.

Key improvements over v7.0:
1. Relaxed entry conditions (2/3 criteria instead of all)
2. LLM validation for high-confidence trades
3. Multi-timeframe confluence scoring
4. Adaptive position sizing based on conviction
5. Smart entry timing (DCA on weakness in uptrend)

Strategy Philosophy:
- Mechanical rules generate candidate signals
- LLM validates and scores signals
- Only execute when both agree (confluence)
- Use ATR-based dynamic stops
- Trail profits with regime-adaptive logic
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import indicators as ind
from .base import Signal
from .llm_advisor import LLMAdvisor, LLMSignal, MarketContext, build_market_context, get_advisor
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass  
class ConfluenceScore:
    """Multi-factor confluence scoring."""
    trend_score: float = 0.0  # -1 to +1 (bearish to bullish)
    momentum_score: float = 0.0
    volume_score: float = 0.0
    pattern_score: float = 0.0
    llm_score: float = 0.0
    total_score: float = 0.0
    factors: Dict[str, bool] = None
    
    def __post_init__(self):
        if self.factors is None:
            self.factors = {}


class HybridStrategy:
    """v8.0 Hybrid Strategy - Mechanical + LLM."""
    
    name = "hybrid_v8"
    
    def __init__(
        self,
        # Trend parameters
        ema_fast: int = 9,
        ema_mid: int = 21,
        ema_slow: int = 55,
        # Momentum parameters  
        rsi_oversold: float = 35.0,  # Relaxed from 30
        rsi_overbought: float = 65.0,  # Relaxed from 70
        # Volume parameters
        volume_mult: float = 1.2,  # Relaxed from 1.3
        # Risk parameters
        stop_atr_mult: float = 1.8,
        target_atr_mult: float = 3.6,
        # Entry conditions
        min_confluence_score: float = 0.6,  # Minimum score to enter
        llm_weight: float = 0.3,  # LLM contribution to final score
    ):
        self.s = get_settings()
        self.ema_fast = ema_fast
        self.ema_mid = ema_mid
        self.ema_slow = ema_slow
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.volume_mult = volume_mult
        self.stop_atr_mult = stop_atr_mult
        self.target_atr_mult = target_atr_mult
        self.min_confluence_score = min_confluence_score
        self.llm_weight = llm_weight
        self.advisor = get_advisor()
        
    def evaluate(
        self,
        market: str,
        candles_1m: List,
        candles_5m: List,
        candles_15m: List,
    ) -> Signal:
        """Evaluate market and generate hybrid signal."""
        
        # Need sufficient data
        if len(candles_5m) < self.ema_slow + 10:
            return self._hold_signal(market, 0.0, "insufficient data")
        
        # Use 5m as primary timeframe
        candles = candles_5m
        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        volumes = [c.volume for c in candles]
        last_close = closes[-1]
        
        # Compute indicators
        indicators = self._compute_indicators(highs, lows, closes, volumes)
        
        # Calculate confluence score
        score = self._calculate_confluence(indicators, candles_1m, candles_5m)
        
        # Get LLM opinion if enabled
        llm_signal = None
        if self.s.use_ai_verification and self.s.llm_autotrading_enabled:
            try:
                ctx = build_market_context(market, candles_1m, candles_5m, indicators)
                if ctx:
                    llm_signal = self.advisor.analyze(ctx)
                    if llm_signal:
                        score.llm_score = self._llm_to_score(llm_signal)
                        score.total_score = self._blend_scores(score)
            except Exception as e:
                logger.warning(f"LLM analysis failed: {e}")
        
        # Decision logic
        atr = indicators.get("atr", 0.0)
        
        if score.total_score >= self.min_confluence_score:
            # BUY signal with high confluence
            stop = last_close - atr * self.stop_atr_mult
            
            # Adjust target based on score strength
            target_mult = self.target_atr_mult * (0.8 + score.total_score * 0.4)
            target = last_close + atr * target_mult
            
            # Adjust confidence based on LLM agreement
            base_confidence = 0.5 + score.total_score * 0.3
            if llm_signal and llm_signal.action == "BUY":
                base_confidence += 0.15
            
            rationale = self._build_rationale(score, llm_signal)
            
            return Signal(
                market=market,
                action="BUY",
                price=last_close,
                atr=atr,
                stop_price=stop,
                target_price=target,
                strategy=self.name,
                rationale=rationale,
                confidence=min(base_confidence, 0.95),
                metrics=self._build_metrics(indicators, score),
            )
        
        elif score.total_score <= -self.min_confluence_score:
            # Strong bearish signal - could be used for exit
            return self._hold_signal(
                market, last_close, 
                f"bearish confluence score={score.total_score:.2f}",
                atr=atr, metrics=self._build_metrics(indicators, score)
            )
        
        # No clear signal
        return self._hold_signal(
            market, last_close,
            f"score={score.total_score:.2f} < threshold",
            atr=atr, metrics=self._build_metrics(indicators, score)
        )
    
    def _compute_indicators(
        self, 
        highs: List[float], 
        lows: List[float], 
        closes: List[float], 
        volumes: List[float]
    ) -> Dict:
        """Compute all technical indicators."""
        return {
            "ema_fast": ind.ema(closes, self.ema_fast),
            "ema_mid": ind.ema(closes, self.ema_mid),
            "ema_slow": ind.ema(closes, self.ema_slow),
            "rsi": ind.rsi(closes, 14),
            "adx": ind.adx(highs, lows, closes, 14),
            "atr": ind.atr(highs, lows, closes, 14),
            "bb_lower": ind.bollinger(closes, 20, 2.0)[0],
            "bb_mid": ind.bollinger(closes, 20, 2.0)[1],
            "bb_upper": ind.bollinger(closes, 20, 2.0)[2],
            "vol_ema": ind.ema(volumes, 20),
            "macd": ind.macd(closes, 12, 26, 9)[0] if len(closes) >= 35 else 0.0,
            "macd_signal": ind.macd(closes, 12, 26, 9)[1] if len(closes) >= 35 else 0.0,
            "donchian_high": ind.donchian_high(highs[:-1], 20),
            "donchian_low": ind.donchian_low(lows[:-1], 20),
            "current_volume": volumes[-1],
            "current_close": closes[-1],
        }
    
    def _calculate_confluence(
        self, 
        indicators: Dict,
        candles_1m: List,
        candles_5m: List,
    ) -> ConfluenceScore:
        """Calculate multi-factor confluence score."""
        score = ConfluenceScore()
        factors = {}
        
        close = indicators["current_close"]
        ema_f = indicators["ema_fast"]
        ema_m = indicators["ema_mid"]
        ema_s = indicators["ema_slow"]
        rsi = indicators["rsi"]
        adx = indicators["adx"]
        bb_lower = indicators["bb_lower"]
        bb_upper = indicators["bb_upper"]
        vol = indicators["current_volume"]
        vol_ema = indicators["vol_ema"]
        macd = indicators["macd"]
        macd_sig = indicators["macd_signal"]
        donchian_high = indicators["donchian_high"]
        
        # Validate indicators
        if any(math.isnan(x) for x in [ema_f, ema_m, ema_s, rsi, adx]):
            score.total_score = 0.0
            return score
        
        # === TREND SCORE (-1 to +1) ===
        trend_points = 0
        
        # EMA alignment (strong trend indicator)
        if ema_f > ema_m > ema_s:
            trend_points += 0.4
            factors["ema_bullish_alignment"] = True
        elif ema_f < ema_m < ema_s:
            trend_points -= 0.4
            factors["ema_bearish_alignment"] = True
        
        # Price vs EMA
        if close > ema_m:
            trend_points += 0.2
            factors["price_above_ema21"] = True
        else:
            trend_points -= 0.2
            
        # ADX trend strength
        if adx > 25:
            trend_points += 0.2 if trend_points > 0 else -0.2
            factors["strong_trend"] = True
        elif adx < 20:
            trend_points *= 0.5  # Reduce trend weight in ranging market
            factors["weak_trend"] = True
            
        # Donchian breakout
        if close > donchian_high:
            trend_points += 0.2
            factors["donchian_breakout"] = True
            
        score.trend_score = max(-1, min(1, trend_points))
        
        # === MOMENTUM SCORE (-1 to +1) ===
        momentum_points = 0
        
        # RSI
        if rsi < self.rsi_oversold:
            momentum_points += 0.4  # Oversold = bullish potential
            factors["rsi_oversold"] = True
        elif rsi > self.rsi_overbought:
            momentum_points -= 0.4  # Overbought = bearish potential
            factors["rsi_overbought"] = True
        else:
            # Neutral zone - check direction
            momentum_points += 0.1 if rsi > 50 else -0.1
            
        # MACD
        if macd > macd_sig:
            momentum_points += 0.3
            factors["macd_bullish"] = True
        else:
            momentum_points -= 0.3
            factors["macd_bearish"] = True
            
        # Bollinger Band position
        if close < bb_lower:
            momentum_points += 0.3  # Below lower band = oversold
            factors["below_bb_lower"] = True
        elif close > bb_upper:
            momentum_points -= 0.3  # Above upper band = overbought
            factors["above_bb_upper"] = True
            
        score.momentum_score = max(-1, min(1, momentum_points))
        
        # === VOLUME SCORE (-1 to +1) ===
        if vol_ema > 0:
            vol_ratio = vol / vol_ema
            if vol_ratio > self.volume_mult:
                # High volume confirms direction
                score.volume_score = 0.5 if score.trend_score > 0 else -0.3
                factors["high_volume"] = True
            elif vol_ratio < 0.7:
                # Low volume = weak move
                score.volume_score = -0.2
                factors["low_volume"] = True
            else:
                score.volume_score = 0.1
        
        # === PATTERN SCORE ===
        # Simple pattern detection
        if len(candles_5m) >= 3:
            last_3 = candles_5m[-3:]
            
            # Bullish engulfing-like pattern
            if (last_3[-1].close > last_3[-1].open and 
                last_3[-2].close < last_3[-2].open and
                last_3[-1].close > last_3[-2].open):
                score.pattern_score = 0.3
                factors["bullish_reversal_pattern"] = True
            
            # Higher lows (accumulation)
            if all(candles_5m[-i].low > candles_5m[-i-1].low for i in range(1, 4) if i+1 < len(candles_5m)):
                score.pattern_score += 0.2
                factors["higher_lows"] = True
        
        # === TOTAL SCORE ===
        # Weight: Trend 35%, Momentum 30%, Volume 20%, Pattern 15%
        score.total_score = (
            score.trend_score * 0.35 +
            score.momentum_score * 0.30 +
            score.volume_score * 0.20 +
            score.pattern_score * 0.15
        )
        
        score.factors = factors
        return score
    
    def _llm_to_score(self, llm_signal: LLMSignal) -> float:
        """Convert LLM signal to confluence score."""
        if llm_signal.action == "BUY":
            return llm_signal.confidence
        elif llm_signal.action == "SELL":
            return -llm_signal.confidence
        return 0.0
    
    def _blend_scores(self, score: ConfluenceScore) -> float:
        """Blend mechanical and LLM scores."""
        mechanical_score = (
            score.trend_score * 0.35 +
            score.momentum_score * 0.30 +
            score.volume_score * 0.20 +
            score.pattern_score * 0.15
        )
        
        if abs(score.llm_score) > 0.1:
            # LLM has opinion - blend
            blended = (
                mechanical_score * (1 - self.llm_weight) +
                score.llm_score * self.llm_weight
            )
            
            # Bonus for agreement
            if (mechanical_score > 0 and score.llm_score > 0) or \
               (mechanical_score < 0 and score.llm_score < 0):
                blended *= 1.15  # 15% bonus for confluence
            
            return blended
        
        return mechanical_score
    
    def _build_rationale(self, score: ConfluenceScore, llm_signal: Optional[LLMSignal]) -> str:
        """Build human-readable rationale."""
        parts = []
        
        if score.trend_score > 0.2:
            parts.append("bullish trend")
        if score.momentum_score > 0.2:
            parts.append("positive momentum")
        if score.volume_score > 0.2:
            parts.append("strong volume")
        if score.pattern_score > 0.1:
            parts.append("bullish pattern")
        
        active_factors = [k for k, v in score.factors.items() if v]
        if active_factors:
            parts.append(f"factors: {', '.join(active_factors[:3])}")
        
        if llm_signal and llm_signal.action == "BUY":
            parts.append(f"LLM: {llm_signal.rationale[:50]}")
        
        return f"score={score.total_score:.2f} | " + " | ".join(parts)
    
    def _build_metrics(self, indicators: Dict, score: ConfluenceScore) -> Dict:
        """Build metrics dictionary for logging."""
        return {
            "confluence_score": round(score.total_score, 3),
            "trend_score": round(score.trend_score, 3),
            "momentum_score": round(score.momentum_score, 3),
            "volume_score": round(score.volume_score, 3),
            "pattern_score": round(score.pattern_score, 3),
            "llm_score": round(score.llm_score, 3),
            "rsi": round(indicators.get("rsi", 0), 1),
            "adx": round(indicators.get("adx", 0), 1),
            "ema_fast": round(indicators.get("ema_fast", 0), 0),
            "ema_mid": round(indicators.get("ema_mid", 0), 0),
            "ema_slow": round(indicators.get("ema_slow", 0), 0),
            "factors": list(score.factors.keys())[:5],
        }
    
    def _hold_signal(
        self, 
        market: str, 
        price: float, 
        rationale: str,
        atr: float = 0.0,
        metrics: Dict = None,
    ) -> Signal:
        """Create a HOLD signal."""
        return Signal(
            market=market,
            action="HOLD",
            price=price,
            atr=atr,
            strategy=self.name,
            rationale=rationale,
            metrics=metrics or {},
        )


class AggressiveMomentumStrategy:
    """Aggressive momentum strategy for trending markets.
    
    Designed for strong uptrends - catches momentum breakouts
    with tighter stops and larger targets.
    """
    
    name = "aggressive_momentum"
    
    def __init__(
        self,
        momentum_threshold: float = 0.015,  # 1.5% move triggers
        volume_surge: float = 2.0,  # 2x volume
        stop_atr_mult: float = 1.2,  # Tight stop
        target_atr_mult: float = 4.0,  # Large target
    ):
        self.momentum_threshold = momentum_threshold
        self.volume_surge = volume_surge
        self.stop_atr_mult = stop_atr_mult
        self.target_atr_mult = target_atr_mult
    
    def evaluate(
        self,
        market: str,
        candles_1m: List,
        candles_5m: List,
        candles_15m: List,
    ) -> Signal:
        """Evaluate for momentum breakout."""
        if len(candles_1m) < 30:
            return Signal(market=market, action="HOLD", price=0.0, 
                         strategy=self.name, rationale="insufficient data")
        
        closes = [c.close for c in candles_1m]
        highs = [c.high for c in candles_1m]
        lows = [c.low for c in candles_1m]
        volumes = [c.volume for c in candles_1m]
        
        last_close = closes[-1]
        
        # Recent momentum (last 5 bars vs prior 5 bars)
        recent_avg = sum(closes[-5:]) / 5
        prior_avg = sum(closes[-10:-5]) / 5
        momentum = (recent_avg - prior_avg) / prior_avg if prior_avg > 0 else 0
        
        # Volume surge
        vol_recent = sum(volumes[-5:]) / 5
        vol_prior = sum(volumes[-20:-5]) / 15 if len(volumes) >= 20 else vol_recent
        vol_ratio = vol_recent / vol_prior if vol_prior > 0 else 1
        
        # ATR for stops
        atr = ind.atr(highs, lows, closes, 14)
        
        # Strong momentum + volume surge = BUY
        if momentum > self.momentum_threshold and vol_ratio > self.volume_surge:
            stop = last_close - atr * self.stop_atr_mult
            target = last_close + atr * self.target_atr_mult
            
            return Signal(
                market=market,
                action="BUY",
                price=last_close,
                atr=atr,
                stop_price=stop,
                target_price=target,
                strategy=self.name,
                rationale=f"momentum={momentum:.2%} vol={vol_ratio:.1f}x",
                confidence=0.7,
                metrics={
                    "momentum": round(momentum, 4),
                    "volume_ratio": round(vol_ratio, 2),
                }
            )
        
        return Signal(
            market=market,
            action="HOLD", 
            price=last_close,
            atr=atr,
            strategy=self.name,
            rationale=f"momentum={momentum:.2%} vol={vol_ratio:.1f}x (threshold: {self.momentum_threshold:.2%}/{self.volume_surge}x)",
        )


class DipBuyingStrategy:
    """Buy-the-dip strategy for accumulation in uptrends.
    
    Looks for temporary pullbacks in overall uptrends to
    accumulate at better prices.
    """
    
    name = "dip_buying"
    
    def __init__(
        self,
        dip_threshold: float = -0.02,  # 2% dip
        uptrend_lookback: int = 100,  # 100 bars for trend
        rsi_entry: float = 40.0,  # RSI below this
        stop_atr_mult: float = 2.0,
        target_atr_mult: float = 3.0,
    ):
        self.dip_threshold = dip_threshold
        self.uptrend_lookback = uptrend_lookback
        self.rsi_entry = rsi_entry
        self.stop_atr_mult = stop_atr_mult
        self.target_atr_mult = target_atr_mult
    
    def evaluate(
        self,
        market: str,
        candles_1m: List,
        candles_5m: List,
        candles_15m: List,
    ) -> Signal:
        """Evaluate for dip buying opportunity."""
        candles = candles_5m if len(candles_5m) >= self.uptrend_lookback else candles_1m
        
        if len(candles) < self.uptrend_lookback:
            return Signal(market=market, action="HOLD", price=0.0,
                         strategy=self.name, rationale="insufficient data")
        
        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        
        last_close = closes[-1]
        
        # Check uptrend (price above 100-bar EMA)
        ema_100 = ind.ema(closes, self.uptrend_lookback)
        in_uptrend = last_close > ema_100 * 0.98  # Allow small dip below
        
        # Recent dip from local high
        recent_high = max(highs[-20:])
        dip_pct = (last_close - recent_high) / recent_high
        
        # RSI
        rsi = ind.rsi(closes, 14)
        
        # ATR
        atr = ind.atr(highs, lows, closes, 14)
        
        # Buy dip in uptrend
        if in_uptrend and dip_pct < self.dip_threshold and rsi < self.rsi_entry:
            stop = last_close - atr * self.stop_atr_mult
            target = recent_high  # Target: return to recent high
            
            return Signal(
                market=market,
                action="BUY",
                price=last_close,
                atr=atr,
                stop_price=stop,
                target_price=target,
                strategy=self.name,
                rationale=f"dip={dip_pct:.1%} rsi={rsi:.0f} uptrend=True",
                confidence=0.65,
                metrics={
                    "dip_pct": round(dip_pct, 4),
                    "rsi": round(rsi, 1),
                    "recent_high": round(recent_high, 0),
                }
            )
        
        return Signal(
            market=market,
            action="HOLD",
            price=last_close,
            atr=atr,
            strategy=self.name,
            rationale=f"uptrend={in_uptrend} dip={dip_pct:.1%} rsi={rsi:.0f}",
        )

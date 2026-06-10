"""LLM-based Market Advisor — AI-powered trading signal generation.

Uses Groq (Llama 3.3 70B) for intelligent market analysis:
1. Technical indicator interpretation
2. Market sentiment analysis  
3. Entry/exit timing optimization
4. Risk-adjusted position sizing recommendations

This module integrates with existing strategies to provide a hybrid
human-like reasoning layer on top of mechanical signals.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Groq client - lazy import
_groq_client = None


def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        try:
            from groq import Groq
            s = get_settings()
            if s.groq_api_key:
                _groq_client = Groq(api_key=s.groq_api_key)
            else:
                logger.warning("GROQ_API_KEY not set, LLM advisor disabled")
        except ImportError:
            logger.warning("groq package not installed, LLM advisor disabled")
    return _groq_client


@dataclass
class LLMSignal:
    """LLM-generated trading signal."""
    action: str  # BUY, SELL, HOLD
    confidence: float  # 0.0 ~ 1.0
    rationale: str
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size_pct: float = 0.1  # Recommended position size (% of equity)
    market_sentiment: str = "neutral"  # bullish, bearish, neutral
    risk_level: str = "medium"  # low, medium, high
    time_horizon: str = "short"  # scalp, short, medium


@dataclass
class MarketContext:
    """Aggregated market data for LLM analysis."""
    market: str
    current_price: float
    price_change_1h: float
    price_change_24h: float
    volume_24h: float
    volume_ratio: float  # vs 20-period average
    rsi: float
    macd_signal: str  # bullish, bearish, neutral
    bb_position: str  # above_upper, middle, below_lower
    adx: float
    atr_pct: float
    support_level: float
    resistance_level: float
    recent_highs: List[float]
    recent_lows: List[float]
    btc_correlation: float = 0.0
    kimchi_premium: float = 0.0  # Korea premium


class LLMAdvisor:
    """LLM-powered trading advisor using Groq API."""
    
    def __init__(self):
        self.s = get_settings()
        self._last_call_time: Dict[str, float] = {}
        self._cache: Dict[str, Tuple[float, LLMSignal]] = {}
        self._cache_ttl = 60  # Cache signals for 60 seconds
        
    def analyze(self, ctx: MarketContext) -> Optional[LLMSignal]:
        """Analyze market and generate trading signal."""
        if not self.s.use_ai_verification or not self.s.use_groq:
            return None
            
        # Check cache
        cache_key = f"{ctx.market}_{ctx.current_price:.0f}"
        if cache_key in self._cache:
            cached_time, cached_signal = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_signal
        
        # Rate limiting - max 1 call per market per 30 seconds
        now = time.time()
        if ctx.market in self._last_call_time:
            if now - self._last_call_time[ctx.market] < 30:
                return None
        
        try:
            signal = self._call_llm(ctx)
            if signal:
                self._cache[cache_key] = (now, signal)
                self._last_call_time[ctx.market] = now
            return signal
        except Exception as e:
            logger.error(f"LLM analysis failed for {ctx.market}: {e}")
            return None
    
    def _call_llm(self, ctx: MarketContext) -> Optional[LLMSignal]:
        """Make actual LLM API call."""
        client = _get_groq_client()
        if not client:
            return None
            
        prompt = self._build_prompt(ctx)
        
        try:
            response = client.chat.completions.create(
                model=self.s.groq_model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            return self._parse_response(content, ctx)
            
        except Exception as e:
            logger.error(f"Groq API call failed: {e}")
            return None
    
    def _get_system_prompt(self) -> str:
        return """You are an expert cryptocurrency trading advisor with 15+ years of experience.
Your role is to analyze market data and provide actionable trading signals.

CRITICAL RULES:
1. Capital preservation is the TOP priority. Never risk more than 1-2% per trade.
2. Only recommend BUY when multiple indicators align (confluence).
3. Always set stop-loss and take-profit levels.
4. Be conservative - when uncertain, recommend HOLD.
5. Consider market regime: trending markets favor breakouts, ranging markets favor reversals.
6. Factor in volume - price moves without volume are weak.
7. Consider the broader market (BTC trend) for altcoins.

MARKET REGIMES:
- TRENDING (ADX > 25): Use trend-following strategies
- RANGING (ADX < 25): Use mean-reversion strategies  
- CHAOTIC (high ATR%): Reduce position size or stay out

ENTRY CRITERIA (need 3+ for BUY):
- RSI oversold (<35) or bullish divergence
- Price near strong support
- Volume spike (>1.3x average)
- Positive MACD signal
- Price bouncing off lower Bollinger Band
- ADX trending up (momentum building)

EXIT CRITERIA:
- Take partial profits at 1:1 risk/reward
- Trail stop to breakeven after +1.5%
- Full exit at 1:2 or 1:3 risk/reward

RISK MANAGEMENT:
- Stop-loss: 1.5-2x ATR below entry
- Position size: Risk 1% of equity per trade
- Max drawdown tolerance: 3% daily

You must respond in valid JSON format with these fields:
{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0-1.0,
  "rationale": "Brief explanation",
  "entry_price": number or null,
  "stop_loss": number or null,
  "take_profit": number or null,
  "position_size_pct": 0.05-0.25,
  "market_sentiment": "bullish" | "bearish" | "neutral",
  "risk_level": "low" | "medium" | "high",
  "time_horizon": "scalp" | "short" | "medium"
}"""

    def _build_prompt(self, ctx: MarketContext) -> str:
        return f"""Analyze {ctx.market} and provide a trading signal.

CURRENT MARKET DATA:
- Price: {ctx.current_price:,.0f} KRW
- 1H Change: {ctx.price_change_1h:+.2%}
- 24H Change: {ctx.price_change_24h:+.2%}
- 24H Volume: {ctx.volume_24h:,.0f} KRW
- Volume Ratio (vs avg): {ctx.volume_ratio:.2f}x

TECHNICAL INDICATORS:
- RSI(14): {ctx.rsi:.1f}
- ADX(14): {ctx.adx:.1f}
- ATR%: {ctx.atr_pct:.2%}
- MACD Signal: {ctx.macd_signal}
- Bollinger Band Position: {ctx.bb_position}

KEY LEVELS:
- Support: {ctx.support_level:,.0f} KRW
- Resistance: {ctx.resistance_level:,.0f} KRW
- Recent Highs: {[f'{h:,.0f}' for h in ctx.recent_highs[-3:]]}
- Recent Lows: {[f'{l:,.0f}' for l in ctx.recent_lows[-3:]]}

MARKET CONTEXT:
- BTC Correlation: {ctx.btc_correlation:.2f}
- Kimchi Premium: {ctx.kimchi_premium:+.2%}
- Time: {datetime.now().strftime('%Y-%m-%d %H:%M')} KST

Based on this data, what is your trading recommendation? Consider:
1. Is there a clear trend or is the market ranging?
2. Are we near a key support/resistance level?
3. Is volume confirming price action?
4. What is the risk/reward ratio for a potential trade?

Provide your analysis in JSON format."""

    def _parse_response(self, content: str, ctx: MarketContext) -> Optional[LLMSignal]:
        """Parse LLM response into LLMSignal."""
        try:
            data = json.loads(content)
            
            action = data.get("action", "HOLD").upper()
            if action not in ("BUY", "SELL", "HOLD"):
                action = "HOLD"
            
            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))
            
            # Apply confidence threshold
            if confidence < self.s.min_confidence_for_trade:
                action = "HOLD"
                
            return LLMSignal(
                action=action,
                confidence=confidence,
                rationale=data.get("rationale", "No rationale provided"),
                entry_price=data.get("entry_price"),
                stop_loss=data.get("stop_loss"),
                take_profit=data.get("take_profit"),
                position_size_pct=float(data.get("position_size_pct", 0.1)),
                market_sentiment=data.get("market_sentiment", "neutral"),
                risk_level=data.get("risk_level", "medium"),
                time_horizon=data.get("time_horizon", "short"),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return None


# Global advisor instance
_advisor: Optional[LLMAdvisor] = None


def get_advisor() -> LLMAdvisor:
    global _advisor
    if _advisor is None:
        _advisor = LLMAdvisor()
    return _advisor


def build_market_context(
    market: str,
    candles_1m: List,
    candles_5m: List,
    indicators: Dict,
) -> MarketContext:
    """Build MarketContext from candle data and computed indicators."""
    from . import indicators as ind
    
    if not candles_1m or len(candles_1m) < 60:
        return None
        
    closes = [c.close for c in candles_1m]
    highs = [c.high for c in candles_1m]
    lows = [c.low for c in candles_1m]
    volumes = [c.volume for c in candles_1m]
    
    current_price = closes[-1]
    
    # Price changes
    if len(closes) >= 60:
        price_change_1h = (current_price - closes[-60]) / closes[-60]
    else:
        price_change_1h = 0.0
    
    # Use 24h data from 5m candles if available
    if candles_5m and len(candles_5m) >= 288:
        closes_24h = [c.close for c in candles_5m[-288:]]
        price_change_24h = (current_price - closes_24h[0]) / closes_24h[0]
    else:
        price_change_24h = price_change_1h * 24  # Rough estimate
    
    # Volume
    volume_24h = sum(volumes[-60:]) * 24 if len(volumes) >= 60 else sum(volumes)
    vol_ema = ind.ema(volumes, 20) if len(volumes) >= 20 else sum(volumes) / len(volumes)
    volume_ratio = volumes[-1] / vol_ema if vol_ema > 0 else 1.0
    
    # Technical indicators
    rsi = indicators.get("rsi", 50.0)
    adx = indicators.get("adx", 20.0)
    atr = indicators.get("atr", 0.0)
    atr_pct = atr / current_price if current_price > 0 else 0.0
    
    # MACD signal
    macd_signal = "neutral"
    if "macd" in indicators and "macd_signal" in indicators:
        if indicators["macd"] > indicators["macd_signal"]:
            macd_signal = "bullish"
        elif indicators["macd"] < indicators["macd_signal"]:
            macd_signal = "bearish"
    
    # Bollinger Band position
    bb_position = "middle"
    if "bb_lower" in indicators and "bb_upper" in indicators:
        if current_price < indicators["bb_lower"]:
            bb_position = "below_lower"
        elif current_price > indicators["bb_upper"]:
            bb_position = "above_upper"
    
    # Support/Resistance (simple pivot points)
    recent_highs = sorted(highs[-20:], reverse=True)[:5]
    recent_lows = sorted(lows[-20:])[:5]
    support_level = sum(recent_lows[:3]) / 3 if recent_lows else current_price * 0.98
    resistance_level = sum(recent_highs[:3]) / 3 if recent_highs else current_price * 1.02
    
    return MarketContext(
        market=market,
        current_price=current_price,
        price_change_1h=price_change_1h,
        price_change_24h=price_change_24h,
        volume_24h=volume_24h,
        volume_ratio=volume_ratio,
        rsi=rsi,
        macd_signal=macd_signal,
        bb_position=bb_position,
        adx=adx,
        atr_pct=atr_pct,
        support_level=support_level,
        resistance_level=resistance_level,
        recent_highs=recent_highs,
        recent_lows=recent_lows,
    )

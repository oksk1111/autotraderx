"""Market Sentiment Analysis — Global indicators and Kimchi Premium tracking.

Provides additional market context for trading decisions:
1. Kimchi Premium (Korea vs Global price spread)
2. BTC Dominance trend
3. Fear & Greed Index (if available)
4. Global market correlation

These indicators help filter out risky market conditions and
identify favorable trading environments.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MarketSentiment:
    """Aggregated market sentiment data."""
    timestamp: float
    
    # Kimchi Premium
    kimchi_premium_pct: float = 0.0  # Positive = Korea premium
    kimchi_premium_trend: str = "stable"  # rising, falling, stable
    
    # BTC Dominance
    btc_dominance: float = 0.0  # 0-100%
    btc_dominance_trend: str = "stable"
    
    # Fear & Greed (0-100, 0=extreme fear, 100=extreme greed)
    fear_greed_index: int = 50
    fear_greed_label: str = "Neutral"
    
    # Global market state
    global_trend: str = "neutral"  # bullish, bearish, neutral
    risk_level: str = "medium"  # low, medium, high, extreme
    
    # Trading recommendation based on sentiment
    trade_bias: str = "neutral"  # bullish, bearish, neutral
    confidence_modifier: float = 1.0  # Multiply signal confidence by this
    
    def is_risky(self) -> bool:
        """Check if market conditions are too risky for new positions."""
        # High kimchi premium often precedes corrections
        if self.kimchi_premium_pct > 5.0:
            return True
        # Extreme fear or greed
        if self.fear_greed_index < 15 or self.fear_greed_index > 85:
            return True
        if self.risk_level == "extreme":
            return True
        return False
    
    def get_confidence_modifier(self) -> float:
        """Get confidence modifier based on sentiment."""
        modifier = 1.0
        
        # Kimchi premium adjustments
        if self.kimchi_premium_pct > 3.0:
            modifier *= 0.8  # Reduce confidence when premium is high
        elif self.kimchi_premium_pct < -2.0:
            modifier *= 1.1  # Slight boost when at discount
        
        # Fear & Greed adjustments
        if self.fear_greed_index < 25:
            # Extreme fear = good buying opportunity
            modifier *= 1.15
        elif self.fear_greed_index > 75:
            # Extreme greed = be cautious
            modifier *= 0.85
        
        return max(0.5, min(1.3, modifier))


class SentimentAnalyzer:
    """Fetches and analyzes global market sentiment."""
    
    def __init__(self):
        self.s = get_settings()
        self._cache: Optional[MarketSentiment] = None
        self._cache_time: float = 0
        self._cache_ttl: int = 300  # 5 minutes
        self._kimchi_history: list[float] = []
        
    async def get_sentiment(self) -> MarketSentiment:
        """Get current market sentiment (cached)."""
        now = time.time()
        if self._cache and (now - self._cache_time) < self._cache_ttl:
            return self._cache
        
        sentiment = MarketSentiment(timestamp=now)
        
        # Fetch data in parallel
        async with httpx.AsyncClient(timeout=10.0) as client:
            tasks = [
                self._fetch_kimchi_premium(client),
                self._fetch_fear_greed(client),
                self._fetch_btc_dominance(client),
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Apply results
        if isinstance(results[0], dict):
            sentiment.kimchi_premium_pct = results[0].get("premium", 0.0)
            sentiment.kimchi_premium_trend = results[0].get("trend", "stable")
        
        if isinstance(results[1], dict):
            sentiment.fear_greed_index = results[1].get("value", 50)
            sentiment.fear_greed_label = results[1].get("label", "Neutral")
        
        if isinstance(results[2], dict):
            sentiment.btc_dominance = results[2].get("dominance", 50.0)
            sentiment.btc_dominance_trend = results[2].get("trend", "stable")
        
        # Compute composite indicators
        sentiment.risk_level = self._compute_risk_level(sentiment)
        sentiment.trade_bias = self._compute_trade_bias(sentiment)
        sentiment.confidence_modifier = sentiment.get_confidence_modifier()
        
        self._cache = sentiment
        self._cache_time = now
        return sentiment
    
    async def _fetch_kimchi_premium(self, client: httpx.AsyncClient) -> Dict:
        """Calculate Kimchi Premium from Upbit vs Binance prices."""
        try:
            # Fetch Upbit BTC price
            upbit_resp = await client.get(
                "https://api.upbit.com/v1/ticker",
                params={"markets": "KRW-BTC"}
            )
            upbit_data = upbit_resp.json()
            upbit_price = upbit_data[0]["trade_price"] if upbit_data else 0
            
            # Fetch Binance BTC price (USDT)
            binance_resp = await client.get(
                "https://api.binance.com/api/v3/ticker/price",
                params={"symbol": "BTCUSDT"}
            )
            binance_data = binance_resp.json()
            binance_price = float(binance_data.get("price", 0))
            
            # Fetch USD/KRW exchange rate
            # Using a proxy or cached rate (simplified)
            usd_krw = 1380  # Default fallback
            try:
                fx_resp = await client.get(
                    "https://api.exchangerate-api.com/v4/latest/USD",
                    timeout=5.0
                )
                fx_data = fx_resp.json()
                usd_krw = fx_data.get("rates", {}).get("KRW", 1380)
            except Exception:
                pass
            
            if upbit_price > 0 and binance_price > 0 and usd_krw > 0:
                binance_krw = binance_price * usd_krw
                premium = ((upbit_price - binance_krw) / binance_krw) * 100
                
                # Track history for trend
                self._kimchi_history.append(premium)
                if len(self._kimchi_history) > 12:  # Keep 1 hour of 5-min data
                    self._kimchi_history = self._kimchi_history[-12:]
                
                # Compute trend
                trend = "stable"
                if len(self._kimchi_history) >= 3:
                    recent_avg = sum(self._kimchi_history[-3:]) / 3
                    older_avg = sum(self._kimchi_history[:3]) / 3
                    if recent_avg > older_avg + 0.5:
                        trend = "rising"
                    elif recent_avg < older_avg - 0.5:
                        trend = "falling"
                
                return {"premium": round(premium, 2), "trend": trend}
                
        except Exception as e:
            logger.debug(f"Kimchi premium fetch failed: {e}")
        
        return {"premium": 0.0, "trend": "stable"}
    
    async def _fetch_fear_greed(self, client: httpx.AsyncClient) -> Dict:
        """Fetch Crypto Fear & Greed Index."""
        try:
            resp = await client.get(
                "https://api.alternative.me/fng/",
                params={"limit": 1}
            )
            data = resp.json()
            if data.get("data"):
                entry = data["data"][0]
                return {
                    "value": int(entry.get("value", 50)),
                    "label": entry.get("value_classification", "Neutral")
                }
        except Exception as e:
            logger.debug(f"Fear & Greed fetch failed: {e}")
        
        return {"value": 50, "label": "Neutral"}
    
    async def _fetch_btc_dominance(self, client: httpx.AsyncClient) -> Dict:
        """Fetch BTC market dominance."""
        try:
            resp = await client.get(
                "https://api.coingecko.com/api/v3/global"
            )
            data = resp.json()
            if data.get("data"):
                dominance = data["data"].get("market_cap_percentage", {}).get("btc", 50.0)
                return {"dominance": round(dominance, 1), "trend": "stable"}
        except Exception as e:
            logger.debug(f"BTC dominance fetch failed: {e}")
        
        return {"dominance": 50.0, "trend": "stable"}
    
    def _compute_risk_level(self, sentiment: MarketSentiment) -> str:
        """Compute overall market risk level."""
        risk_score = 0
        
        # Kimchi premium risk
        if abs(sentiment.kimchi_premium_pct) > 5:
            risk_score += 3
        elif abs(sentiment.kimchi_premium_pct) > 3:
            risk_score += 2
        elif abs(sentiment.kimchi_premium_pct) > 1.5:
            risk_score += 1
        
        # Fear & Greed risk
        fg = sentiment.fear_greed_index
        if fg < 20 or fg > 80:
            risk_score += 2
        elif fg < 30 or fg > 70:
            risk_score += 1
        
        # BTC dominance (high dominance during fear = risk-off)
        if sentiment.btc_dominance > 55 and fg < 40:
            risk_score += 1
        
        if risk_score >= 5:
            return "extreme"
        elif risk_score >= 3:
            return "high"
        elif risk_score >= 1:
            return "medium"
        return "low"
    
    def _compute_trade_bias(self, sentiment: MarketSentiment) -> str:
        """Compute directional bias based on sentiment."""
        score = 0
        
        # Fear = bullish (buy fear), Greed = bearish (sell greed)
        fg = sentiment.fear_greed_index
        if fg < 30:
            score += 2
        elif fg < 45:
            score += 1
        elif fg > 70:
            score -= 2
        elif fg > 55:
            score -= 1
        
        # Negative kimchi premium = bullish (discount)
        if sentiment.kimchi_premium_pct < -1:
            score += 1
        elif sentiment.kimchi_premium_pct > 3:
            score -= 1
        
        if score >= 2:
            return "bullish"
        elif score <= -2:
            return "bearish"
        return "neutral"


# Global instance
_analyzer: Optional[SentimentAnalyzer] = None


def get_sentiment_analyzer() -> SentimentAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentAnalyzer()
    return _analyzer


async def get_market_sentiment() -> MarketSentiment:
    """Convenience function to get current sentiment."""
    return await get_sentiment_analyzer().get_sentiment()


def get_sentiment_sync() -> Optional[MarketSentiment]:
    """Synchronous wrapper for sentiment (uses cached value or None)."""
    analyzer = get_sentiment_analyzer()
    return analyzer._cache

"""v8.0 Strategy layer — Hybrid LLM + Mechanical Trading."""
from .base import Signal, Strategy
from .indicators import (
    rsi, ema, sma, atr, bollinger, donchian_high, donchian_low, 
    adx, volume_zscore, macd, stochastic, obv, vwap
)
from .regime import Regime, RegimeClassifier
from .mean_reversion import MeanReversionStrategy
from .trend_following import TrendFollowingStrategy
from .universe import UniverseSelector, rank_candidates, UniverseCandidate
from .hybrid_strategy import HybridStrategy, AggressiveMomentumStrategy, DipBuyingStrategy
from .llm_advisor import LLMAdvisor, LLMSignal, MarketContext, get_advisor, build_market_context

__all__ = [
    # Base
    "Signal",
    "Strategy",
    # Indicators
    "rsi",
    "ema",
    "sma",
    "atr",
    "bollinger",
    "donchian_high",
    "donchian_low",
    "adx",
    "volume_zscore",
    "macd",
    "stochastic",
    "obv",
    "vwap",
    # Regime
    "Regime",
    "RegimeClassifier",
    # Strategies
    "MeanReversionStrategy",
    "TrendFollowingStrategy",
    "HybridStrategy",
    "AggressiveMomentumStrategy",
    "DipBuyingStrategy",
    # Universe
    "UniverseSelector",
    "rank_candidates",
    "UniverseCandidate",
    # LLM
    "LLMAdvisor",
    "LLMSignal",
    "MarketContext",
    "get_advisor",
    "build_market_context",
]

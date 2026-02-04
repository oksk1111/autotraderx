from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import pandas as pd
import pyupbit
from app.core.logging import get_logger

logger = get_logger(__name__)

class InvestmentPersona(ABC):
    def __init__(self, name: str, risk_level: str, description: str):
        self.name = name
        self.risk_level = risk_level  # 'low', 'medium', 'high'
        self.description = description

    @abstractmethod
    def analyze(self, market: str, df: pd.DataFrame) -> Dict:
        """
        Analyze the market data and return a decision.
        Returns:
            {
                "action": "BUY" | "SELL" | "HOLD",
                "confidence": float (0.0 - 1.0),
                "reason": str
            }
        """
        pass

class WarrenBuffettPersona(InvestmentPersona):
    """
    Value Investor Persona.
    Looks for oversold conditions (RSI < 30) and steady accumulation.
    Low risk, patient.
    """
    def __init__(self):
        super().__init__("Warren Buffett (Value)", "low", "Buy when others are fearful. Targets oversold assets with fundamentals.")

    def analyze(self, market: str, df: pd.DataFrame) -> Dict:
        if df is None or len(df) < 50:
            return {"action": "HOLD", "confidence": 0.0, "reason": "Insufficient data"}

        # Calculate RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1]

        # Value conditions
        if current_rsi < 30:
            return {
                "action": "BUY",
                "confidence": 0.8 + (30 - current_rsi) / 100,  # Higher confidence as RSI drops
                "reason": f"Oversold condition (RSI: {current_rsi:.1f})"
            }
        elif current_rsi > 70:
             return {
                "action": "SELL",
                "confidence": 0.7,
                "reason": f"Overbought condition (RSI: {current_rsi:.1f})"
            }
        
        return {"action": "HOLD", "confidence": 0.0, "reason": "Market is neutral"}

class LarryWilliamsPersona(InvestmentPersona):
    """
    Volatility Breakout Persona.
    Buys when price breaks the volatility range.
    High risk, short term.
    """
    def __init__(self):
        super().__init__("Larry Williams (Volatility)", "high", "Volatility Breakout Strategy. Catch strong moves early.")

    def analyze(self, market: str, df: pd.DataFrame) -> Dict:
        if df is None or len(df) < 20:
             return {"action": "HOLD", "confidence": 0.0, "reason": "Insufficient data"}
        
        # Latest completed candle (previous day/hour)
        prev = df.iloc[-2]
        current = df.iloc[-1]
        
        range_val = prev['high'] - prev['low']
        k = 0.5
        target_price = current['open'] + range_val * k
        
        # Check breakout
        if current['close'] > target_price:
             return {
                "action": "BUY",
                "confidence": 0.75,
                "reason": f"Volatility Breakout (Price {current['close']} > Target {target_price})"
            }
        
        # Simple stop loss / trailing logic handled by main engine usually, 
        # but here we can signal sell if trend reverses
        return {"action": "HOLD", "confidence": 0.0, "reason": "No breakout"}

class MomentumPersona(InvestmentPersona):
    """
    Trend Following Persona (Golden Cross).
    Buys when MA20 crosses above MA60.
    Medium risk.
    """
    def __init__(self):
        super().__init__("The Trend Follower", "medium", "Trend is your friend. Golden Cross strategy.")

    def analyze(self, market: str, df: pd.DataFrame) -> Dict:
        if df is None or len(df) < 65:
             return {"action": "HOLD", "confidence": 0.0, "reason": "Insufficient data"}
        
        # Calculate MA
        ma20 = df['close'].rolling(window=20).mean()
        ma60 = df['close'].rolling(window=60).mean()
        
        prev_ma20 = ma20.iloc[-2]
        prev_ma60 = ma60.iloc[-2]
        curr_ma20 = ma20.iloc[-1]
        curr_ma60 = ma60.iloc[-1]
        
        # Golden Cross
        if prev_ma20 <= prev_ma60 and curr_ma20 > curr_ma60:
             return {
                "action": "BUY",
                "confidence": 0.85,
                "reason": "Golden Cross (MA20 crossed above MA60)"
            }
        # Dead Cross
        elif prev_ma20 >= prev_ma60 and curr_ma20 < curr_ma60:
             return {
                "action": "SELL",
                "confidence": 0.85,
                "reason": "Dead Cross (MA20 crossed below MA60)"
            }
            
        return {"action": "HOLD", "confidence": 0.0, "reason": "Trend continuation"}

class PersonaManager:
    def __init__(self):
        self.personas = [
            WarrenBuffettPersona(),
            LarryWilliamsPersona(),
            MomentumPersona()
        ]
    
    def get_personas(self) -> List[InvestmentPersona]:
        return self.personas
    
    def evaluate_all(self, market: str, df: pd.DataFrame) -> List[Dict]:
        results = []
        for persona in self.personas:
            decision = persona.analyze(market, df)
            decision['persona'] = persona.name
            results.append(decision)
        return results

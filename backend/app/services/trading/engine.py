from typing import Dict, List, Optional
from app.services.upbit.client import upbit_client
from app.services.indicators.technical import technical_indicators
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class TradingEngine:
    """매매 엔진 - 자동 매수/매도 로직"""
    
    def __init__(self):
        self.upbit = upbit_client
        self.indicators = technical_indicators
        self.positions: Dict[str, Dict] = {}
    
    def analyze_market(self, market: str, candles: List[Dict]) -> Dict:
        """시장 분석 및 매매 신호 생성"""
        if not candles:
            return {"signal": "hold", "confidence": 0.0, "reason": "No data"}
        
        # 기술적 지표 계산
        indicators = self.indicators.calculate_all_indicators(candles)
        
        # 매수/매도 신호 판단
        signal = self._generate_signal(indicators)
        
        return {
            "market": market,
            "signal": signal["action"],
            "confidence": signal["confidence"],
            "reason": signal["reason"],
            "indicators": indicators,
            "current_price": indicators.get("current_price", 0)
        }
    
    def _generate_signal(self, indicators: Dict) -> Dict:
        """매매 신호 생성 로직"""
        rsi = indicators.get("rsi", 50)
        macd = indicators.get("macd", {})
        trend = indicators.get("trend", "neutral")
        current_price = indicators.get("current_price", 0)
        ma_5 = indicators.get("ma_5", 0)
        ma_20 = indicators.get("ma_20", 0)
        mfi = indicators.get("mfi", 50)
        stoch = indicators.get("stochastic", {})
        
        buy_signals = 0
        sell_signals = 0
        reasons = []
        
        # 매수 조건 체크
        # 1. RSI 과매도 구간
        if rsi < settings.RSI_OVERSOLD:
            buy_signals += 1
            reasons.append(f"RSI oversold ({rsi:.2f})")
        
        # 2. MACD 골든크로스
        if macd.get("histogram", 0) > 0 and macd.get("macd", 0) > macd.get("signal", 0):
            buy_signals += 1
            reasons.append("MACD golden cross")
        
        # 3. 단기 이동평균선이 장기 이동평균선을 상향 돌파
        if ma_5 > ma_20 and current_price > ma_5:
            buy_signals += 1
            reasons.append("MA golden cross")
        
        # 4. 상승 추세
        if trend == "uptrend":
            buy_signals += 1
            reasons.append("Uptrend detected")
        
        # 5. MFI 과매도
        if mfi < 30:
            buy_signals += 1
            reasons.append(f"MFI oversold ({mfi:.2f})")
        
        # 매도 조건 체크
        # 1. RSI 과매수 구간
        if rsi > settings.RSI_OVERBOUGHT:
            sell_signals += 1
            reasons.append(f"RSI overbought ({rsi:.2f})")
        
        # 2. MACD 데드크로스
        if macd.get("histogram", 0) < 0 and macd.get("macd", 0) < macd.get("signal", 0):
            sell_signals += 1
            reasons.append("MACD dead cross")
        
        # 3. 단기 이동평균선이 장기 이동평균선을 하향 돌파
        if ma_5 < ma_20 and current_price < ma_5:
            sell_signals += 1
            reasons.append("MA dead cross")
        
        # 4. 하락 추세
        if trend == "downtrend":
            sell_signals += 1
            reasons.append("Downtrend detected")
        
        # 5. MFI 과매수
        if mfi > 70:
            sell_signals += 1
            reasons.append(f"MFI overbought ({mfi:.2f})")
        
        # 신호 결정
        # 매수 신호가 2개 이상이면 매수
        if buy_signals >= 2 and sell_signals == 0:
            return {
                "action": "buy",
                "confidence": min(buy_signals / 5.0, 1.0),
                "reason": " | ".join(reasons)
            }
        # 매도 신호가 2개 이상이면 매도
        elif sell_signals >= 2:
            return {
                "action": "sell",
                "confidence": min(sell_signals / 5.0, 1.0),
                "reason": " | ".join(reasons)
            }
        else:
            return {
                "action": "hold",
                "confidence": 0.5,
                "reason": "No clear signal"
            }
    
    def execute_trade(
        self,
        market: str,
        signal: str,
        amount: Optional[float] = None
    ) -> Dict:
        """거래 실행"""
        try:
            if signal == "buy":
                return self._execute_buy(market, amount)
            elif signal == "sell":
                return self._execute_sell(market)
            else:
                return {"status": "skipped", "reason": "Hold signal"}
        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def _execute_buy(self, market: str, amount: Optional[float] = None) -> Dict:
        """매수 실행"""
        # 현재가 조회
        ticker = self.upbit.get_ticker([market])
        if not ticker:
            return {"status": "error", "message": "Failed to get ticker"}
        
        current_price = ticker[0]['trade_price']
        
        # 매수 금액 결정
        if amount is None:
            amount = settings.MAX_TRADE_AMOUNT
        
        # 매수 수량 계산
        volume = amount / current_price
        
        # 주문 실행
        order = self.upbit.place_order(
            market=market,
            side="bid",
            price=current_price,
            volume=volume,
            ord_type="limit"
        )
        
        if "error" in order:
            return {"status": "error", "message": order["error"]}
        
        # 포지션 기록
        self.positions[market] = {
            "avg_buy_price": current_price,
            "volume": volume,
            "order_id": order.get("uuid")
        }
        
        logger.info(f"Buy order placed: {market} at {current_price}, volume: {volume}")
        
        return {
            "status": "success",
            "order": order,
            "market": market,
            "price": current_price,
            "volume": volume
        }
    
    def _execute_sell(self, market: str) -> Dict:
        """매도 실행"""
        # 포지션 확인
        if market not in self.positions:
            return {"status": "error", "message": "No position found"}
        
        position = self.positions[market]
        volume = position["volume"]
        
        # 현재가 조회
        ticker = self.upbit.get_ticker([market])
        if not ticker:
            return {"status": "error", "message": "Failed to get ticker"}
        
        current_price = ticker[0]['trade_price']
        
        # 주문 실행
        order = self.upbit.place_order(
            market=market,
            side="ask",
            volume=volume,
            ord_type="market"
        )
        
        if "error" in order:
            return {"status": "error", "message": order["error"]}
        
        # 수익률 계산
        buy_price = position["avg_buy_price"]
        profit_percent = ((current_price - buy_price) / buy_price) * 100
        
        # 포지션 제거
        del self.positions[market]
        
        logger.info(f"Sell order placed: {market} at {current_price}, profit: {profit_percent:.2f}%")
        
        return {
            "status": "success",
            "order": order,
            "market": market,
            "buy_price": buy_price,
            "sell_price": current_price,
            "profit_percent": profit_percent
        }
    
    def check_stop_loss_take_profit(self, market: str) -> Optional[str]:
        """손절/익절 체크"""
        if market not in self.positions:
            return None
        
        position = self.positions[market]
        buy_price = position["avg_buy_price"]
        
        # 현재가 조회
        ticker = self.upbit.get_ticker([market])
        if not ticker:
            return None
        
        current_price = ticker[0]['trade_price']
        profit_percent = ((current_price - buy_price) / buy_price) * 100
        
        # 손절 체크
        if profit_percent <= -settings.STOP_LOSS_PERCENT:
            logger.warning(f"Stop loss triggered for {market}: {profit_percent:.2f}%")
            return "sell"
        
        # 익절 체크
        if profit_percent >= settings.TAKE_PROFIT_PERCENT:
            logger.info(f"Take profit triggered for {market}: {profit_percent:.2f}%")
            return "sell"
        
        return None
    
    def get_positions(self) -> Dict[str, Dict]:
        """현재 포지션 조회"""
        return self.positions


trading_engine = TradingEngine()

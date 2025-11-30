from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.llm.verifier import DualLLMVerifier
from app.ml.predictor import HybridPredictor
from app.models import AutoTradingConfig, MLDecisionLog, TradeLog
from app.trading.emergency import EmergencyGuard

logger = get_logger(__name__)


@dataclass
class TradeDecisionResult:
    approved: bool
    action: str
    market: str
    confidence: float
    rationale: str
    emergency: bool
    investment_ratio: float = 0.1  # 기본값 10%
    max_loss_acceptable: float = 0.03
    take_profit_target: float = 0.05


class TradingEngine:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.predictor = HybridPredictor(settings=self.settings)
        self.verifier = DualLLMVerifier(self.settings)
        self.guard = EmergencyGuard(self.settings)

    async def decide(self, db: Session, market: str, features: Dict[str, float], account_info: Dict[str, Any] | None = None) -> TradeDecisionResult:
        config = db.query(AutoTradingConfig).first()
        if not config or not config.is_active:
            return TradeDecisionResult(False, "HOLD", market, 0.0, "System inactive", False)

        ml_signal = self.predictor.infer({"market": market, **features})
        summary = self._build_summary(market, ml_signal)

        emergency = self.guard.tripped(ml_signal, features)
        if emergency:
            self._log_decision(db, market, ml_signal, True, True, True, "Emergency sell triggered")
            return TradeDecisionResult(
                True, "SELL", market, ml_signal.sell_probability, 
                "Emergency detected", True,
                investment_ratio=1.0  # 긴급 상황이면 전량 매도
            )

        if not self.settings.use_ai_verification:
            self._log_decision(db, market, ml_signal, False, False, False, "AI verification bypassed")
            return TradeDecisionResult(
                True, ml_signal.action, market, 
                max(ml_signal.buy_probability, ml_signal.sell_probability), 
                "Bypass", False
            )

        groq_ok, ollama_ok = await self.verifier.verify(summary)
        # 둘 다 승인해야 거래 실행
        approved = groq_ok and ollama_ok and ml_signal.action != "HOLD"
        
        # LLM을 사용하여 투자 비율 결정 (둘 다 승인했을 때만)
        if approved and account_info:
            investment_decision = await self.verifier.decide_investment_ratio(
                ml_signal={
                    "buy_probability": ml_signal.buy_probability,
                    "sell_probability": ml_signal.sell_probability,
                    "confidence": max(ml_signal.buy_probability, ml_signal.sell_probability),
                    "emergency_score": ml_signal.emergency_score
                },
                account_info=account_info,
                market_info=features
            )
            investment_ratio = investment_decision["investment_ratio"]
            max_loss = investment_decision["max_loss_acceptable"]
            take_profit = investment_decision["take_profit_target"]
            rationale = f"LLM approvals + {investment_decision['reasoning']}"
        else:
            # ML 신뢰도 기반 자동 투자 비율 계산
            confidence = max(ml_signal.buy_probability, ml_signal.sell_probability)
            if confidence >= 0.8:
                investment_ratio = 0.3  # 높은 신뢰도: 30%
            elif confidence >= 0.65:
                investment_ratio = 0.2  # 중간 신뢰도: 20%
            elif confidence >= 0.55:
                investment_ratio = 0.1  # 낮은 신뢰도: 10%
            else:
                investment_ratio = 0.05  # 매우 낮은 신뢰도: 5%
            
            max_loss = 0.03
            take_profit = 0.05
            llm_status = "Groq ✅" if groq_ok else "Groq ❌"
            llm_status += f" Ollama {'✅' if ollama_ok else '❌'}"
            rationale = f"{llm_status} (신뢰도 기반 자동: {investment_ratio*100:.0f}%)" if approved else "LLM veto"
        
        self._log_decision(db, market, ml_signal, groq_ok, ollama_ok, emergency, rationale)
        return TradeDecisionResult(
            approved, ml_signal.action, market, 
            max(ml_signal.buy_probability, ml_signal.sell_probability), 
            rationale, False,
            investment_ratio=investment_ratio,
            max_loss_acceptable=max_loss,
            take_profit_target=take_profit
        )

    def _build_summary(self, market: str, signal: Any) -> str:
        return (
            f"Market: {market}\n"
            f"Buy probability: {signal.buy_probability:.3f}\n"
            f"Sell probability: {signal.sell_probability:.3f}\n"
            f"Action: {signal.action}\n"
            "Validate if market conditions, sentiment, and macro justify executing this trade."
        )

    def _log_decision(
        self,
        db: Session,
        market: str,
        ml_signal,
        groq_alignment: bool,
        ollama_alignment: bool,
        emergency: bool,
        rationale: str,
    ) -> None:
        # 상세한 판단 근거 생성
        detailed_rationale = f"""
판단: {ml_signal.action}
근거:
- ML 예측: Buy {ml_signal.buy_probability:.1%} / Sell {ml_signal.sell_probability:.1%}
- 신뢰도: {max(ml_signal.buy_probability, ml_signal.sell_probability):.1%}
- Groq LLM: {'승인' if groq_alignment else '거부'}
- Ollama LLM: {'승인' if ollama_alignment else '거부'}
- 긴급 상황: {'감지됨' if emergency else '정상'}
상세: {rationale}
        """.strip()
        
        log = MLDecisionLog(
            market=market,
            predicted_move=ml_signal.action,
            confidence=max(ml_signal.buy_probability, ml_signal.sell_probability),
            groq_alignment=groq_alignment,
            ollama_alignment=ollama_alignment,
            emergency_triggered=emergency,
            rationale=detailed_rationale,
        )
        db.add(log)
        db.commit()

        if rationale.startswith("Emergency"):
            logger.warning("Emergency decision logged for %s", market)


class TradeExecutor:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def execute(self, db: Session, decision: TradeDecisionResult, available_balance: float | None = None) -> None:
        if not decision.approved:
            return
        
        # 투자 금액 계산: 가용 자금 * 투자 비율
        if available_balance is None:
            available_balance = self.settings.default_trade_amount
        
        trade_amount = available_balance * decision.investment_ratio
        
        # 실제 Upbit API 호출하여 거래 실행
        import pyupbit
        try:
            upbit = pyupbit.Upbit(self.settings.upbit_access_key, self.settings.upbit_secret_key)
            
            if decision.action == "BUY":
                # 매수: KRW로 코인 구매
                result = upbit.buy_market_order(decision.market, trade_amount)
                logger.info(f"✅ BUY 주문 실행: {decision.market}, {trade_amount:,.0f}원 ({decision.investment_ratio*100:.0f}%)")
            elif decision.action == "SELL":
                # 매도: 보유 코인 전량 매도
                ticker = decision.market.split('-')[1]
                balance = upbit.get_balance(ticker)
                try:
                    balance_amount = float(balance) if balance else 0.0  # type: ignore
                except (ValueError, TypeError):
                    balance_amount = 0.0
                    
                if balance_amount > 0:
                    result = upbit.sell_market_order(decision.market, balance_amount)
                    logger.info(f"✅ SELL 주문 실행: {decision.market}, {balance_amount} {ticker} 전량 매도")
                else:
                    logger.warning(f"⚠️ SELL 실패: {decision.market} 보유량 없음")
                    result = None
            else:
                result = None
                
        except Exception as e:
            logger.error(f"❌ 거래 실행 실패: {decision.market} {decision.action} - {e}")
            result = None
        
        # DB에 거래 로그 저장 (실패해도 계속 진행)
        try:
            trade = TradeLog(
                market=decision.market,
                side=decision.action,
                amount=trade_amount,
                reason=decision.rationale,
                context={
                    "confidence": decision.confidence, 
                    "emergency": decision.emergency,
                    "investment_ratio": decision.investment_ratio,
                    "max_loss_acceptable": decision.max_loss_acceptable,
                    "take_profit_target": decision.take_profit_target,
                    "available_balance": available_balance,
                    "upbit_result": str(result) if result else None
                },
            )
            db.add(trade)
            db.commit()
        except Exception as e:
            logger.error(f"거래 로그 저장 실패: {e}")
            db.rollback()

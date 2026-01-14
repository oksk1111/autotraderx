from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.llm.verifier import DualLLMVerifier
from app.ml.predictor import HybridPredictor
from app.models import AutoTradingConfig, MLDecisionLog, TradeLog, TradePosition
from app.services.signal_filter import SignalFilter
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
        self.signal_filter = SignalFilter(self.settings)

    async def decide(self, db: Session, market: str, features: Dict[str, float], account_info: Dict[str, Any] | None = None) -> TradeDecisionResult:
        config = db.query(AutoTradingConfig).first()
        if not config or not config.is_active:
            return TradeDecisionResult(False, "HOLD", market, 0.0, "System inactive", False)

        ml_signal = self.predictor.infer({"market": market, **features})
        
        # ML 모델이 비활성화된 경우(Confidence=0.0), 기술적 지표만으로 판단하거나 Skip
        # 여기서는 기본적으로 ML Signal이 없으면 TradingEngine은 HOLD를 반환함.
        # BreakoutStrategy 등 상위 엔진에서 이미 처리했으므로 여기로 도달했다면 
        # ML 기반 로직을 원했지만 모델이 없는 경우임.
        if ml_signal.confidence == 0.0:
             return TradeDecisionResult(False, "HOLD", market, 0.0, "ML models disabled", False)

        logger.info(f"🤖 {market} ML 예측: {ml_signal.action} (Buy: {ml_signal.buy_probability:.1%}, Sell: {ml_signal.sell_probability:.1%}, Confidence: {max(ml_signal.buy_probability, ml_signal.sell_probability):.1%})")
        
        # 신호 필터링: 연속 신호 차단 (단, 고신뢰도는 허용)
        confidence = max(ml_signal.buy_probability, ml_signal.sell_probability)
        signal_allowed, filter_reason = self.signal_filter.should_allow_trade(market, ml_signal.action, confidence)
        if not signal_allowed:
            logger.info(f"⏸️ {market}: {filter_reason}")
            return TradeDecisionResult(False, "HOLD", market, 0.0, filter_reason, False)
        
        summary = self._build_summary(market, ml_signal)

        emergency = self.guard.tripped(ml_signal, features)
        if emergency:
            self._log_decision(db, market, ml_signal, True, True, True, "Emergency sell triggered")
            return TradeDecisionResult(
                True, "SELL", market, ml_signal.sell_probability, 
                "Emergency detected", True,
                investment_ratio=1.0,  # 긴급 상황이면 전량 매도
                max_loss_acceptable=0.02,
                take_profit_target=0.02
            )

        # ML 기반 거래 (AI 검증 비활성화 시)
        if not self.settings.use_ai_verification:
            approved = ml_signal.action != "HOLD"
            confidence = max(ml_signal.buy_probability, ml_signal.sell_probability)
            
            # ML 신뢰도 기반 투자 비율 (워뇨띠 스타일: 소액 분산)
            if confidence >= 0.8:
                investment_ratio = 0.15  # 높은 신뢰도: 15%
            elif confidence >= 0.7:
                investment_ratio = 0.10  # 중간 신뢰도: 10%
            elif confidence >= 0.6:
                investment_ratio = 0.07  # 보통 신뢰도: 7%
            else:
                investment_ratio = 0.05  # 낮은 신뢰도: 5%
            
            self._log_decision(db, market, ml_signal, False, False, False, f"ML only: {ml_signal.action} (confidence: {confidence:.1%})")
            
            return TradeDecisionResult(
                approved, ml_signal.action, market, confidence,
                f"ML 기반 거래 (신뢰도: {confidence:.1%})", False,
                investment_ratio=investment_ratio,
                max_loss_acceptable=0.02,  # 워뇨띠 스타일: -2% 손절
                take_profit_target=0.02  # 워뇨띠 스타일: +2% 익절
            )

        groq_ok, ollama_ok = await self.verifier.verify(summary)
        
        # LLM 응답 실패(None)와 거부(False) 구분
        # None = 응답 실패 (타임아웃/에러) -> ML 신호로 진행
        # False = 명시적 거부 -> 거래 중단
        
        # 둘 다 명시적으로 거부한 경우만 거래 중단
        if groq_ok is False and ollama_ok is False:
            logger.warning(f"❌ {market}: 두 LLM 모두 거부 - 거래 중단")
            self._log_decision(db, market, ml_signal, False, False, emergency, "Both LLMs rejected")
            return TradeDecisionResult(False, "HOLD", market, 0.0, "Both LLMs rejected", False)
        
        # 하나라도 응답 실패(None)하면 ML 신호만으로 진행
        llm_failed = (groq_ok is None) or (ollama_ok is None)
        
        if llm_failed:
            logger.warning(f"⚠️ {market}: LLM 응답 실패 - ML 신호만으로 진행 (Groq={groq_ok}, Ollama={ollama_ok})")
            # ML 신호만으로 거래 승인
            approved = ml_signal.action != "HOLD"
            groq_status = "⚠️" if groq_ok is None else ("✅" if groq_ok else "❌")
            ollama_status = "⚠️" if ollama_ok is None else ("✅" if ollama_ok else "❌")
            rationale_prefix = f"Groq {groq_status} Ollama {ollama_status} (LLM 실패, ML 신호 사용)"
        else:
            # 둘 다 응답 받음 - 둘 다 승인해야 거래 실행
            approved = groq_ok and ollama_ok and ml_signal.action != "HOLD"
            groq_status = "✅" if groq_ok else "❌"
            ollama_status = "✅" if ollama_ok else "❌"
            rationale_prefix = f"Groq {groq_status} Ollama {ollama_status}"
        
        # LLM을 사용하여 투자 비율 결정 (둘 다 승인했을 때만)
        if approved and not llm_failed and account_info:
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
            rationale = f"{rationale_prefix} + {investment_decision['reasoning']}"
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
            rationale = f"{rationale_prefix} (신뢰도 기반 자동: {investment_ratio*100:.0f}%)" if approved else f"{rationale_prefix} (veto)"
        
        # None을 False로 변환하여 로깅
        self._log_decision(db, market, ml_signal, bool(groq_ok), bool(ollama_ok), emergency, rationale)
        return TradeDecisionResult(
            bool(approved), ml_signal.action, market, 
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
        self.signal_filter = SignalFilter(self.settings)

    def execute(self, db: Session, decision: TradeDecisionResult, available_balance: float | None = None) -> None:
        if not decision.approved:
            return
        
        # 투자 금액 계산: 가용 자금 * 투자 비율
        if available_balance is None:
            # [Fix] 가용 잔고가 전달되지 않은 경우 실시간 조회 시도
            try:
                import pyupbit
                u = pyupbit.Upbit(self.settings.upbit_access_key, self.settings.upbit_secret_key)
                bal = u.get_balance("KRW")
                if bal is not None:
                    available_balance = float(bal)
                else:
                    available_balance = self.settings.default_trade_amount
            except Exception:
                available_balance = self.settings.default_trade_amount
        
        trade_amount = available_balance * decision.investment_ratio
        
        # [Fix] 최소 주문 금액 보정 (Upbit 최소 5,000원)
        if trade_amount < 6000:
            trade_amount = 6000
        
        # 잔고가 부족한 경우 최대 가용 금액 사용
        if trade_amount > available_balance:
            trade_amount = available_balance * 0.995 # 수수료 고려
            
        if trade_amount < 5000:
            logger.warning(f"⚠️ 주문 금액 부족 (최소 5,000원): 산출금액 {trade_amount:,.0f}원 / 가용 {available_balance:,.0f}원")
            return

        # 실제 Upbit API 호출하여 거래 실행
        import pyupbit
        try:
            upbit = pyupbit.Upbit(self.settings.upbit_access_key, self.settings.upbit_secret_key)
            
            if decision.action == "BUY":
                # 매수: KRW로 코인 구매
                result = upbit.buy_market_order(decision.market, trade_amount)
                
                # 주문 성공 여부 확인 (result가 dict이고 uuid가 있어야 함)
                if result and isinstance(result, dict) and 'uuid' in result:
                    logger.info(f"✅ BUY 주문 성공: {decision.market}, {trade_amount:,.0f}원")
                    # 성공 시 신호 및 신뢰도 저장
                    self.signal_filter.set_last_signal(decision.market, "BUY", decision.confidence)
                    
                    # TradePosition 생성
                    try:
                        current_price = pyupbit.get_current_price(decision.market)
                        if current_price and isinstance(current_price, (int, float)):
                            current_price = float(current_price)
                            size = trade_amount / current_price
                            position = TradePosition(
                                market=decision.market,
                                size=size,
                                entry_price=current_price,
                                stop_loss=current_price * (1 - decision.max_loss_acceptable),
                                take_profit=current_price * (1 + decision.take_profit_target),
                                status="OPEN"
                            )
                            db.add(position)
                            db.commit()
                            logger.info(f"📝 포지션 생성: {decision.market} @ {current_price:,.0f}원")
                    except Exception as e:
                        logger.error(f"포지션 생성 실패: {e}")
                else:
                    logger.warning(f"⚠️ BUY 주문 실패: {decision.market} - {result}")

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
                    # 성공 시 신호 및 신뢰도 저장
                    self.signal_filter.set_last_signal(decision.market, "SELL", decision.confidence)
                    
                    # TradePosition 종료
                    try:
                        positions = db.query(TradePosition).filter(
                            TradePosition.market == decision.market,
                            TradePosition.status == "OPEN"
                        ).all()
                        for pos in positions:
                            pos.status = "CLOSED"
                        db.commit()
                        logger.info(f"📝 포지션 종료: {decision.market} ({len(positions)}건)")
                    except Exception as e:
                        logger.error(f"포지션 종료 실패: {e}")
                else:
                    logger.warning(f"⚠️ SELL 실패: {decision.market} 보유량 없음 (DB 동기화 진행)")
                    # 실제 보유량이 없는데 DB에 OPEN으로 남아있다면 강제 종료 (Sync fix)
                    try:
                        positions = db.query(TradePosition).filter(
                            TradePosition.market == decision.market,
                            TradePosition.status == "OPEN"
                        ).all()
                        if positions:
                            for pos in positions:
                                pos.status = "CLOSED"
                            db.commit()
                            logger.info(f"📝 유령 포지션 강제 종료: {decision.market} ({len(positions)}건)")
                    except Exception as e:
                        logger.error(f"유령 포지션 정리 실패: {e}")
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

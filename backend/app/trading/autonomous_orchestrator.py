from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Any

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


@dataclass
class CandidatePlan:
    market: str
    score: float
    regime: str
    confidence: float
    buy_probability: float
    sell_probability: float
    investment_ratio: float
    max_loss_acceptable: float
    take_profit_target: float
    rationale: str


class AutonomousStrategyOrchestrator:
    """
    장기적으로 수익이 날 가능성이 높은 코인을 사전에 선별하고,
    급등 추격(FOMO) 매수를 피하기 위한 자율 오케스트레이터.
    """

    def __init__(self, predictor: Any, verifier: Any, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.predictor = predictor
        self.verifier = verifier

    async def build_plan(
        self,
        markets: list[str],
        multi_tf_data_dict: dict[str, dict[str, list[dict[str, Any]]]],
        feature_map: dict[str, dict[str, Any]],
        account_info: dict[str, Any],
    ) -> dict[str, Any]:
        plans: list[CandidatePlan] = []
        regime_counts: dict[str, int] = {"TREND_UP": 0, "RANGE": 0, "RISK_OFF": 0}

        for market in markets:
            market_data = multi_tf_data_dict.get(market, {}).get("minute60", [])
            if len(market_data) < 80:
                continue

            features = self._extract_market_features(market_data)
            ml_signal = self.predictor.infer(feature_map.get(market, {"market": market}))

            regime = self._detect_regime(features, ml_signal)
            regime_counts[regime] = regime_counts.get(regime, 0) + 1

            base_score = self._score_candidate(features, ml_signal, regime)
            if base_score <= 0:
                continue

            investment_ratio = 0.08
            max_loss = 0.02
            take_profit = 0.045
            reasoning = "Rule-based prepositioning"

            try:
                llm_decision = await self.verifier.decide_investment_ratio(
                    ml_signal={
                        "buy_probability": float(ml_signal.buy_probability),
                        "sell_probability": float(ml_signal.sell_probability),
                        "confidence": float(max(ml_signal.buy_probability, ml_signal.sell_probability)),
                        "emergency_score": float(getattr(ml_signal, "emergency_score", 0.0)),
                    },
                    account_info={
                        **account_info,
                        "position_count": account_info.get("open_positions", 0),
                    },
                    market_info={
                        "volatility": features["volatility"],
                        "win_rate": _clamp(base_score, 0.0, 1.0),
                        "consecutive_losses": account_info.get("consecutive_losses", 0),
                    },
                )
                investment_ratio = _clamp(float(llm_decision.get("investment_ratio", investment_ratio)), 0.03, self.settings.max_investment_ratio)
                max_loss = _clamp(float(llm_decision.get("max_loss_acceptable", max_loss)), 0.01, 0.04)
                take_profit = _clamp(float(llm_decision.get("take_profit_target", take_profit)), 0.02, 0.08)
                reasoning = str(llm_decision.get("reasoning", reasoning))
            except Exception as e:
                logger.warning("LLM sizing fallback for %s: %s", market, e)

            score = base_score * (0.65 + investment_ratio)
            plans.append(
                CandidatePlan(
                    market=market,
                    score=score,
                    regime=regime,
                    confidence=float(max(ml_signal.buy_probability, ml_signal.sell_probability)),
                    buy_probability=float(ml_signal.buy_probability),
                    sell_probability=float(ml_signal.sell_probability),
                    investment_ratio=investment_ratio,
                    max_loss_acceptable=max_loss,
                    take_profit_target=take_profit,
                    rationale=reasoning,
                )
            )

        plans.sort(key=lambda x: x.score, reverse=True)

        selected = [
            p.market
            for p in plans
            if p.buy_probability > p.sell_probability
            and p.confidence >= self.settings.min_confidence_for_trade
            and p.regime != "RISK_OFF"
        ]

        status = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "AUTONOMOUS_PREPOSITIONING",
            "selection_logic": "LLM+ML regime scoring (no manual mode)",
            "regime_counts": regime_counts,
            "selected_markets": selected,
            "candidates": [
                {
                    "market": p.market,
                    "score": round(p.score, 4),
                    "regime": p.regime,
                    "confidence": round(p.confidence, 4),
                    "buy_probability": round(p.buy_probability, 4),
                    "sell_probability": round(p.sell_probability, 4),
                    "investment_ratio": round(p.investment_ratio, 4),
                    "max_loss_acceptable": round(p.max_loss_acceptable, 4),
                    "take_profit_target": round(p.take_profit_target, 4),
                    "rationale": p.rationale,
                }
                for p in plans[:10]
            ],
        }
        return status

    def _extract_market_features(self, market_data: list[dict[str, Any]]) -> dict[str, float]:
        closes = [float(c.get("close", 0.0)) for c in market_data if c.get("close") is not None]
        highs = [float(c.get("high", 0.0)) for c in market_data if c.get("high") is not None]
        lows = [float(c.get("low", 0.0)) for c in market_data if c.get("low") is not None]
        volumes = [float(c.get("volume", 0.0)) for c in market_data if c.get("volume") is not None]

        if len(closes) < 30:
            return {
                "trend_strength": 0.0,
                "momentum": 0.0,
                "volatility": 1.0,
                "pullback": 0.0,
                "volume_accel": 0.0,
            }

        now_price = closes[-1]
        ma_20 = mean(closes[-20:]) if len(closes) >= 20 else now_price
        ma_50 = mean(closes[-50:]) if len(closes) >= 50 else ma_20
        trend_strength = _clamp((ma_20 - ma_50) / ma_50 if ma_50 > 0 else 0.0, -0.1, 0.1)

        ref = closes[-6] if len(closes) >= 6 else closes[0]
        momentum = _clamp((now_price - ref) / ref if ref > 0 else 0.0, -0.12, 0.12)

        returns = []
        for i in range(1, min(21, len(closes))):
            prev = closes[-(i + 1)]
            cur = closes[-i]
            returns.append((cur - prev) / prev if prev > 0 else 0.0)
        volatility = float((sum(r * r for r in returns) / len(returns)) ** 0.5) if returns else 0.0

        window = closes[-20:] if len(closes) >= 20 else closes
        peak = max(window) if window else now_price
        pullback = _clamp((peak - now_price) / peak if peak > 0 else 0.0, 0.0, 0.08)

        vol_now = volumes[-1] if volumes else 0.0
        vol_base = mean(volumes[-20:]) if len(volumes) >= 20 else (mean(volumes) if volumes else 0.0)
        volume_accel = _clamp((vol_now / vol_base) - 1.0 if vol_base > 0 else 0.0, -0.7, 2.0)

        # 단순 ATR 대체 지표
        tr_values = []
        for i in range(max(1, len(highs) - 15), len(highs)):
            h = highs[i]
            l = lows[i]
            c_prev = closes[i - 1] if i - 1 >= 0 else closes[i]
            tr_values.append(max(h - l, abs(h - c_prev), abs(l - c_prev)))
        atr_ratio = (mean(tr_values) / now_price) if tr_values and now_price > 0 else 0.0

        return {
            "trend_strength": trend_strength,
            "momentum": momentum,
            "volatility": volatility,
            "pullback": pullback,
            "volume_accel": volume_accel,
            "atr_ratio": atr_ratio,
        }

    def _detect_regime(self, features: dict[str, float], ml_signal: Any) -> str:
        if features["volatility"] > 0.03 or features["atr_ratio"] > 0.035:
            return "RISK_OFF"
        if features["trend_strength"] > 0.0 and ml_signal.buy_probability >= ml_signal.sell_probability:
            return "TREND_UP"
        return "RANGE"

    def _score_candidate(self, features: dict[str, float], ml_signal: Any, regime: str) -> float:
        trend = _clamp((features["trend_strength"] + 0.1) / 0.2, 0.0, 1.0)
        momentum = _clamp((features["momentum"] + 0.12) / 0.24, 0.0, 1.0)
        pullback = _clamp(features["pullback"] / 0.08, 0.0, 1.0)
        vol_accel = _clamp((features["volume_accel"] + 0.7) / 2.7, 0.0, 1.0)
        ml_edge = _clamp(float(ml_signal.buy_probability - ml_signal.sell_probability) + 0.5, 0.0, 1.0)
        risk_penalty = _clamp(features["volatility"] / 0.05, 0.0, 1.0)

        # 사전 포지셔닝: 우상향 + 눌림 + 거래량 회복 + ML edge 조합
        score = (
            0.30 * trend
            + 0.20 * momentum
            + 0.20 * pullback
            + 0.15 * vol_accel
            + 0.25 * ml_edge
            - 0.25 * risk_penalty
        )

        if regime == "RISK_OFF":
            score *= 0.3
        elif regime == "TREND_UP":
            score *= 1.08

        return _clamp(score, 0.0, 1.5)
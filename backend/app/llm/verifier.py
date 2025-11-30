from __future__ import annotations

import json
import httpx
from typing import Dict, Any

from app.core.config import Settings, get_settings
from app.llm.groq_client import GroqClient
from app.llm.ollama_client import OllamaClient


class DualLLMVerifier:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.groq = GroqClient(self.settings)
        self.ollama = OllamaClient(self.settings)

    async def verify(self, summary: str) -> tuple[bool, bool]:
        return await self.groq.safe_verify(summary), await self.ollama.safe_verify(summary)

    async def approve(self, summary: str) -> bool:
        groq_ok, ollama_ok = await self.verify(summary)
        return groq_ok and ollama_ok
    
    async def decide_investment_ratio(
        self,
        ml_signal: Dict[str, Any],
        account_info: Dict[str, Any],
        market_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        LLM을 사용하여 투자 비율을 결정합니다.
        
        Args:
            ml_signal: ML 모델의 예측 결과
            account_info: 계좌 정보 (원금, 가용자금, 포지션 등)
            market_info: 시장 정보 (변동성, 히스토리 등)
            
        Returns:
            {
                "investment_ratio": float,  # 0.0 ~ 1.0
                "reasoning": str,
                "max_loss_acceptable": float,
                "take_profit_target": float
            }
        """
        prompt = self._build_investment_prompt(ml_signal, account_info, market_info)
        
        # Groq로 빠른 결정
        payload = {
            "model": self.settings.groq_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "당신은 전문 암호화폐 트레이더입니다. "
                        "ML 시그널과 계좌 정보, 시장 상황을 분석하여 "
                        "최적의 투자 비율을 결정해야 합니다. "
                        "반드시 JSON 형식으로만 응답하세요."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 500
        }
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self.groq.base_url,
                    headers=self.groq.headers,
                    json=payload
                )
                resp.raise_for_status()
                data = resp.json()
            
            content = data["choices"][0]["message"]["content"]
            # JSON 파싱
            result = json.loads(content)
            
            # 검증
            if not (0.0 <= result.get("investment_ratio", 0) <= 1.0):
                raise ValueError("Invalid investment_ratio")
            
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # 레이트 리미트 시 신뢰도 기반 폴백
                confidence = ml_signal.get('confidence', 0)
                if confidence >= 0.8:
                    ratio = 0.3
                elif confidence >= 0.65:
                    ratio = 0.2
                elif confidence >= 0.55:
                    ratio = 0.1
                else:
                    ratio = 0.05
                return {
                    "investment_ratio": ratio,
                    "reasoning": f"Groq API 레이트 리미트, 신뢰도 기반 {ratio*100:.0f}% 투자",
                    "max_loss_acceptable": 0.03,
                    "take_profit_target": 0.05
                }
            raise
        except (json.JSONDecodeError, ValueError, KeyError, Exception) as e:
            # 기본값 반환 (보수적)
            return {
                "investment_ratio": 0.1,
                "reasoning": f"LLM 응답 파싱 실패, 보수적 10% 투자. Error: {str(e)}",
                "max_loss_acceptable": 0.03,
                "take_profit_target": 0.05
            }
    
    def _build_investment_prompt(
        self,
        ml_signal: Dict[str, Any],
        account_info: Dict[str, Any],
        market_info: Dict[str, Any]
    ) -> str:
        """투자 비율 결정을 위한 프롬프트 생성"""
        return f"""
다음 정보를 분석하여 투자 비율을 결정해주세요:

### ML 시그널:
- 매수 확률: {ml_signal.get('buy_probability', 0):.2%}
- 매도 확률: {ml_signal.get('sell_probability', 0):.2%}
- 신뢰도: {ml_signal.get('confidence', 0):.2%}
- 긴급 점수: {ml_signal.get('emergency_score', 0):.2f}

### 계좌 정보:
- 총 원금: {account_info.get('principal', 0):,.0f}원
- 가용 자금: {account_info.get('available_balance', 0):,.0f}원
- 현재 포지션 수: {account_info.get('position_count', 0)}개
- 평균 수익률: {account_info.get('avg_return', 0):.2%}

### 시장 정보:
- 변동성 (ATR): {market_info.get('volatility', 0):.2f}
- 최근 승률: {market_info.get('win_rate', 0):.2%}
- 연속 손실: {market_info.get('consecutive_losses', 0)}회

### 결정 기준:
1. ML 신호 강도와 신뢰도가 높으면 (>0.8) → 높은 비율 (50~100%)
2. 중간 신뢰도 (0.6~0.8) → 중간 비율 (20~50%)
3. 낮은 신뢰도 (<0.6) → 낮은 비율 (5~20%)
4. 변동성이 높으면 → 비율 감소
5. 연속 손실 시 → 비율 감소 (5~10%)
6. 연속 수익 시 → 비율 점진 증가

다음 JSON 형식으로만 응답하세요 (코멘트 없이):
{{
  "investment_ratio": 0.15,
  "reasoning": "높은 신뢰도와 낮은 변동성으로 중간 수준 투자 권장",
  "max_loss_acceptable": 0.03,
  "take_profit_target": 0.05
}}
"""

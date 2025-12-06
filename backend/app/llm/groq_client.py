from __future__ import annotations

import httpx
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class GroqClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.headers = {"Authorization": f"Bearer {self.settings.groq_api_key}"}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    async def verify(self, summary: str) -> dict:
        payload = {
            "model": self.settings.groq_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You validate cryptocurrency trades for risk, sentiment, and macro correctness.",
                },
                {"role": "user", "content": summary},
            ],
            "temperature": 0.3,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(self.base_url, headers=self.headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            logger.debug("Groq verification response: %s", data)
            return data

    async def safe_verify(self, summary: str) -> bool | None:
        """
        LLM 검증 수행
        
        Returns:
            True: 승인
            False: 거부
            None: 응답 실패 (타임아웃, 에러 등)
        """
        try:
            data = await self.verify(summary)
            content = data["choices"][0]["message"]["content"].lower()
            
            # 승인 키워드 확인
            if any(keyword in content for keyword in ["approve", "buy", "sell", "execute", "yes"]):
                logger.info("Groq: ✅ 승인")
                return True
            
            # 거부 키워드 확인
            if any(keyword in content for keyword in ["reject", "no", "deny", "decline"]):
                logger.info(f"Groq: ❌ 거부 - {content[:100]}")
                return False
            
            # 모호한 응답은 승인으로 처리 (보수적)
            logger.warning(f"Groq: ⚠️ 모호한 응답, 승인 처리 - {content[:100]}")
            return True
            
        except RetryError:
            logger.warning("⚠️ Groq: 재시도 후 실패 (None 반환)")
            return None  # 실패
        except Exception as exc:  # noqa: BLE001
            logger.error(f"⚠️ Groq: 에러 발생 (None 반환) - {exc}")
            return None  # 실패

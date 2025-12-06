from __future__ import annotations

import httpx
from tenacity import RetryError, retry, stop_after_attempt, wait_fixed

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OllamaClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.base_url = f"{self.settings.ollama_base_url}/api/chat"

    async def verify(self, summary: str) -> dict:
        payload = {
            "model": self.settings.ollama_model,
            "messages": [
                {"role": "system", "content": "You are a cautious trading auditor. Answer with 'approve' or 'reject' only."},
                {"role": "user", "content": f"{summary}\n\nShould this trade be executed? Answer with one word: approve or reject."},
            ],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 5,  # 더 짧은 답변 (10 → 5)
            }
        }
        timeout = getattr(self.settings, 'ollama_timeout', 5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            logger.info(f"Sending request to {self.base_url} with model {self.settings.ollama_model}")
            resp = await client.post(self.base_url, json=payload)
            resp.raise_for_status()
            return resp.json()

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
            content = data.get("message", {}).get("content", "").lower()
            logger.info(f"Ollama response: {content[:100]}")
            
            # 승인 키워드 확인
            if any(word in content for word in ["approve", "yes", "proceed", "buy", "execute"]):
                logger.info("Ollama: ✅ 승인")
                return True
            
            # 거부 키워드 확인
            if any(word in content for word in ["reject", "no", "deny", "decline"]):
                logger.info(f"Ollama: ❌ 거부")
                return False
            
            # 모호한 응답은 승인으로 처리
            logger.warning(f"Ollama: ⚠️ 모호한 응답, 승인 처리")
            return True
            
        except Exception as exc:
            logger.error(f"⚠️ Ollama: 에러 발생 (None 반환) - {type(exc).__name__}: {exc}")
            return None  # 실패

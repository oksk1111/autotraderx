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
                "num_predict": 10,  # 짧은 답변만 요청
            }
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            logger.info(f"Sending request to {self.base_url} with model {self.settings.ollama_model}")
            resp = await client.post(self.base_url, json=payload)
            resp.raise_for_status()
            return resp.json()

    async def safe_verify(self, summary: str) -> bool:
        try:
            data = await self.verify(summary)
            content = data.get("message", {}).get("content", "").lower()
            logger.info(f"Ollama response: {content[:100]}")
            # approve, yes, proceed, buy 등의 긍정적 키워드 확인
            return any(word in content for word in ["approve", "yes", "proceed", "buy", "execute"])
        except Exception as exc:
            logger.error(f"Ollama verification error: {type(exc).__name__}: {exc}")
            return False

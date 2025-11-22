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

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
    async def verify(self, summary: str) -> dict:
        payload = {
            "model": self.settings.ollama_model,
            "messages": [
                {"role": "system", "content": "You are a cautious trading auditor."},
                {"role": "user", "content": summary},
            ],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(self.base_url, json=payload)
            resp.raise_for_status()
            return resp.json()

    async def safe_verify(self, summary: str) -> bool:
        try:
            data = await self.verify(summary)
            content = data.get("message", {}).get("content", "").lower()
            return any(word in content for word in ["approve", "agree", "proceed"])
        except RetryError:
            logger.warning("Ollama verification failed after retries")
            return False
        except Exception as exc:  # noqa: BLE001
            logger.exception("Ollama verification error: %s", exc)
            return False

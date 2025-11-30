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

    async def safe_verify(self, summary: str) -> bool:
        try:
            data = await self.verify(summary)
            content = data["choices"][0]["message"]["content"].lower()
            return any(keyword in content for keyword in ["approve", "buy", "sell", "execute"])
        except RetryError:
            logger.warning("Groq verification failed after retries")
            return False
        except Exception as exc:  # noqa: BLE001
            logger.exception("Groq verification error: %s", exc)
            return False

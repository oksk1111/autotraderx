from __future__ import annotations

import json

import httpx
from slack_sdk.webhook import WebhookClient

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Notifier:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    async def send(self, title: str, message: str) -> None:
        await self._slack(title, message)
        await self._telegram(f"{title}\n{message}")

    async def _slack(self, title: str, message: str) -> None:
        if not self.settings.slack_webhook_url:
            return
        webhook = WebhookClient(self.settings.slack_webhook_url)
        webhook.send(text=f"*{title}*\n{message}")

    async def _telegram(self, message: str) -> None:
        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            return
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        payload = {"chat_id": self.settings.telegram_chat_id, "text": message}
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload)

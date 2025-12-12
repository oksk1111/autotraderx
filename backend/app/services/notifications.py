from __future__ import annotations

import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from enum import Enum
from typing import List, Optional

import httpx
from slack_sdk.webhook import WebhookClient

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class AlertLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Notifier:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.alert_level = self._parse_alert_level(self.settings.alert_level)

    def _parse_alert_level(self, level_str: str) -> AlertLevel:
        try:
            return AlertLevel(level_str.upper())
        except ValueError:
            return AlertLevel.WARNING

    def _should_send(self, level: AlertLevel) -> bool:
        levels = [AlertLevel.INFO, AlertLevel.WARNING, AlertLevel.ERROR]
        try:
            config_idx = levels.index(self.alert_level)
            msg_idx = levels.index(level)
            return msg_idx >= config_idx
        except ValueError:
            return True

    async def send(self, title: str, message: str, level: str = "INFO", email_recipients: List[str] | None = None) -> None:
        """
        알림 전송 메인 함수
        
        Args:
            title: 알림 제목
            message: 알림 내용
            level: 알림 중요도 (INFO, WARNING, ERROR)
            email_recipients: 이메일 수신자 목록 (None일 경우 이메일 전송 안함)
        """
        try:
            msg_level = AlertLevel(level.upper())
        except ValueError:
            msg_level = AlertLevel.INFO

        # 레벨 체크 (설정된 레벨보다 낮으면 전송 안 함)
        if not self._should_send(msg_level):
            logger.debug(f"알림 스킵 ({level} < {self.alert_level}): {title}")
            return

        # 이모지 추가
        emoji = "ℹ️"
        if msg_level == AlertLevel.WARNING:
            emoji = "⚠️"
        elif msg_level == AlertLevel.ERROR:
            emoji = "🚨"
            
        formatted_title = f"{emoji} {title}"

        # 각 채널로 전송
        await self._slack(formatted_title, message)
        await self._telegram(f"{formatted_title}\n\n{message}")
        
        if email_recipients:
            await self._email(formatted_title, message, email_recipients)

    async def _slack(self, title: str, message: str) -> None:
        if not self.settings.slack_webhook_url:
            return
        try:
            webhook = WebhookClient(self.settings.slack_webhook_url)
            webhook.send(text=f"*{title}*\n{message}")
        except Exception as e:
            logger.error(f"Slack 전송 실패: {e}")

    async def _telegram(self, message: str) -> None:
        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            return
        
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        payload = {"chat_id": self.settings.telegram_chat_id, "text": message}
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(url, json=payload)
        except Exception as e:
            logger.error(f"Telegram 전송 실패: {e}")

    async def _email(self, title: str, message: str, recipients: List[str]) -> None:
        if not self.settings.email_user or not self.settings.email_password:
            return

        try:
            # 동기 함수지만 짧은 작업이라 여기서 처리 (필요시 비동기 래퍼 사용)
            with smtplib.SMTP(self.settings.email_host, self.settings.email_port) as server:
                server.starttls()
                server.login(self.settings.email_user, self.settings.email_password)
                
                for recipient in recipients:
                    msg = MIMEMultipart()
                    msg['From'] = self.settings.email_user
                    msg['To'] = recipient
                    msg['Subject'] = f"[AutoTraderX] {title}"
                    msg.attach(MIMEText(message, 'plain'))
                    
                    server.send_message(msg)
                    logger.info(f"Email sent to {recipient}")
                
        except Exception as e:
            logger.error(f"Email 전송 실패: {e}")

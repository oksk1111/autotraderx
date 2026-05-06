#!/usr/bin/env python3
"""Validate surge alert configuration and notifier readiness."""

from __future__ import annotations

from app.core.config import get_settings
from app.services.notifications import Notifier


def main() -> int:
    settings = get_settings()
    notifier = Notifier(settings)

    print("[surge-alert] enabled:", settings.surge_alert_enabled)
    print("[surge-alert] threshold_percent:", settings.surge_alert_threshold_percent)
    print("[surge-alert] window_seconds:", settings.surge_alert_window_seconds)
    print("[surge-alert] cooldown_seconds:", settings.surge_alert_cooldown_seconds)
    print("[surge-alert] min_volume_24h:", int(settings.surge_alert_min_volume_24h))

    has_slack = bool(settings.slack_webhook_url)
    has_telegram = bool(settings.telegram_bot_token and settings.telegram_chat_id)

    print("[notifier] slack_configured:", has_slack)
    print("[notifier] telegram_configured:", has_telegram)
    print("[notifier] alert_level:", notifier.alert_level.value)

    if not settings.surge_alert_enabled:
        print("[warn] surge alerts are disabled")
    if not has_slack and not has_telegram:
        print("[warn] no realtime channel configured (Slack/Telegram)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

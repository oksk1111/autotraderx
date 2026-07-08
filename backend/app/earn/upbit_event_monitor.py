"""Upbit Event Monitor — detects earning opportunities from Upbit announcements.

Monitors:
  1. Quiz events (1,000~5,000 KRW reward per correct answer)
  2. New coin listings (early entry opportunity)
  3. Airdrop/staking promotions
  4. Trading competitions with prizes
  5. Sign-up/deposit reward campaigns

Uses the public Upbit notice API — no authentication required.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import re
from typing import Dict, List, Optional, Set

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from .base import ActionType, BaseEarner, EarnEvent, EarnSource, EventStatus

logger = get_logger(__name__)

# Upbit public APIs
UPBIT_NOTICE_URL = "https://api-manager.upbit.com/api/v1/notices"
UPBIT_DISCLOSURE_URL = "https://api-manager.upbit.com/api/v1/disclosure"

# Keywords for detecting reward events
REWARD_KEYWORDS = [
    "퀴즈", "이벤트", "에어드롭", "리워드", "보상",
    "경품", "상금", "무료", "증정", "선착순",
    "캠페인", "프로모션", "지급", "혜택",
]
LISTING_KEYWORDS = ["신규", "상장", "마켓 추가", "거래 지원", "디지털 자산 추가"]
STAKING_KEYWORDS = ["스테이킹", "락업", "이자", "수익률"]

# Keyword weights for value estimation
VALUE_HINTS = {
    "퀴즈": 3000,
    "에어드롭": 10000,
    "선착순": 5000,
    "이벤트": 2000,
    "스테이킹": 5000,
    "캠페인": 3000,
}


class UpbitEventMonitor(BaseEarner):
    """Monitors Upbit announcements for earning opportunities."""

    name = "upbit_event"

    def __init__(self):
        self.s = get_settings()
        self._seen_ids: Set[str] = set()
        self._client: Optional[httpx.AsyncClient] = None
        self._last_scan: Optional[dt.datetime] = None

    def is_enabled(self) -> bool:
        return self.s.earn_upbit_events_enabled

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=15.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; AutoTraderX/1.0)",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def scan(self) -> List[EarnEvent]:
        """Fetch Upbit notices and detect reward/listing events."""
        events: List[EarnEvent] = []

        try:
            notices = await self._fetch_notices()
            for notice in notices:
                event = self._classify_notice(notice)
                if event is not None:
                    events.append(event)
        except Exception as e:
            logger.warning("[upbit_event] scan failed: %s", e)

        self._last_scan = dt.datetime.utcnow()

        if events:
            logger.info("[upbit_event] found %d new opportunities", len(events))

        return events

    async def _fetch_notices(self) -> List[Dict]:
        """Fetch recent notices from Upbit API."""
        client = await self._get_client()

        all_notices: List[Dict] = []

        # Fetch general notices
        try:
            resp = await client.get(
                UPBIT_NOTICE_URL,
                params={"page": 1, "per_page": 20, "thread_name": "general"},
            )
            if resp.status_code == 200:
                data = resp.json()
                notices = data.get("data", {}).get("list", [])
                if isinstance(notices, list):
                    all_notices.extend(notices)
        except Exception as e:
            logger.debug("[upbit_event] general notices fetch error: %s", e)

        # Fetch event notices
        try:
            resp = await client.get(
                UPBIT_NOTICE_URL,
                params={"page": 1, "per_page": 20, "thread_name": "event"},
            )
            if resp.status_code == 200:
                data = resp.json()
                notices = data.get("data", {}).get("list", [])
                if isinstance(notices, list):
                    all_notices.extend(notices)
        except Exception as e:
            logger.debug("[upbit_event] event notices fetch error: %s", e)

        return all_notices

    def _classify_notice(self, notice: Dict) -> Optional[EarnEvent]:
        """Classify a notice and return an EarnEvent if it's an opportunity."""
        notice_id = str(notice.get("id", ""))
        title = notice.get("title", "")
        created_at = notice.get("created_at", "")

        # Generate unique hash for dedup
        event_hash = hashlib.md5(f"{notice_id}:{title}".encode()).hexdigest()
        if event_hash in self._seen_ids:
            return None

        # Check if this is an earning opportunity
        title_lower = title.lower()
        full_text = title  # We only have title from the list API

        # Detect reward events (quiz, airdrop, campaign)
        is_reward = any(kw in full_text for kw in REWARD_KEYWORDS)
        is_listing = any(kw in full_text for kw in LISTING_KEYWORDS)
        is_staking = any(kw in full_text for kw in STAKING_KEYWORDS)

        if not (is_reward or is_listing or is_staking):
            return None

        # Mark as seen
        self._seen_ids.add(event_hash)
        # Keep seen set bounded
        if len(self._seen_ids) > 1000:
            self._seen_ids = set(list(self._seen_ids)[-500:])

        # Determine action type and estimate value
        action_type = ActionType.NOTIFICATION
        estimated_value = 0.0

        if is_reward:
            action_type = ActionType.MANUAL
            # Estimate value from keywords
            for kw, val in VALUE_HINTS.items():
                if kw in full_text:
                    estimated_value = max(estimated_value, val)
            if estimated_value == 0:
                estimated_value = 2000.0  # Default estimate

        elif is_listing:
            action_type = ActionType.NOTIFICATION
            estimated_value = 0.0  # Trading opportunity, not direct reward
            # Extract coin name if possible
            coin_match = re.search(r"([A-Z]{2,10})", title)
            if coin_match:
                notice["detected_coin"] = coin_match.group(1)

        elif is_staking:
            action_type = ActionType.MANUAL
            estimated_value = 5000.0

        # Build event URL
        action_url = f"https://upbit.com/service_center/notice?id={notice_id}"

        # Parse expiry if available
        expires_at = None

        event = EarnEvent(
            source=EarnSource.UPBIT_EVENT,
            title=title,
            description=self._build_description(notice, is_reward, is_listing, is_staking),
            estimated_value_krw=estimated_value,
            action_url=action_url,
            action_type=action_type,
            status=EventStatus.DISCOVERED,
            expires_at=expires_at,
            metadata={
                "notice_id": notice_id,
                "created_at": created_at,
                "is_reward": is_reward,
                "is_listing": is_listing,
                "is_staking": is_staking,
                "detected_coin": notice.get("detected_coin", ""),
            },
        )

        return event

    def _build_description(
        self, notice: Dict, is_reward: bool, is_listing: bool, is_staking: bool
    ) -> str:
        """Build a human-readable description for the event."""
        parts = []
        title = notice.get("title", "")

        if is_reward:
            parts.append(f"🎁 업비트 보상 이벤트 감지: {title}")
            parts.append("퀴즈/이벤트 참여로 KRW 보상을 받을 수 있습니다.")
        elif is_listing:
            coin = notice.get("detected_coin", "??")
            parts.append(f"🆕 신규 상장 감지: {title}")
            parts.append(f"코인 {coin} 상장 — 상장 직후 급등 가능성 있음.")
        elif is_staking:
            parts.append(f"💎 스테이킹 기회: {title}")
            parts.append("보유만으로 이자 수익을 받을 수 있습니다.")

        return " | ".join(parts)

    async def claim(self, event: EarnEvent) -> bool:
        """Most Upbit events require manual participation (quiz answers, etc.).
        We can only notify; actual claiming is manual."""
        # Upbit events typically can't be auto-claimed — they require
        # human interaction (answering quizzes, clicking buttons, etc.)
        logger.info("[upbit_event] Event requires manual action: %s", event.title)
        return False

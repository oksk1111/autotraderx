"""Faucet Claimer — collects small crypto amounts from legitimate faucets.

Only targets faucets with:
  - API-based claims (no CAPTCHA)
  - Upbit-depositable coins (BTC, ETH, XRP, etc.)
  - Verified legitimate operation

This is a supplementary income source (~50-200 KRW/day) that compounds over time.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from .base import ActionType, BaseEarner, EarnEvent, EarnSource, EventStatus

logger = get_logger(__name__)


@dataclass
class FaucetSite:
    """Configuration for a single faucet."""

    name: str
    url: str
    claim_url: str
    currency: str
    claim_interval_sec: int  # Minimum seconds between claims
    min_withdraw: float  # Minimum balance to withdraw
    estimated_claim_krw: float  # Estimated KRW per claim
    active: bool = True

    # Runtime state
    last_claim_unix: float = 0.0
    total_claimed: float = 0.0
    consecutive_failures: int = 0

    @property
    def can_claim(self) -> bool:
        if not self.active:
            return False
        if self.consecutive_failures >= 5:
            return False  # Too many failures, disable
        elapsed = time.time() - self.last_claim_unix
        return elapsed >= self.claim_interval_sec


# Known API-based faucets (no CAPTCHA required)
# NOTE: Faucet availability changes frequently — these should be verified periodically
DEFAULT_FAUCETS: List[FaucetSite] = [
    FaucetSite(
        name="FaucetCrypto",
        url="https://www.faucetcrypto.com",
        claim_url="https://www.faucetcrypto.com/api/claim",
        currency="BTC",
        claim_interval_sec=3600,  # 1 hour
        min_withdraw=0.0001,
        estimated_claim_krw=10.0,
    ),
    # Additional faucets can be configured via environment
]


class FaucetClaimer(BaseEarner):
    """Automatically claims from legitimate crypto faucets."""

    name = "faucet_claimer"

    def __init__(self):
        self.s = get_settings()
        self.faucets: List[FaucetSite] = list(DEFAULT_FAUCETS)
        self._client: Optional[httpx.AsyncClient] = None
        self._total_earned_krw: float = 0.0

    def is_enabled(self) -> bool:
        return self.s.earn_faucets_enabled

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=15.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def scan(self) -> List[EarnEvent]:
        """Check which faucets are ready to claim."""
        events: List[EarnEvent] = []

        for faucet in self.faucets:
            if faucet.can_claim:
                events.append(EarnEvent(
                    source=EarnSource.FAUCET,
                    title=f"Faucet ready: {faucet.name} ({faucet.currency})",
                    description=(
                        f"{faucet.name}에서 {faucet.currency} 수집 가능. "
                        f"예상 수익: ~{faucet.estimated_claim_krw:.0f} KRW"
                    ),
                    estimated_value_krw=faucet.estimated_claim_krw,
                    action_url=faucet.url,
                    action_type=ActionType.AUTO_CLAIM,
                    status=EventStatus.DISCOVERED,
                    metadata={"faucet_name": faucet.name, "currency": faucet.currency},
                ))

        return events

    async def claim(self, event: EarnEvent) -> bool:
        """Attempt to claim from a faucet."""
        faucet_name = event.metadata.get("faucet_name", "")
        faucet = next((f for f in self.faucets if f.name == faucet_name), None)

        if faucet is None:
            return False

        try:
            success = await self._claim_faucet(faucet)
            if success:
                faucet.last_claim_unix = time.time()
                faucet.total_claimed += 1
                faucet.consecutive_failures = 0
                self._total_earned_krw += faucet.estimated_claim_krw
                logger.info(
                    "[faucet] claimed from %s (%s), total: %.0f KRW",
                    faucet.name, faucet.currency, self._total_earned_krw,
                )
                return True
            else:
                faucet.consecutive_failures += 1
                return False
        except Exception as e:
            faucet.consecutive_failures += 1
            logger.debug("[faucet] claim error %s: %s", faucet.name, e)
            return False

    async def _claim_faucet(self, faucet: FaucetSite) -> bool:
        """Execute the actual claim request to a faucet."""
        client = await self._get_client()

        try:
            # Generic API claim attempt
            resp = await client.post(
                faucet.claim_url,
                json={"currency": faucet.currency},
            )

            if resp.status_code == 200:
                data = resp.json()
                # Check for success indicators
                if data.get("success") or data.get("status") == "ok":
                    return True

            # Rate limited or unavailable
            if resp.status_code in (429, 503):
                faucet.claim_interval_sec = int(faucet.claim_interval_sec * 1.5)
                logger.debug("[faucet] %s rate limited, backing off", faucet.name)

            return False

        except httpx.TimeoutException:
            return False
        except Exception as e:
            logger.debug("[faucet] %s request error: %s", faucet.name, e)
            return False

    def get_stats(self) -> Dict:
        """Return faucet claiming statistics."""
        return {
            "total_earned_krw": self._total_earned_krw,
            "active_faucets": sum(1 for f in self.faucets if f.active),
            "faucets": [
                {
                    "name": f.name,
                    "currency": f.currency,
                    "active": f.active,
                    "total_claims": f.total_claimed,
                    "can_claim": f.can_claim,
                    "failures": f.consecutive_failures,
                }
                for f in self.faucets
            ],
        }

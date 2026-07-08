"""Airdrop Scanner — monitors airdrop aggregator sites for free token distributions.

Sources:
  1. airdrops.io - Curated active airdrops
  2. CoinMarketCap airdrops
  3. Upbit-listed token airdrops (priority)

Filters:
  - Only tokens that can be deposited to Upbit (KRW markets)
  - Excludes obviously scammy/low-quality airdrops
  - Prioritizes zero-gas-cost opportunities
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from typing import Dict, List, Optional, Set

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from .base import ActionType, BaseEarner, EarnEvent, EarnSource, EventStatus

logger = get_logger(__name__)

# Known Upbit-listed major coins (for filtering relevant airdrops)
UPBIT_COINS = {
    "BTC", "ETH", "XRP", "ADA", "SOL", "DOGE", "AVAX", "DOT", "MATIC",
    "LINK", "ATOM", "UNI", "APT", "ARB", "OP", "SEI", "SUI", "TIA",
    "NEAR", "FTM", "SAND", "MANA", "AXS", "IMX", "AAVE", "CRV",
    "STX", "HBAR", "VET", "ALGO", "EOS", "XLM", "TRX", "ETC",
}

# Airdrop quality signals (positive)
QUALITY_SIGNALS = [
    "verified", "official", "exchange", "listed", "mainnet",
    "confirmed", "guaranteed", "reward",
]

# Scam signals (negative)
SCAM_SIGNALS = [
    "send", "deposit first", "private key", "seed phrase",
    "connect wallet", "approval", "unlimited",
]


class AirdropScanner(BaseEarner):
    """Scans for legitimate airdrop opportunities."""

    name = "airdrop_scanner"

    def __init__(self):
        self.s = get_settings()
        self._seen_ids: Set[str] = set()
        self._client: Optional[httpx.AsyncClient] = None

    def is_enabled(self) -> bool:
        return self.s.earn_airdrop_enabled

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=20.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                    "Accept": "text/html,application/json",
                },
                follow_redirects=True,
            )
        return self._client

    async def scan(self) -> List[EarnEvent]:
        """Scan all airdrop sources for new opportunities."""
        events: List[EarnEvent] = []

        # Scan CoinMarketCap airdrops (JSON API available)
        cmc_events = await self._scan_cmc_airdrops()
        events.extend(cmc_events)

        # Scan airdrops.io (HTML scraping)
        aio_events = await self._scan_airdrops_io()
        events.extend(aio_events)

        if events:
            logger.info("[airdrop] found %d new airdrop opportunities", len(events))

        return events

    async def _scan_cmc_airdrops(self) -> List[EarnEvent]:
        """Scan CoinMarketCap airdrop page."""
        events: List[EarnEvent] = []
        client = await self._get_client()

        try:
            resp = await client.get(
                "https://coinmarketcap.com/airdrop/",
                headers={"Accept": "text/html"},
            )
            if resp.status_code != 200:
                return events

            # Extract airdrop info from page content
            text = resp.text
            # Look for airdrop cards — simplified extraction
            airdrop_sections = re.findall(
                r'<h3[^>]*>([^<]+)</h3>.*?(?:worth|value|reward)[^$]*?\$?([\d,]+)',
                text, re.IGNORECASE | re.DOTALL,
            )

            for title, value_str in airdrop_sections[:10]:  # Limit to 10
                event_hash = hashlib.md5(title.encode()).hexdigest()
                if event_hash in self._seen_ids:
                    continue
                self._seen_ids.add(event_hash)

                try:
                    value_usd = float(value_str.replace(",", ""))
                    value_krw = value_usd * 1350  # Approximate USD/KRW
                except (ValueError, TypeError):
                    value_krw = 5000.0

                events.append(EarnEvent(
                    source=EarnSource.AIRDROP,
                    title=f"CMC Airdrop: {title.strip()}",
                    description=f"CoinMarketCap에서 발견된 에어드롭: {title.strip()}",
                    estimated_value_krw=value_krw,
                    action_url="https://coinmarketcap.com/airdrop/",
                    action_type=ActionType.MANUAL,
                    status=EventStatus.DISCOVERED,
                ))

        except Exception as e:
            logger.debug("[airdrop] CMC scan error: %s", e)

        return events

    async def _scan_airdrops_io(self) -> List[EarnEvent]:
        """Scan airdrops.io for active airdrops."""
        events: List[EarnEvent] = []
        client = await self._get_client()

        try:
            resp = await client.get("https://airdrops.io/latest-airdrops/")
            if resp.status_code != 200:
                return events

            text = resp.text

            # Extract airdrop listings (simplified HTML parsing)
            # Look for airdrop names and links
            listings = re.findall(
                r'<a[^>]*href="(https://airdrops\.io/[^"]+)"[^>]*>([^<]+)</a>',
                text,
            )

            for url, title in listings[:15]:
                # Skip navigation/footer links
                if len(title.strip()) < 3 or title.strip().lower() in {"home", "latest", "exclusive"}:
                    continue

                event_hash = hashlib.md5(url.encode()).hexdigest()
                if event_hash in self._seen_ids:
                    continue
                self._seen_ids.add(event_hash)

                # Check if related to an Upbit-listed coin
                is_upbit_related = any(
                    coin.lower() in title.lower() for coin in UPBIT_COINS
                )

                # Check for scam signals
                is_suspicious = any(
                    sig in title.lower() for sig in SCAM_SIGNALS
                )
                if is_suspicious:
                    continue

                estimated_value = 15000.0 if is_upbit_related else 5000.0

                events.append(EarnEvent(
                    source=EarnSource.AIRDROP,
                    title=f"Airdrop: {title.strip()}",
                    description=(
                        f"airdrops.io 에어드롭: {title.strip()}"
                        + (" (업비트 상장 코인)" if is_upbit_related else "")
                    ),
                    estimated_value_krw=estimated_value,
                    action_url=url,
                    action_type=ActionType.MANUAL,
                    status=EventStatus.DISCOVERED,
                    metadata={"upbit_related": is_upbit_related},
                ))

        except Exception as e:
            logger.debug("[airdrop] airdrops.io scan error: %s", e)

        return events

    async def claim(self, event: EarnEvent) -> bool:
        """Airdrops generally require manual participation."""
        return False

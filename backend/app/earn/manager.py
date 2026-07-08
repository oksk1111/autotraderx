"""EarnManager — orchestrates all earning strategies.

Pattern: identical to ShadowRunner — periodic async loop that calls each
earner's scan() method and processes discovered opportunities.

Lifecycle:
  Phase 1 (balance == 0): Scan for free earning opportunities
  Phase 2 (balance >= 6,000 KRW): Activate micro-capital trading
  Phase 3 (balance >= 50,000 KRW): Normal trading mode
"""
from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass, field
from typing import List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from .base import ActionType, BaseEarner, EarnEvent, EventStatus

logger = get_logger(__name__)


@dataclass
class EarnState:
    """In-memory state for the earn manager."""

    current_phase: int = 1
    total_earned_krw: float = 0.0
    phase2_activated_at: Optional[dt.datetime] = None
    phase3_activated_at: Optional[dt.datetime] = None
    last_scan_at: Optional[dt.datetime] = None
    opportunities_found: int = 0
    opportunities_claimed: int = 0
    recent_events: List[EarnEvent] = field(default_factory=list)

    @property
    def last_scan_iso(self) -> Optional[str]:
        return self.last_scan_at.isoformat() if self.last_scan_at else None


class EarnManager:
    """Async runner that orchestrates all earning strategies."""

    def __init__(self, interval_sec: Optional[int] = None):
        self.s = get_settings()
        self.interval = interval_sec or self.s.earn_scan_interval_sec
        self._stop = asyncio.Event()
        self.earners: List[BaseEarner] = []
        self.state = EarnState()
        self._init_earners()

    def _init_earners(self) -> None:
        """Initialize enabled earners."""
        s = self.s

        if s.earn_upbit_events_enabled:
            from .upbit_event_monitor import UpbitEventMonitor
            self.earners.append(UpbitEventMonitor())

        if s.earn_airdrop_enabled:
            from .airdrop_scanner import AirdropScanner
            self.earners.append(AirdropScanner())

        if s.earn_faucets_enabled:
            from .faucet_claimer import FaucetClaimer
            self.earners.append(FaucetClaimer())

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        """Main loop — runs alongside ShadowRunner in the FastAPI lifespan."""
        await asyncio.sleep(15)  # Let WebSocket/DB warm up first
        logger.info(
            "EarnManager started, %d earners active, interval=%ds",
            len(self.earners), self.interval,
        )
        while not self._stop.is_set():
            await self._scan_cycle()
            await self._check_phase_transition()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                pass
        logger.info("EarnManager stopped")

    async def _scan_cycle(self) -> None:
        """Run one full scan across all earners."""
        self.state.last_scan_at = dt.datetime.utcnow()

        for earner in self.earners:
            if not earner.is_enabled():
                continue
            try:
                events = await earner.scan()
                for event in events:
                    await self._process_event(earner, event)
            except Exception as e:
                logger.exception("EarnManager %s scan error: %s", earner.name, e)

    async def _process_event(self, earner: BaseEarner, event: EarnEvent) -> None:
        """Process a single discovered event."""
        self.state.opportunities_found += 1

        # Keep recent events (max 100)
        self.state.recent_events.append(event)
        if len(self.state.recent_events) > 100:
            self.state.recent_events = self.state.recent_events[-100:]

        # Auto-claim if eligible and enabled
        if event.is_claimable and self.s.earn_auto_claim:
            try:
                success = await earner.claim(event)
                if success:
                    event.status = EventStatus.CLAIMED
                    self.state.opportunities_claimed += 1
                    self.state.total_earned_krw += event.estimated_value_krw
                    logger.info(
                        "[earn] CLAIMED %s: %s (~%.0f KRW)",
                        earner.name, event.title, event.estimated_value_krw,
                    )
                else:
                    event.status = EventStatus.FAILED
            except Exception as e:
                event.status = EventStatus.FAILED
                logger.warning("[earn] claim failed %s: %s", event.title, e)
        else:
            # Notify user about manual opportunities
            await self._notify_opportunity(event)

    async def _notify_opportunity(self, event: EarnEvent) -> None:
        """Send notification for discovered opportunity."""
        event.status = EventStatus.NOTIFIED

        # Use existing notification service
        try:
            from app.services.notification import get_notification_service
            svc = get_notification_service()
            msg = (
                f"💰 [{event.source.value}] {event.title}\n"
                f"예상 가치: {event.estimated_value_krw:,.0f} KRW\n"
                f"{event.description[:200]}"
            )
            if event.action_url:
                msg += f"\n🔗 {event.action_url}"
            await asyncio.to_thread(svc.send, "earn_opportunity", msg)
        except Exception as e:
            logger.debug("Notification send failed (non-critical): %s", e)

    async def _check_phase_transition(self) -> None:
        """Check if accumulated balance allows phase transition."""
        try:
            from app.broker import UpbitLiveBroker
            broker = UpbitLiveBroker()
            available_krw = broker.get_available_krw()
        except Exception:
            available_krw = 0.0

        if available_krw >= self.s.earn_phase3_threshold_krw and self.state.current_phase < 3:
            self.state.current_phase = 3
            self.state.phase3_activated_at = dt.datetime.utcnow()
            logger.info(
                "[earn] Phase 3 activated! Balance: %.0f KRW", available_krw,
            )
            await self._notify_phase_change(3, available_krw)

        elif available_krw >= self.s.earn_phase2_threshold_krw and self.state.current_phase < 2:
            self.state.current_phase = 2
            self.state.phase2_activated_at = dt.datetime.utcnow()
            logger.info(
                "[earn] Phase 2 activated! Balance: %.0f KRW >= %.0f. Micro-trading enabled.",
                available_krw, self.s.earn_phase2_threshold_krw,
            )
            await self._notify_phase_change(2, available_krw)
            self._activate_micro_trading()

    def _activate_micro_trading(self) -> None:
        """Apply micro-capital trading parameters."""
        try:
            from .micro_optimizer import MicroCapitalOptimizer
            optimizer = MicroCapitalOptimizer()
            optimizer.apply()
            logger.info("[earn] Micro-capital optimizer applied")
        except Exception as e:
            logger.warning("[earn] Micro-capital optimizer failed: %s", e)

    async def _notify_phase_change(self, phase: int, balance: float) -> None:
        """Notify user about phase transition."""
        try:
            from app.services.notification import get_notification_service
            svc = get_notification_service()
            msg = (
                f"🚀 Phase {phase} 활성화!\n"
                f"현재 잔고: {balance:,.0f} KRW\n"
            )
            if phase == 2:
                msg += "초소액 자동매매를 시작합니다."
            elif phase == 3:
                msg += "정상 자동매매 모드로 전환합니다."
            await asyncio.to_thread(svc.send, "phase_change", msg)
        except Exception:
            pass

    def get_status(self) -> dict:
        """Return current earn system status for API/dashboard."""
        return {
            "phase": self.state.current_phase,
            "total_earned_krw": self.state.total_earned_krw,
            "opportunities_found": self.state.opportunities_found,
            "opportunities_claimed": self.state.opportunities_claimed,
            "last_scan": self.state.last_scan_iso,
            "earners": {
                e.name: {"enabled": e.is_enabled()} for e in self.earners
            },
            "recent_events_count": len(self.state.recent_events),
        }

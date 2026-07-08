"""API routes for the Earn subsystem — status, opportunities, history."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.logging import get_logger
from app.earn import get_earn_manager

logger = get_logger(__name__)
router = APIRouter()


@router.get("/status")
def earn_status() -> dict:
    """Current earn system state: phase, earnings, active earners."""
    mgr = get_earn_manager()
    return mgr.get_status()


@router.get("/opportunities")
def list_opportunities(limit: int = 50) -> dict:
    """List recently discovered opportunities."""
    mgr = get_earn_manager()
    events = mgr.state.recent_events[-limit:]

    return {
        "count": len(events),
        "opportunities": [
            {
                "source": e.source.value,
                "title": e.title,
                "description": e.description[:300],
                "estimated_value_krw": e.estimated_value_krw,
                "action_url": e.action_url,
                "action_type": e.action_type.value,
                "status": e.status.value,
                "discovered_at": e.discovered_at.isoformat(),
                "expires_at": e.expires_at.isoformat() if e.expires_at else None,
            }
            for e in reversed(events)
        ],
    }


@router.get("/history")
def earn_history() -> dict:
    """Earning history and cumulative stats."""
    mgr = get_earn_manager()
    state = mgr.state

    return {
        "current_phase": state.current_phase,
        "total_earned_krw": state.total_earned_krw,
        "opportunities_found": state.opportunities_found,
        "opportunities_claimed": state.opportunities_claimed,
        "phase2_activated_at": (
            state.phase2_activated_at.isoformat() if state.phase2_activated_at else None
        ),
        "phase3_activated_at": (
            state.phase3_activated_at.isoformat() if state.phase3_activated_at else None
        ),
    }


@router.post("/toggle")
def toggle_earn_system(enabled: bool = True) -> dict:
    """Enable or disable the earn system at runtime."""
    s = get_settings()
    # Note: This only affects runtime state, not the .env file
    s.earn_system_enabled = enabled
    return {"earn_system_enabled": enabled, "message": "Updated (runtime only)"}


@router.post("/scan-now")
async def trigger_scan() -> dict:
    """Manually trigger an immediate scan cycle."""
    mgr = get_earn_manager()
    await mgr._scan_cycle()
    return {
        "message": "Scan completed",
        "opportunities_found": mgr.state.opportunities_found,
        "recent_count": len(mgr.state.recent_events),
    }

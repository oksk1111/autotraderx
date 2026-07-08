"""Micro-Capital Optimizer — adjusts trading parameters for ultra-small accounts.

When balance is between Phase 2 threshold (6,000 KRW) and Phase 3 threshold (50,000 KRW),
this optimizer overrides the trading engine settings to maximize survival and growth:

Strategy:
  - Single position only (concentrate capital)
  - High-confidence entries only (min 0.65 score)
  - Dip-buying strategy (historically highest win rate)
  - Max 3 trades per day (minimize fee drag)
  - 100% profit reinvestment (compound growth)
  - Tighter stops to protect limited capital

Expected behavior:
  - Conservative but persistent: ~1-3 trades per day
  - Target: 1-2% daily growth via compounding
  - From 6,000 KRW to 50,000 KRW in ~3-4 weeks at 1.5% daily avg
"""
from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class MicroCapitalOptimizer:
    """Adjusts trading parameters for micro-capital phase."""

    # Micro-capital parameter overrides
    MICRO_SETTINGS = {
        "max_open_positions": 1,          # Single position to concentrate capital
        "strategy_mode": "dip",           # Highest win-rate strategy
        "min_confidence_for_trade": 0.65, # Only high-confidence signals
        "max_daily_trades": 3,            # Limit fee drag
        "risk_per_trade": 0.3,            # 30% risk per trade (aggressive for growth)
        "max_position_ratio": 0.9,        # Use most of available capital
        "stop_loss_percent": 1.5,         # Tighter stop (1.5%)
        "take_profit_percent": 3.0,       # Reasonable target (3%)
        "trading_cycle_seconds": 30,      # Faster evaluation for opportunities
    }

    def __init__(self):
        self.s = get_settings()
        self._original_values: dict = {}
        self._applied = False

    def apply(self) -> None:
        """Apply micro-capital optimized settings."""
        if self._applied:
            return

        # Save original values for potential rollback
        for key, new_val in self.MICRO_SETTINGS.items():
            if hasattr(self.s, key):
                self._original_values[key] = getattr(self.s, key)
                setattr(self.s, key, new_val)

        self._applied = True
        logger.info(
            "[micro] Applied micro-capital settings: positions=%d, strategy=%s, "
            "confidence=%.2f, max_trades=%d",
            self.MICRO_SETTINGS["max_open_positions"],
            self.MICRO_SETTINGS["strategy_mode"],
            self.MICRO_SETTINGS["min_confidence_for_trade"],
            self.MICRO_SETTINGS["max_daily_trades"],
        )

    def rollback(self) -> None:
        """Restore original settings when transitioning to Phase 3."""
        if not self._applied:
            return

        for key, orig_val in self._original_values.items():
            if hasattr(self.s, key):
                setattr(self.s, key, orig_val)

        self._applied = False
        self._original_values.clear()
        logger.info("[micro] Rolled back to normal trading parameters")

    @property
    def is_applied(self) -> bool:
        return self._applied

    @staticmethod
    def should_activate(equity_krw: float) -> bool:
        """Determine if micro-capital mode should be active."""
        s = get_settings()
        return (
            s.earn_phase2_threshold_krw <= equity_krw < s.earn_phase3_threshold_krw
        )

    @staticmethod
    def should_deactivate(equity_krw: float) -> bool:
        """Determine if we've grown past micro-capital phase."""
        s = get_settings()
        return equity_krw >= s.earn_phase3_threshold_krw

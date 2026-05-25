"""v5.0 Risk layer."""
from .kill_switch import KillSwitch, get_kill_switch
from .sizing import compute_position_size, SizingResult
from .guards import (
    RiskContext,
    GuardResult,
    KillSwitchGuard,
    DailyLossGuard,
    MaxDailyTradesGuard,
    ConcurrencyGuard,
    CooldownGuard,
    FeeViabilityGuard,
    LiquidityGuard,
    NewsBlackoutGuard,
    RiskGuardChain,
)

__all__ = [
    "KillSwitch", "get_kill_switch",
    "compute_position_size", "SizingResult",
    "RiskContext", "GuardResult",
    "KillSwitchGuard", "DailyLossGuard", "MaxDailyTradesGuard",
    "ConcurrencyGuard", "CooldownGuard", "FeeViabilityGuard",
    "LiquidityGuard", "NewsBlackoutGuard", "RiskGuardChain",
]

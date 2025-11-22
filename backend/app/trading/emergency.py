from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.ml.predictor import MLSignal

logger = get_logger(__name__)


@dataclass
class EmergencyRule:
    label: str
    threshold: float


class EmergencyGuard:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.rules = [
            EmergencyRule("volatility_spike", 0.92),
            EmergencyRule("news_negative", 0.85),
            EmergencyRule("volume_manipulation", 0.9),
        ]

    def tripped(self, signal: MLSignal, features: dict[str, float | str]) -> bool:
        custom_score = features.get("volatility", 0)
        if isinstance(custom_score, (float, int)) and custom_score > 0.95:
            logger.warning("Emergency due to volatility score %.3f", custom_score)
            return True
        if signal.emergency_score > self.rules[0].threshold:
            logger.warning("Emergency due to ML emergency score %.3f", signal.emergency_score)
            return True
        return False

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration sourced from environment variables."""

    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / ".env", env_file_encoding="utf-8", extra="allow")

    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    backend_port: int = 8000
    frontend_port: int = 4173

    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "autotrader"
    postgres_user: str = "autotrader"
    postgres_password: str = "autotrader"
    database_url: str | None = None

    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    redis_url: str | None = None

    upbit_access_key: str = ""
    upbit_secret_key: str = ""

    # AI/LLM 설정 (ML 우선, LLM은 선택적)
    use_ai_verification: bool = False  # ML 기반 거래로 전환
    use_groq: bool = False  # Groq API rate limit 문제로 비활성화
    use_ollama: bool = False  # 필요시 활성화 (현재는 ML만 사용)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout: float = 5.0  # Ollama 타임아웃 단축 (20s → 5s)

    secret_key: str = "change_me"
    encryption_key: str = "change_me"

    default_trade_amount: float = 50_000
    max_open_positions: int = 3
    stop_loss_percent: float = 2.0  # 워뇨띠 스타일: -2% 손절
    take_profit_percent: float = 2.0  # 워뇨띠 스타일: +2% 익절
    max_position_hold_minutes: int = 30  # 최대 포지션 보유 시간 (30분)
    
    # 매매 주기 설정 (초단위, 기본값: 5분)
    trading_cycle_seconds: int = 60
    
    # 공격적 매매 모드 설정
    aggressive_trading_mode: bool = True  # True: tick 단위 공격적 매매 활성화
    tick_interval_seconds: int = 60  # tick 매매 주기 (초단위, 기본값: 1분)
    tick_min_confidence: float = 0.7  # tick 매매 최소 신뢰도 (기본값: 70%)
    tick_max_positions: int = 5  # tick 매매 최대 동시 포지션 수

    tracked_markets: List[str] = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"]

    slack_webhook_url: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def resolved_redis_url(self) -> str:
        if self.redis_url:
            return self.redis_url
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[arg-type]

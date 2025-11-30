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

    groq_api_key: str = ""
    groq_model: str = "llama-3.1-70b-versatile"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen2.5:7b"

    secret_key: str = "change_me"
    encryption_key: str = "change_me"

    default_trade_amount: float = 50_000
    max_open_positions: int = 3
    stop_loss_percent: float = 3.0
    take_profit_percent: float = 5.0
    use_ai_verification: bool = True
    
    # 매매 주기 설정 (초단위, 기본값: 5분)
    trading_cycle_seconds: int = 300

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

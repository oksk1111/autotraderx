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

    # AI/LLM 설정
    use_ai_verification: bool = False  # ML 및 LLM 검증 비활성화 -> 기술적 지표/전략 알고리즘 우선
    use_groq: bool = False
    use_ollama: bool = False
    
    # ML 모델 사용 여부 (Configurable) - v4.1 Update
    use_ml_models: bool = False  # ML 모델 로드 및 예측 비활성화 (클라우드 비용/리소스 절감)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout: float = 5.0  # Ollama 타임아웃 단축 (20s → 5s)

    secret_key: str = "change_me"
    encryption_key: str = "change_me"
    jwt_secret_key: str = "change_me"
    
    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:4173/auth/google/callback"
    
    # Naver OAuth
    naver_client_id: str = ""
    naver_client_secret: str = ""
    naver_redirect_uri: str = "http://localhost:4173/auth/naver/callback"
    
    # Kakao OAuth
    kakao_client_id: str = ""
    kakao_redirect_uri: str = "http://localhost:4173/auth/kakao/callback"

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
    tick_min_confidence: float = 0.6  # tick 매매 최소 신뢰도 (기본값: 60%, v4.0 조정)
    tick_max_positions: int = 5  # tick 매매 최대 동시 포지션 수

    # 펌핑 감지 (Pump Detection) 설정 [v4.1]
    pump_detection_enabled: bool = True
    pump_threshold_percent: float = 1.5  # 1.5% 이상 급등 시 감지
    pump_check_interval: float = 2.0  # 2초마다 체크
    pump_lookback_seconds: int = 60  # 최근 60초 기준 상승률
    pump_investment_ratio: float = 0.2  # 펌핑 감지 시 자산의 20% 투입

    tracked_markets: List[str] = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"]

    slack_webhook_url: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    
    # Email Notification
    email_host: str | None = "smtp.gmail.com"
    email_port: int = 587
    email_user: str | None = None
    email_password: str | None = None
    
    # Alert Level (INFO, WARNING, ERROR)
    alert_level: str = "WARNING"

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

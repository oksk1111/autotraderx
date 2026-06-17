from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration sourced from environment variables."""

    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / ".env", env_file_encoding="utf-8", extra="allow")

    environment: str = "production"
    debug: bool = False
    log_level: str = "WARNING"

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

    # AI/LLM 설정 (LLM 무거운 연산 제거, 경량화 및 속도 향상)
    use_ai_verification: bool = False
    use_groq: bool = False
    use_ollama: bool = False
    
    # ML 모델 사용 여부 (무거운 모델 제거)
    use_ml_models: bool = False
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

    default_trade_amount: float = 10_000
    max_open_positions: int = 5
    stop_loss_percent: float = 2.0
    take_profit_percent: float = 4.0
    max_position_hold_minutes: int = 30
    
    # 매매 주기 설정 (초단위) 
    trading_cycle_seconds: int = 60
    
    # Legacy momentum/reversal/pump settings removed.
    
    # v6.0 신규: 자본 보존 안전장치 (Capital Preservation)
    daily_max_loss_percent: float = 5.0
    min_confidence_for_trade: float = 0.50
    max_investment_ratio: float = 0.2
    cooldown_after_loss_minutes: int = 5
    max_daily_trades: int = 50
    llm_autotrading_enabled: bool = False

    # 급등 스트리밍 알림 (WebSocket, alert-only)
    surge_alert_enabled: bool = True
    surge_alert_threshold_percent: float = 1.8
    surge_alert_window_seconds: int = 20
    surge_alert_cooldown_seconds: int = 180
    surge_alert_min_volume_24h: float = 35_000_000_000

    # v7.0: tracked_markets 는 동적 유니버스의 fallback / 시드 역할만 한다.
    tracked_markets: List[str] = ["KRW-BTC", "KRW-ETH"]  # seed/anchor markets

    # =========================================================================
    # v7.0 Dynamic Portfolio — 유망 코인 자동 선별 (Cross-sectional momentum)
    # =========================================================================
    dynamic_universe_enabled: bool = True      # 동적 유니버스 on/off
    universe_size: int = 10
    universe_refresh_sec: int = 900
    universe_min_value_24h: float = 30_000_000_000  # 최소 24h 거래대금 (유동성 필터)
    universe_max_spread_pct: float = 0.005     # 진입 허용 최대 스프레드 (0.5%)
    universe_momentum_window: int = 24         # 모멘텀 평가 캔들 수 (15m * 24 = 6h)
    universe_always_include: List[str] = ["KRW-BTC", "KRW-ETH"]  # 항상 포함 앵커
    universe_exclude: List[str] = []           # 제외할 마켓 (스테이블코인 등)
    max_portfolio_exposure: float = 0.95

    # =========================================================================
    # v5.0 Capital First Rebuild — 신규 설정
    # =========================================================================
    # 1) 라이브 매매 활성 (기본 true = real Upbit orders when keys are configured)
    live_trading_enabled: bool = True

    # 2) 리스크 관리
    risk_per_trade: float = 0.05
    max_position_ratio: float = 1.0
    daily_loss_limit: float = 0.05        # v8.1: 5%로 완화 (소액 계좌)
    fee_rate: float = 0.0005              # 업비트 수수료 (편도)
    slippage_est: float = 0.0005          # 슬리피지 추정

    # 3) 전략 모드
    # auto: hybrid (v8.0 default - LLM + mechanical)
    # hybrid: LLM + mechanical confluence strategy
    # trend: trend-following only
    # range: mean-reversion only  
    # momentum: aggressive momentum strategy
    # dip: buy-the-dip strategy
    # off: no trading
    strategy_mode: str = "momentum"

    # v8.0 Hybrid Strategy Settings
    hybrid_min_confluence: float = 0.55     # Minimum score for entry (lowered for more trades)
    hybrid_llm_weight: float = 0.35         # LLM contribution to final score
    hybrid_use_multi_strategy: bool = True  # Use multiple strategies in parallel

    # 4) Kill switch (Redis key 와 매칭)
    kill_switch: bool = False

    # 5) WebSocket
    upbit_ws_url: str = "wss://api.upbit.com/websocket/v1"
    ws_ping_interval_sec: int = 60
    ws_reconnect_max_sec: int = 30

    # 6) 캔들 buffer 크기
    candle_1m_history: int = 240
    candle_5m_history: int = 200
    candle_15m_history: int = 200
    trade_buffer_size: int = 2000

    # 7) 백테스트
    backtest_data_dir: str = "data/raw"

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

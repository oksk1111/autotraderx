from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # App Config
    APP_NAME: str = "AutoTraderX"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # Security
    SECRET_KEY: str
    ENCRYPTION_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Upbit API
    UPBIT_ACCESS_KEY: str
    UPBIT_SECRET_KEY: str
    UPBIT_API_URL: str = "https://api.upbit.com/v1"
    
    # Ollama AI Settings
    OLLAMA_API_URL: str = "http://host.docker.internal:11434"
    OLLAMA_MODEL: str = "deepseek-r1:8b"
    OLLAMA_TEMPERATURE: float = 0.7
    USE_AI_DECISION: bool = True
    
    # News & Sentiment API
    NEWS_API_KEY: str = ""
    
    # Database
    DATABASE_URL: str
    
    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Trading Settings
    MAX_TRADE_AMOUNT: float = 100000.0
    DAILY_TRADE_LIMIT: int = 10
    STOP_LOSS_PERCENT: float = 2.0
    TAKE_PROFIT_PERCENT: float = 3.0
    
    # Technical Indicators
    RSI_PERIOD: int = 14
    RSI_OVERBOUGHT: int = 70
    RSI_OVERSOLD: int = 30
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

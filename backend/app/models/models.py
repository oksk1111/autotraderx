from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.sql import func
from app.core.database import Base


class Trade(Base):
    """거래 내역 모델"""
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    market = Column(String(20), nullable=False)  # e.g., KRW-BTC
    side = Column(String(10), nullable=False)  # buy or sell
    price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)
    fee = Column(Float, default=0.0)
    order_id = Column(String(100), unique=True)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    executed_at = Column(DateTime(timezone=True), nullable=True)


class Position(Base):
    """포지션 모델"""
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    market = Column(String(20), nullable=False, unique=True)
    avg_buy_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    profit_loss = Column(Float, default=0.0)
    profit_loss_percent = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    stop_loss_price = Column(Float, nullable=True)
    take_profit_price = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class MarketData(Base):
    """시장 데이터 모델"""
    __tablename__ = "market_data"
    
    id = Column(Integer, primary_key=True, index=True)
    market = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    value = Column(Float, nullable=False)


class TradingSignal(Base):
    """매매 신호 모델"""
    __tablename__ = "trading_signals"
    
    id = Column(Integer, primary_key=True, index=True)
    market = Column(String(20), nullable=False)
    signal_type = Column(String(10), nullable=False)  # buy or sell
    price = Column(Float, nullable=False)
    confidence = Column(Float, default=0.0)
    indicators = Column(Text, nullable=True)  # JSON string of indicators
    executed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class BacktestResult(Base):
    """백테스트 결과 모델"""
    __tablename__ = "backtest_results"
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_name = Column(String(100), nullable=False)
    market = Column(String(20), nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    initial_balance = Column(Float, nullable=False)
    final_balance = Column(Float, nullable=False)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    total_profit = Column(Float, default=0.0)
    total_loss = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

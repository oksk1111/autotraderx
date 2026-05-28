import pytest
import datetime as dt
import time
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, PaperPosition, TradePosition, StrategySignal, TradeLog
from app.marketdata.store import Ticker, Orderbook, OrderbookUnit, get_store
from app.marketdata.candles import Candle
from app.engine.trading_engine import TradingEngine, get_engine
from app.strategy import Regime


@pytest.fixture(name="db_session")
def fixture_db_session():
    # Use in-memory SQLite for testing to avoid connection issues with PostgreSQL
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    
    with patch("app.engine.trading_engine.SessionLocal", TestingSessionLocal), \
         patch("app.broker.paper.SessionLocal", TestingSessionLocal), \
         patch("app.broker.upbit_live.SessionLocal", TestingSessionLocal):
        db = TestingSessionLocal()
        yield db
        db.close()


def test_trading_engine_evaluate_market(db_session):
    # Initialize trading engine
    engine = TradingEngine()
    
    # Configure mock store and settings using the global singleton store
    mock_store = get_store()
    mock_store._views.clear()
    engine.store = mock_store
    
    # 1. Populate candle history to trigger a strategy signal (TREND or RANGE)
    # Let's generate 100 1-minute, 5-minute, and 15-minute candles
    market = "KRW-BTC"
    now_ms = int(time.time() * 1000)
    
    candles_1m = []
    candles_5m = []
    candles_15m = []
    
    # Standard values to guarantee indicators calculate without NaN
    # Let's build a clear trend where EMA fast (20) > EMA slow (60)
    # Price rises gradually
    base_price = 80_000_000.0
    for i in range(100):
        price = base_price + i * 20_000.0
        
        c1 = Candle(
            market=market,
            timeframe="1m",
            open_time_ms=now_ms - (100 - i) * 60_000,
            open=price - 10000,
            high=price + 30000,
            low=price - 20000,
            close=price,
            volume=2.0 + (i % 3) * 0.5,
            quote_volume=(price * 2.0),
            closed=True
        )
        candles_1m.append(c1)
        
        if i % 5 == 0:
            c5 = Candle(
                market=market,
                timeframe="5m",
                open_time_ms=now_ms - (100 - i) * 60_000,
                open=price - 10000,
                high=price + 50000,
                low=price - 30000,
                close=price,
                volume=10.0,
                quote_volume=(price * 10.0),
                closed=True
            )
            candles_5m.append(c5)
            
        if i % 15 == 0:
            c15 = Candle(
                market=market,
                timeframe="15m",
                open_time_ms=now_ms - (100 - i) * 60_000,
                open=price - 10000,
                high=price + 100000,
                low=price - 50000,
                close=price,
                volume=30.0,
                quote_volume=(price * 30.0),
                closed=True
            )
            candles_15m.append(c15)

    mock_store.set_candles(market, "1m", candles_1m)
    mock_store.set_candles(market, "5m", candles_5m)
    mock_store.set_candles(market, "15m", candles_15m)
    
    # 2. Add modern ticker/orderbook to avoid Liquidity/Staleness filters
    ticker = Ticker(
        market=market,
        trade_price=base_price + 100 * 20_000.0,
        timestamp_ms=now_ms,
        acc_trade_price_24h=100_000_000_000.0, # 1000 Billion (> 5 Billion limit)
        high_24h=base_price + 1000000,
        low_24h=base_price - 1000000
    )
    mock_store.update_ticker(ticker)
    
    orderbook = Orderbook(
        market=market,
        timestamp_ms=now_ms,
        units=[OrderbookUnit(ask_price=base_price + 1000.0, bid_price=base_price, ask_size=1.0, bid_size=1.0)]
    )
    mock_store.update_orderbook(orderbook)
    
    # Check that staleness is near 0
    assert mock_store.staleness_sec(market) < 5
    
    # Disable live trading for clean paper trade evaluation during unit test
    engine.s.live_trading_enabled = False
    
    # Force regime of the classifier to RANGE or TREND
    engine.classifier.classify = MagicMock(return_value=MagicMock(regime=Regime.TREND, value="TREND", note="trend-up"))
    
    # Mock strategy evaluation to produce a BUY action signal
    mock_signal = MagicMock(
        action="BUY",
        regime="TREND",
        strategy="trend_following",
        price=base_price + 100 * 20_000.0,
        atr=20000.0,
        stop_price=base_price + 100 * 20_000.0 - 40000.0,
        target_price=(base_price + 100 * 20_000.0) * 1.05,
        rationale="strong breakout",
        metrics={}
    )
    engine.trend.evaluate = MagicMock(return_value=mock_signal)
    
    # 3. Evaluate the market!
    signal = engine.evaluate_market(market)
    
    # Print risk events to help diagnose any failures
    from app.models import RiskEvent
    events = db_session.query(RiskEvent).all()
    for ev in events:
        print(f"RISK EVENT logged in test: guard={ev.guard}, severity={ev.severity}, message={ev.message}")

    # Validate a BUY signal was raised and processed
    assert signal is not None
    assert signal.action == "BUY"
    
    # Validate paper trade was successfully executed and logged
    logs = db_session.query(TradeLog).all()
    assert len(logs) > 0
    assert logs[0].market == market
    assert logs[0].side == "BUY"
    assert logs[0].context.get("paper_ok") is True
    
    # Validate paper positions are updated
    paper_positions = db_session.query(PaperPosition).filter(PaperPosition.status == "OPEN").all()
    assert len(paper_positions) == 1
    assert paper_positions[0].market == market

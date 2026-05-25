"""In-memory rolling store for ticker / trades / orderbook / candles per market.

Thread-safe-ish (asyncio single-loop) singleton. No DB writes here.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from threading import RLock
from typing import Deque, Dict, List, Optional

from app.core.config import get_settings


@dataclass
class Ticker:
    market: str
    trade_price: float
    timestamp_ms: int
    acc_trade_price_24h: float = 0.0
    high_24h: float = 0.0
    low_24h: float = 0.0


@dataclass
class Trade:
    market: str
    price: float
    volume: float
    ask_bid: str  # "ASK" | "BID"
    timestamp_ms: int


@dataclass
class OrderbookUnit:
    ask_price: float
    bid_price: float
    ask_size: float
    bid_size: float


@dataclass
class Orderbook:
    market: str
    timestamp_ms: int
    units: List[OrderbookUnit] = field(default_factory=list)

    @property
    def spread_pct(self) -> float:
        if not self.units:
            return 0.0
        u = self.units[0]
        if u.bid_price <= 0:
            return 0.0
        return (u.ask_price - u.bid_price) / u.bid_price


@dataclass
class MarketView:
    market: str
    ticker: Optional[Ticker] = None
    orderbook: Optional[Orderbook] = None
    trades: Deque[Trade] = field(default_factory=deque)
    candles_1m: Deque = field(default_factory=deque)
    candles_5m: Deque = field(default_factory=deque)
    candles_15m: Deque = field(default_factory=deque)
    last_update_ts: float = 0.0


class MarketDataStore:
    """Singleton in-memory market data store."""

    def __init__(self):
        s = get_settings()
        self._views: Dict[str, MarketView] = {}
        self._lock = RLock()
        self._trade_buf = s.trade_buffer_size
        self._c1 = s.candle_1m_history
        self._c5 = s.candle_5m_history
        self._c15 = s.candle_15m_history

    def _view(self, market: str) -> MarketView:
        v = self._views.get(market)
        if v is None:
            v = MarketView(
                market=market,
                trades=deque(maxlen=self._trade_buf),
                candles_1m=deque(maxlen=self._c1),
                candles_5m=deque(maxlen=self._c5),
                candles_15m=deque(maxlen=self._c15),
            )
            self._views[market] = v
        return v

    # -- writers --------------------------------------------------------------
    def update_ticker(self, t: Ticker) -> None:
        with self._lock:
            v = self._view(t.market)
            v.ticker = t
            v.last_update_ts = time.time()

    def push_trade(self, t: Trade) -> None:
        with self._lock:
            v = self._view(t.market)
            v.trades.append(t)
            v.last_update_ts = time.time()

    def update_orderbook(self, ob: Orderbook) -> None:
        with self._lock:
            v = self._view(ob.market)
            v.orderbook = ob
            v.last_update_ts = time.time()

    def set_candles(self, market: str, tf: str, candles) -> None:
        with self._lock:
            v = self._view(market)
            dq = self._candle_dq(v, tf)
            dq.clear()
            for c in candles:
                dq.append(c)

    def append_candle(self, market: str, tf: str, candle) -> None:
        with self._lock:
            v = self._view(market)
            self._candle_dq(v, tf).append(candle)

    def replace_last_candle(self, market: str, tf: str, candle) -> None:
        with self._lock:
            v = self._view(market)
            dq = self._candle_dq(v, tf)
            if dq:
                dq[-1] = candle
            else:
                dq.append(candle)

    @staticmethod
    def _candle_dq(v: MarketView, tf: str) -> Deque:
        if tf == "1m":
            return v.candles_1m
        if tf == "5m":
            return v.candles_5m
        if tf == "15m":
            return v.candles_15m
        raise ValueError(f"unknown timeframe: {tf}")

    # -- readers --------------------------------------------------------------
    def get_ticker(self, market: str) -> Optional[Ticker]:
        with self._lock:
            v = self._views.get(market)
            return v.ticker if v else None

    def get_orderbook(self, market: str) -> Optional[Orderbook]:
        with self._lock:
            v = self._views.get(market)
            return v.orderbook if v else None

    def get_candles(self, market: str, tf: str) -> list:
        with self._lock:
            v = self._views.get(market)
            if not v:
                return []
            return list(self._candle_dq(v, tf))

    def known_markets(self) -> list[str]:
        with self._lock:
            return list(self._views.keys())

    def staleness_sec(self, market: str) -> float:
        with self._lock:
            v = self._views.get(market)
            if not v or v.last_update_ts == 0:
                return float("inf")
            return time.time() - v.last_update_ts


_STORE: Optional[MarketDataStore] = None


def get_store() -> MarketDataStore:
    global _STORE
    if _STORE is None:
        _STORE = MarketDataStore()
    return _STORE

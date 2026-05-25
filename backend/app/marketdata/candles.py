"""Candle dataclass + builder that synthesizes minute candles from a trade stream
and bootstraps history from Upbit REST.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import time
from dataclasses import dataclass, asdict
from typing import List, Optional

import aiohttp

from app.core.logging import get_logger
from .store import MarketDataStore, Trade, get_store

logger = get_logger(__name__)


@dataclass
class Candle:
    market: str
    timeframe: str           # "1m" | "5m" | "15m"
    open_time_ms: int        # bar open time (UTC ms)
    open: float
    high: float
    low: float
    close: float
    volume: float            # base-asset volume (e.g. BTC)
    quote_volume: float = 0.0  # KRW volume
    trades: int = 0
    closed: bool = False     # bar finalized


_TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900}
_UPBIT_REST = "https://api.upbit.com/v1/candles/minutes/{unit}"


def _floor_open_ms(ts_ms: int, tf: str) -> int:
    sec = _TF_SECONDS[tf]
    bucket = (ts_ms // 1000 // sec) * sec
    return bucket * 1000


class CandleBuilder:
    """Builds 1m/5m/15m candles from streaming trades. Also bootstraps history."""

    def __init__(self, markets: List[str], store: Optional[MarketDataStore] = None):
        self.markets = markets
        self.store = store or get_store()
        # per (market, tf) -> currently-forming candle dict
        self._cur: dict[tuple[str, str], Candle] = {}
        self._listeners: list = []  # on-close subscribers

    def add_close_listener(self, callback) -> None:
        """callback(candle: Candle) -> None — invoked when a candle is finalized."""
        self._listeners.append(callback)

    async def bootstrap_history(self, count_per_tf: int = 200) -> None:
        """Pull historical candles from Upbit REST for each (market, tf)."""
        async with aiohttp.ClientSession() as session:
            for market in self.markets:
                for tf in ("1m", "5m", "15m"):
                    unit = int(_TF_SECONDS[tf] // 60)
                    url = _UPBIT_REST.format(unit=unit)
                    params = {"market": market, "count": count_per_tf}
                    try:
                        async with session.get(url, params=params, timeout=10) as resp:
                            data = await resp.json()
                    except Exception as e:
                        logger.warning("bootstrap %s %s failed: %s", market, tf, e)
                        continue
                    if not isinstance(data, list):
                        logger.warning("bootstrap unexpected response %s %s: %s", market, tf, data)
                        continue
                    # Upbit returns newest first → reverse to oldest-first
                    candles: List[Candle] = []
                    for row in reversed(data):
                        try:
                            ts_str = row["candle_date_time_utc"]
                            ts = dt.datetime.fromisoformat(ts_str).replace(tzinfo=dt.timezone.utc)
                            candles.append(Candle(
                                market=market,
                                timeframe=tf,
                                open_time_ms=int(ts.timestamp() * 1000),
                                open=float(row["opening_price"]),
                                high=float(row["high_price"]),
                                low=float(row["low_price"]),
                                close=float(row["trade_price"]),
                                volume=float(row["candle_acc_trade_volume"]),
                                quote_volume=float(row.get("candle_acc_trade_price", 0.0)),
                                trades=0,
                                closed=True,
                            ))
                        except Exception as e:  # noqa
                            logger.debug("parse candle skip: %s", e)
                            continue
                    self.store.set_candles(market, tf, candles)
                    logger.info("bootstrap %s %s loaded %d candles", market, tf, len(candles))
                    # Rate limit polite
                    await asyncio.sleep(0.15)

    def on_trade(self, t: Trade) -> None:
        """Update in-progress candles for each timeframe."""
        for tf in ("1m", "5m", "15m"):
            self._update_tf(t, tf)

    def _update_tf(self, t: Trade, tf: str) -> None:
        open_ms = _floor_open_ms(t.timestamp_ms, tf)
        key = (t.market, tf)
        cur = self._cur.get(key)

        # New bucket → close previous, start new
        if cur is None or cur.open_time_ms != open_ms:
            if cur is not None:
                cur.closed = True
                self.store.replace_last_candle(t.market, tf, cur)
                self._notify(cur)
            cur = Candle(
                market=t.market,
                timeframe=tf,
                open_time_ms=open_ms,
                open=t.price,
                high=t.price,
                low=t.price,
                close=t.price,
                volume=t.volume,
                quote_volume=t.price * t.volume,
                trades=1,
                closed=False,
            )
            self._cur[key] = cur
            self.store.append_candle(t.market, tf, cur)
            return

        # Same bucket → incremental update
        cur.high = max(cur.high, t.price)
        cur.low = min(cur.low, t.price)
        cur.close = t.price
        cur.volume += t.volume
        cur.quote_volume += t.price * t.volume
        cur.trades += 1
        self.store.replace_last_candle(t.market, tf, cur)

    def _notify(self, candle: Candle) -> None:
        for cb in self._listeners:
            try:
                cb(candle)
            except Exception as e:  # noqa
                logger.exception("candle listener error: %s", e)

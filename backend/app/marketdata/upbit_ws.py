"""Upbit Public WebSocket client.

Subscribes to ticker / trade / orderbook for the given markets, normalizes
payloads into MarketDataStore, and feeds the CandleBuilder.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Iterable, List, Optional

import aiohttp

from app.core.config import get_settings
from app.core.logging import get_logger
from .store import MarketDataStore, Ticker, Trade, Orderbook, OrderbookUnit, get_store
from .candles import CandleBuilder

logger = get_logger(__name__)


class UpbitWebSocketClient:
    def __init__(
        self,
        markets: List[str],
        store: Optional[MarketDataStore] = None,
        candle_builder: Optional[CandleBuilder] = None,
    ):
        self.settings = get_settings()
        self.markets = markets
        self.store = store or get_store()
        self.candle_builder = candle_builder
        self._stop = asyncio.Event()
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        """Connect forever with exponential backoff on errors."""
        backoff = 1.0
        while not self._stop.is_set():
            try:
                await self._connect_once()
                backoff = 1.0  # reset on clean exit
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("Upbit WS error: %s — reconnecting in %.1fs", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, float(self.settings.ws_reconnect_max_sec))

    async def _connect_once(self) -> None:
        ticket = str(uuid.uuid4())
        subscribe_payload = [
            {"ticket": ticket},
            {"type": "ticker", "codes": self.markets, "isOnlyRealtime": True},
            {"type": "trade", "codes": self.markets, "isOnlyRealtime": True},
            {"type": "orderbook", "codes": self.markets, "isOnlyRealtime": True},
            {"format": "DEFAULT"},
        ]
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                self.settings.upbit_ws_url,
                heartbeat=self.settings.ws_ping_interval_sec,
                autoping=True,
                max_msg_size=0,
                timeout=10.0,
            ) as ws:
                self._ws = ws
                await ws.send_str(json.dumps(subscribe_payload))
                logger.info("Upbit WS connected. subscribed=%s", self.markets)

                async for msg in ws:
                    if self._stop.is_set():
                        await ws.close()
                        return
                    if msg.type == aiohttp.WSMsgType.BINARY:
                        try:
                            payload = json.loads(msg.data.decode("utf-8"))
                        except Exception:
                            continue
                    elif msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            payload = json.loads(msg.data)
                        except Exception:
                            continue
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        logger.warning("Upbit WS closed/error: %s", msg)
                        return
                    else:
                        continue

                    self._dispatch(payload)

    def _dispatch(self, payload: dict) -> None:
        ptype = payload.get("type") or payload.get("ty")
        try:
            if ptype == "ticker":
                t = Ticker(
                    market=payload["code"],
                    trade_price=float(payload["trade_price"]),
                    timestamp_ms=int(payload.get("timestamp", int(time.time() * 1000))),
                    acc_trade_price_24h=float(payload.get("acc_trade_price_24h", 0.0)),
                    high_24h=float(payload.get("high_price", 0.0)),
                    low_24h=float(payload.get("low_price", 0.0)),
                )
                self.store.update_ticker(t)
            elif ptype == "trade":
                tr = Trade(
                    market=payload["code"],
                    price=float(payload["trade_price"]),
                    volume=float(payload["trade_volume"]),
                    ask_bid=str(payload.get("ask_bid", "")),
                    timestamp_ms=int(payload.get("timestamp", int(time.time() * 1000))),
                )
                self.store.push_trade(tr)
                if self.candle_builder is not None:
                    self.candle_builder.on_trade(tr)
            elif ptype == "orderbook":
                units_raw = payload.get("orderbook_units", []) or []
                units = [
                    OrderbookUnit(
                        ask_price=float(u["ask_price"]),
                        bid_price=float(u["bid_price"]),
                        ask_size=float(u["ask_size"]),
                        bid_size=float(u["bid_size"]),
                    )
                    for u in units_raw[:5]
                ]
                ob = Orderbook(
                    market=payload["code"],
                    timestamp_ms=int(payload.get("timestamp", int(time.time() * 1000))),
                    units=units,
                )
                self.store.update_orderbook(ob)
        except Exception as e:  # noqa
            logger.debug("dispatch parse error: %s — payload=%s", e, payload)


async def run_upbit_ws_loop(markets: List[str]) -> None:
    """Convenience: bootstrap candles + run WS forever. For use in lifespan task."""
    store = get_store()
    builder = CandleBuilder(markets=markets, store=store)
    await builder.bootstrap_history(count_per_tf=200)
    client = UpbitWebSocketClient(markets=markets, store=store, candle_builder=builder)
    await client.run()

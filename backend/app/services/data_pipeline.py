from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import AsyncGenerator, Dict

import aiohttp
import pyupbit

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MarketTick:
    market: str
    price: float
    volume: float
    ask_bid: str


class UpbitStream:
    def __init__(self, markets: list[str]):
        self.markets = markets

    async def ticker_stream(self) -> AsyncGenerator[MarketTick, None]:
        async with aiohttp.ClientSession() as session:
            uri = "wss://api.upbit.com/websocket/v1"
            payload = [{"ticket": "autotrader"}, {"type": "ticker", "codes": self.markets}]
            async with session.ws_connect(uri) as ws:
                await ws.send_json(payload)
                async for msg in ws:
                    data = msg.json(loads=None)
                    yield MarketTick(
                        market=data["code"],
                        price=data["trade_price"],
                        volume=data["acc_trade_volume"],
                        ask_bid=data["ask_bid"],
                    )


class HistoricalDataService:
    def __init__(self, markets: list[str]):
        self.markets = markets

    async def fetch_recent(self) -> Dict[str, list[dict]]:
        """
        최근 시장 데이터 조회 (시간봉 데이터, 최소 200개)
        ML 모델이 24시간 시퀀스 + 기술적 지표 계산을 위해 충분한 데이터 필요
        """
        loop = asyncio.get_event_loop()
        results: Dict[str, list[dict]] = {}
        for market in self.markets:
            try:
                # minute60 (1시간봉) 데이터 200개 조회
                candles = await loop.run_in_executor(None, pyupbit.get_ohlcv, market, "minute60", 200)
                if candles is not None and len(candles) > 0:
                    results[market] = candles.reset_index().to_dict("records")
                    logger.debug(f"Fetched {len(candles)} candles for {market}")
                else:
                    logger.warning(f"No data received for {market}")
                    results[market] = []
            except Exception as e:
                logger.error(f"Error fetching data for {market}: {e}")
                results[market] = []
        return results

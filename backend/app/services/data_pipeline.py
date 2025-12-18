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
                    # reset_index()로 timestamp를 컬럼으로 변환하되, 'index' 컬럼 제거
                    df = candles.reset_index()
                    if 'index' in df.columns:
                        df = df.drop(columns=['index'])
                    results[market] = df.to_dict("records")
                    logger.debug(f"Fetched {len(candles)} candles for {market}")
                else:
                    logger.warning(f"No data received for {market}")
                    results[market] = []
            except Exception as e:
                logger.error(f"Error fetching data for {market}: {e}")
                results[market] = []
        return results

    async def fetch_multi_timeframe(self) -> Dict[str, Dict[str, list[dict]]]:
        """
        멀티 타임프레임 데이터 조회 (1h, 15m, 5m)
        Returns: {market: {'minute60': [...], 'minute15': [...], 'minute5': [...]}}
        """
        loop = asyncio.get_event_loop()
        results: Dict[str, Dict[str, list[dict]]] = {}
        intervals = ["minute60", "minute15", "minute5"]
        
        for market in self.markets:
            results[market] = {}
            for interval in intervals:
                success = False
                for attempt in range(3):
                    try:
                        # API 호출 간격 조절 (Rate Limit 방지)
                        await asyncio.sleep(0.3 * (attempt + 1))
                        
                        candles = await loop.run_in_executor(None, pyupbit.get_ohlcv, market, interval, 200)
                        if candles is not None and len(candles) > 0:
                            df = candles.reset_index()
                            if 'index' in df.columns:
                                df = df.drop(columns=['index'])
                            results[market][interval] = df.to_dict("records")
                            success = True
                            break
                        else:
                            logger.warning(f"Attempt {attempt+1}: No data for {market} {interval}")
                    except Exception as e:
                        logger.warning(f"Attempt {attempt+1} failed for {market} {interval}: {e}")
                
                if not success:
                    logger.error(f"Failed to fetch data for {market} {interval} after 3 attempts")
                    results[market][interval] = []
        return results

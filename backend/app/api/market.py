from fastapi import APIRouter, HTTPException
from typing import List
from app.services.upbit.client import upbit_client

router = APIRouter()


@router.get("/markets")
async def get_markets():
    """마켓 목록 조회"""
    try:
        markets = upbit_client.get_markets()
        
        # KRW 마켓만 필터링
        krw_markets = [m for m in markets if m['market'].startswith('KRW-')]
        
        return {
            "success": True,
            "data": krw_markets
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ticker/{market}")
async def get_ticker(market: str):
    """현재가 정보 조회"""
    try:
        ticker = upbit_client.get_ticker([market])
        
        if not ticker:
            raise HTTPException(status_code=404, detail="Market not found")
        
        return {
            "success": True,
            "data": ticker[0]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tickers")
async def get_multiple_tickers(markets: str):
    """여러 마켓의 현재가 정보 조회"""
    try:
        market_list = markets.split(',')
        tickers = upbit_client.get_ticker(market_list)
        
        return {
            "success": True,
            "data": tickers
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orderbook/{market}")
async def get_orderbook(market: str):
    """호가 정보 조회"""
    try:
        orderbook = upbit_client.get_orderbook([market])
        
        if not orderbook:
            raise HTTPException(status_code=404, detail="Market not found")
        
        return {
            "success": True,
            "data": orderbook[0]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/candles/{market}")
async def get_candles(
    market: str,
    unit: str = "minutes/5",
    count: int = 200
):
    """캔들 데이터 조회"""
    try:
        candles = upbit_client.get_candles(
            market=market,
            unit=unit,
            count=count
        )
        
        if not candles:
            raise HTTPException(status_code=404, detail="No candle data found")
        
        return {
            "success": True,
            "data": candles
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

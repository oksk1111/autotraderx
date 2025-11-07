from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from app.services.trading.engine import trading_engine
from app.services.upbit.client import upbit_client

router = APIRouter()


class TradeRequest(BaseModel):
    market: str
    signal: str  # buy, sell, hold
    amount: Optional[float] = None


class AnalyzeRequest(BaseModel):
    market: str
    interval: str = "minutes/5"
    count: int = 200


@router.post("/analyze")
async def analyze_market(request: AnalyzeRequest):
    """시장 분석 및 매매 신호 생성"""
    try:
        # 캔들 데이터 조회
        candles = upbit_client.get_candles(
            market=request.market,
            unit=request.interval,
            count=request.count
        )
        
        if not candles:
            raise HTTPException(status_code=404, detail="No candle data found")
        
        # 시장 분석
        analysis = trading_engine.analyze_market(request.market, candles)
        
        return {
            "success": True,
            "data": analysis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_trade(request: TradeRequest):
    """거래 실행"""
    try:
        result = trading_engine.execute_trade(
            market=request.market,
            signal=request.signal,
            amount=request.amount
        )
        
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_positions():
    """현재 포지션 조회"""
    try:
        positions = trading_engine.get_positions()
        return {
            "success": True,
            "data": positions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-signals")
async def check_signals(markets: List[str]):
    """여러 마켓의 매매 신호 일괄 체크"""
    try:
        results = []
        
        for market in markets:
            # 캔들 데이터 조회
            candles = upbit_client.get_candles(
                market=market,
                unit="minutes/5",
                count=200
            )
            
            if candles:
                # 시장 분석
                analysis = trading_engine.analyze_market(market, candles)
                results.append(analysis)
            
            # 손절/익절 체크
            action = trading_engine.check_stop_loss_take_profit(market)
            if action:
                results.append({
                    "market": market,
                    "signal": action,
                    "reason": "Stop loss or take profit triggered"
                })
        
        return {
            "success": True,
            "data": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_trading_status():
    """거래 시스템 상태 조회"""
    try:
        positions = trading_engine.get_positions()
        
        return {
            "success": True,
            "data": {
                "active": True,
                "positions_count": len(positions),
                "positions": positions
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

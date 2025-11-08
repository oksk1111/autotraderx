"""
AI 트레이딩 로그 및 모니터링 API
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict
from datetime import datetime
from app.services.ai.ollama_engine import ollama_engine
from app.services.trading.engine import trading_engine

router = APIRouter()

# 메모리 기반 로그 저장소 (실제 프로덕션에서는 DB 사용)
ai_decision_logs: List[Dict] = []


@router.get("/status")
async def get_ai_status():
    """AI 엔진 상태 확인"""
    is_healthy = ollama_engine.check_health()
    
    return {
        "success": True,
        "data": {
            "ollama_running": is_healthy,
            "model": ollama_engine.model,
            "api_url": ollama_engine.base_url,
            "ai_enabled": trading_engine.use_ai
        }
    }


@router.get("/logs")
async def get_ai_decision_logs(limit: int = 50):
    """AI 판단 로그 조회"""
    return {
        "success": True,
        "data": ai_decision_logs[-limit:] if ai_decision_logs else []
    }


@router.post("/analyze")
async def analyze_with_ai(market: str = "KRW-BTC", use_ai: bool = True):
    """특정 마켓에 대한 AI 분석"""
    try:
        from app.services.upbit.client import upbit_client
        
        # 캔들 데이터 가져오기
        candles = upbit_client.get_candles(market, "minutes/5", 200)
        
        if not candles:
            raise HTTPException(status_code=404, detail="캔들 데이터를 가져올 수 없습니다")
        
        # 시장 분석
        analysis = trading_engine.analyze_market(market, candles, use_ai=use_ai)
        
        # 로그 저장
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "market": market,
            "signal": analysis.get("signal"),
            "confidence": analysis.get("confidence"),
            "reason": analysis.get("reason"),
            "ai_used": analysis.get("ai_used", False),
            "current_price": analysis.get("current_price")
        }
        
        ai_decision_logs.append(log_entry)
        
        # 최대 500개까지만 유지
        if len(ai_decision_logs) > 500:
            ai_decision_logs.pop(0)
        
        return {
            "success": True,
            "data": analysis
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/toggle")
async def toggle_ai_engine(enabled: bool):
    """AI 엔진 활성화/비활성화"""
    trading_engine.use_ai = enabled
    
    return {
        "success": True,
        "message": f"AI 엔진이 {'활성화' if enabled else '비활성화'}되었습니다",
        "data": {
            "ai_enabled": enabled
        }
    }


@router.delete("/logs")
async def clear_ai_logs():
    """AI 로그 초기화"""
    ai_decision_logs.clear()
    
    return {
        "success": True,
        "message": "AI 로그가 초기화되었습니다"
    }

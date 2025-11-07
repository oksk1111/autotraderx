from fastapi import APIRouter, HTTPException
from app.services.upbit.client import upbit_client

router = APIRouter()


@router.get("/balance")
async def get_account_balance():
    """계좌 잔고 조회"""
    try:
        accounts = upbit_client.get_accounts()
        
        return {
            "success": True,
            "data": accounts
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders")
async def get_orders(state: str = "wait", market: str = None):
    """주문 내역 조회"""
    try:
        orders = upbit_client.get_orders(market=market, state=state)
        
        return {
            "success": True,
            "data": orders
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/order/{uuid}")
async def get_order(uuid: str):
    """개별 주문 조회"""
    try:
        order = upbit_client.get_order(uuid)
        
        if "error" in order:
            raise HTTPException(status_code=404, detail=order["error"])
        
        return {
            "success": True,
            "data": order
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/order/{uuid}")
async def cancel_order(uuid: str):
    """주문 취소"""
    try:
        result = upbit_client.cancel_order(uuid)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

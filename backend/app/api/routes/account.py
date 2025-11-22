"""
계정 정보 및 잔고 API
"""
from fastapi import APIRouter
import pyupbit
from app.core.config import get_settings
from app.core.logging import get_logger

router = APIRouter()
settings = get_settings()
logger = get_logger(__name__)


@router.get("/balance")
def get_account_balance():
    """실시간 계정 잔고 조회"""
    try:
        upbit = pyupbit.Upbit(settings.upbit_access_key, settings.upbit_secret_key)
        balances = upbit.get_balances()
        krw_balance = float(upbit.get_balance("KRW") or 0)
        
        # 보유 코인 목록
        holdings = []
        total_asset_value = krw_balance
        
        for balance in balances:
            if balance['currency'] != 'KRW':
                ticker = f"KRW-{balance['currency']}"
                current_price = pyupbit.get_current_price(ticker)
                
                if current_price and isinstance(current_price, (int, float)):
                    amount = float(balance['balance'])
                    avg_buy_price = float(balance['avg_buy_price'])
                    current_value = amount * float(current_price)
                    total_asset_value += current_value
                    profit_loss = current_value - (amount * avg_buy_price)
                    profit_loss_rate = (profit_loss / (amount * avg_buy_price) * 100) if avg_buy_price > 0 else 0
                    
                    holdings.append({
                        "market": ticker,
                        "currency": balance['currency'],
                        "amount": amount,
                        "avg_buy_price": avg_buy_price,
                        "current_price": float(current_price),
                        "current_value": current_value,
                        "profit_loss": profit_loss,
                        "profit_loss_rate": profit_loss_rate
                    })
        
        return {
            "krw_balance": krw_balance,
            "total_asset_value": total_asset_value,
            "holdings": holdings,
            "total_positions": len(holdings)
        }
        
    except Exception as e:
        logger.error(f"Failed to get account balance: {e}")
        return {
            "krw_balance": 0,
            "total_asset_value": 0,
            "holdings": [],
            "total_positions": 0,
            "error": str(e)
        }

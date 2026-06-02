"""
계정 정보 및 잔고 API
"""
from fastapi import APIRouter
try:
    import pyupbit
except ImportError:  # pragma: no cover - deployment dependency guard
    pyupbit = None

from app.core.config import get_settings
from app.core.http_timeout import install_default_requests_timeout
from app.core.logging import get_logger

router = APIRouter()
settings = get_settings()
logger = get_logger(__name__)
install_default_requests_timeout()


@router.get("/balance")
def get_account_balance():
    """실시간 계정 잔고 조회"""
    try:
        if pyupbit is None:
            return {
                "total_krw": 0,
                "total_asset_value": 0,
                "holdings": [],
                "error": "pyupbit is not installed"
            }

        if not settings.upbit_access_key or not settings.upbit_secret_key:
            logger.warning("Upbit keys are missing.")
            return {
                "total_krw": 0,
                "total_asset_value": 0,
                "holdings": [],
                "error": "Upbit API keys are not configured"
            }

        upbit = pyupbit.Upbit(settings.upbit_access_key, settings.upbit_secret_key)
        balances = upbit.get_balances()
        
        # Upbit API 에러 처리 (IP 미등록 등)
        if hasattr(balances, 'get') and balances.get('error'):
            error_msg = balances.get('error')
            logger.error(f"Upbit API Error: {error_msg}")
            # 프론트엔드에서 처리할 수 있도록 구조화된 에러 반환 (500 대신 정상 응답 + 에러 플래그)
            return {
                "total_krw": 0,
                "total_asset_value": 0,
                "holdings": [],
                "api_error": error_msg
            }
            
        if not isinstance(balances, list):
             logger.error(f"Unexpected Upbit response type: {type(balances)} - {balances}")
             return {
                "total_krw": 0,
                "total_asset_value": 0,
                "holdings": [],
                "api_error": "Unexpected response from exchange"
            }
            
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


@router.get("/diagnostics")
def account_diagnostics():
    """Connectivity diagnostics for trading/balance failures.

    Surfaces the most common root causes (missing keys, IP not whitelisted,
    network errors) so the operator can tell server vs API vs code issues apart.
    """
    result = {
        "pyupbit_installed": pyupbit is not None,
        "keys_configured": bool(settings.upbit_access_key and settings.upbit_secret_key),
        "live_trading_enabled": settings.live_trading_enabled,
        "outbound_ip": None,
        "balance_ok": False,
        "error": None,
        "hint": None,
    }

    # Outbound IP — must match the IP whitelisted in the Upbit API console.
    try:
        import requests as _rq
        result["outbound_ip"] = _rq.get("https://api.ipify.org", timeout=5).text.strip()
    except Exception as exc:  # noqa
        result["outbound_ip"] = f"unknown ({exc})"

    if pyupbit is None:
        result["hint"] = "pyupbit is not installed on the server."
        return result
    if not result["keys_configured"]:
        result["hint"] = "Set UPBIT_ACCESS_KEY / UPBIT_SECRET_KEY in the server .env."
        return result

    try:
        upbit = pyupbit.Upbit(settings.upbit_access_key, settings.upbit_secret_key)
        balances = upbit.get_balances()
        if hasattr(balances, "get") and balances.get("error"):
            result["error"] = balances.get("error")
            result["hint"] = (
                "Upbit rejected the request. If 'no_authorization_ip', add the "
                f"server outbound IP ({result['outbound_ip']}) to the API key's "
                "allowed IP list in the Upbit console."
            )
        elif isinstance(balances, list):
            result["balance_ok"] = True
            result["hint"] = "Upbit API reachable and authorized."
        else:
            result["error"] = f"unexpected response: {type(balances).__name__}"
    except Exception as exc:  # noqa
        result["error"] = str(exc)
        result["hint"] = "Network/exchange error reaching Upbit from the server."
    return result

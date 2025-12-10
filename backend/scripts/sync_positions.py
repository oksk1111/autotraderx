#!/usr/bin/env python3
"""
Sync TradePosition with Upbit Balance
Upbit 계좌의 현재 보유 코인을 조회하여 DB의 TradePosition 테이블과 동기화합니다.
"""
import os
import sys
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import SessionLocal
from app.models.trading import TradePosition
import pyupbit
from app.core.config import get_settings

def sync_positions():
    settings = get_settings()
    db = SessionLocal()
    
    try:
        print("🔄 Upbit 계좌 정보 조회 중...")
        upbit = pyupbit.Upbit(settings.upbit_access_key, settings.upbit_secret_key)
        balances = upbit.get_balances()
        
        current_holdings = {}
        for b in balances:
            if b['currency'] == 'KRW':
                continue
            
            market = f"KRW-{b['currency']}"
            amount = float(b['balance'])
            avg_price = float(b['avg_buy_price'])
            
            if amount * avg_price > 5000:  # 5000원 이상만 취급
                current_holdings[market] = {
                    'amount': amount,
                    'avg_price': avg_price
                }
                print(f"💰 보유: {market} {amount} @ {avg_price:,.0f}원")

        # DB의 Open Position 조회
        db_positions = db.query(TradePosition).filter(TradePosition.status == "OPEN").all()
        db_markets = {p.market: p for p in db_positions}
        
        # 1. DB에 없는데 Upbit에 있는 경우 -> 추가
        for market, data in current_holdings.items():
            if market not in db_markets:
                print(f"➕ DB에 포지션 추가: {market}")
                pos = TradePosition(
                    market=market,
                    size=data['amount'],
                    entry_price=data['avg_price'],
                    stop_loss=data['avg_price'] * 0.97,  # -3% 손절
                    take_profit=data['avg_price'] * 1.05, # +5% 익절
                    status="OPEN"
                )
                db.add(pos)
        
        # 2. DB에 있는데 Upbit에 없는 경우 -> 종료 처리
        for market, pos in db_markets.items():
            if market not in current_holdings:
                print(f"➖ DB 포지션 종료 처리 (잔고 없음): {market}")
                pos.status = "CLOSED"
        
        db.commit()
        print("✅ 동기화 완료")
        
    except Exception as e:
        print(f"❌ 동기화 실패: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    sync_positions()

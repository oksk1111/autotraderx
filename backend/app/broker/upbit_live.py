"""UpbitLiveBroker — wraps pyupbit for real KRW market orders.

NO-OP unless settings.live_trading_enabled is True.
"""
from __future__ import annotations

import time
from typing import List, Optional

import pyupbit

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.marketdata import get_store
from app.models import TradePosition
from .base import Broker, Order, OrderSide, Position

logger = get_logger(__name__)


class UpbitLiveBroker:
    name = "live"

    def __init__(self):
        self.s = get_settings()
        self.store = get_store()
        self._client: Optional[pyupbit.Upbit] = None

    # ------------------------------------------------------------------ utils
    def _enabled(self) -> bool:
        return bool(self.s.live_trading_enabled and self.s.upbit_access_key and self.s.upbit_secret_key)

    def _upbit(self) -> Optional[pyupbit.Upbit]:
        if not self._enabled():
            return None
        if self._client is None:
            self._client = pyupbit.Upbit(self.s.upbit_access_key, self.s.upbit_secret_key)
        return self._client

    # --------------------------------------------------------------- interface
    def get_equity(self) -> float:
        u = self._upbit()
        if u is None:
            return 0.0
        try:
            balances = u.get_balances() or []
            if not isinstance(balances, list):
                return 0.0
            total = 0.0
            for b in balances:
                cur = b.get("currency")
                amt = float(b.get("balance", 0)) + float(b.get("locked", 0))
                if cur == "KRW":
                    total += amt
                else:
                    t = self.store.get_ticker(f"KRW-{cur}")
                    px = t.trade_price if t else float(b.get("avg_buy_price", 0) or 0)
                    total += amt * px
            return total
        except Exception as e:
            logger.warning("live get_equity failed: %s", e)
            return 0.0

    def get_position(self, market: str) -> Optional[Position]:
        db = SessionLocal()
        try:
            p = db.query(TradePosition).filter(
                TradePosition.market == market, TradePosition.status == "OPEN"
            ).first()
            if not p:
                return None
            return Position(market=p.market, qty=p.size, entry_price=p.entry_price,
                            stop_loss=p.stop_loss, take_profit=p.take_profit)
        finally:
            db.close()

    def list_positions(self) -> List[Position]:
        db = SessionLocal()
        try:
            rows = db.query(TradePosition).filter(TradePosition.status == "OPEN").all()
            return [Position(market=p.market, qty=p.size, entry_price=p.entry_price,
                             stop_loss=p.stop_loss, take_profit=p.take_profit) for p in rows]
        finally:
            db.close()

    def submit_market_buy(self, market: str, notional_krw: float, *,
                          stop_loss: float = 0.0, take_profit: float = 0.0,
                          strategy: str = "") -> Order:
        order = Order(side=OrderSide.BUY, market=market, requested_notional_krw=notional_krw, broker=self.name)
        if not self._enabled():
            order.error = "live disabled"
            return order
        u = self._upbit()
        if u is None:
            order.error = "no upbit client"
            return order
        notional_krw = max(notional_krw, 6000.0)
        try:
            res = u.buy_market_order(market, notional_krw)
            if not isinstance(res, dict) or "uuid" not in res:
                order.error = f"order rejected: {res}"
                return order
            # poll for fill (best-effort)
            time.sleep(0.7)
            try:
                detail = u.get_order(res["uuid"])
                trades = (detail or {}).get("trades") or []
                if trades:
                    total_qty = sum(float(t["volume"]) for t in trades)
                    total_funds = sum(float(t["funds"]) for t in trades)
                    avg_price = total_funds / total_qty if total_qty > 0 else 0.0
                else:
                    total_qty = 0.0
                    avg_price = 0.0
            except Exception:
                total_qty, avg_price = 0.0, 0.0
            if total_qty <= 0:
                t = self.store.get_ticker(market)
                avg_price = t.trade_price if t else 0.0
                total_qty = (notional_krw / avg_price) if avg_price > 0 else 0.0
            order.filled_qty = total_qty
            order.filled_price = avg_price
            order.filled_notional_krw = total_qty * avg_price
            order.success = total_qty > 0

            if order.success:
                db = SessionLocal()
                try:
                    pos = TradePosition(
                        market=market, size=total_qty, entry_price=avg_price,
                        stop_loss=stop_loss or avg_price * 0.98,
                        take_profit=take_profit or avg_price * 1.04,
                        status="OPEN",
                    )
                    db.add(pos); db.commit()
                finally:
                    db.close()
                logger.info("[live] BUY %s qty=%.6f @ %.2f", market, total_qty, avg_price)
            return order
        except Exception as e:
            order.error = f"exception: {e}"
            logger.exception("live buy failed: %s", e)
            return order

    def submit_market_sell(self, market: str, qty: float) -> Order:
        order = Order(side=OrderSide.SELL, market=market, requested_qty=qty, broker=self.name)
        if not self._enabled():
            order.error = "live disabled"
            return order
        u = self._upbit()
        if u is None:
            order.error = "no upbit client"
            return order
        try:
            res = u.sell_market_order(market, qty)
            if not isinstance(res, dict) or "uuid" not in res:
                order.error = f"order rejected: {res}"
                return order
            time.sleep(0.7)
            try:
                detail = u.get_order(res["uuid"])
                trades = (detail or {}).get("trades") or []
                total_qty = sum(float(t["volume"]) for t in trades) if trades else qty
                total_funds = sum(float(t["funds"]) for t in trades) if trades else 0.0
                avg_price = (total_funds / total_qty) if total_qty > 0 else 0.0
            except Exception:
                total_qty = qty
                t = self.store.get_ticker(market)
                avg_price = t.trade_price if t else 0.0
            order.filled_qty = total_qty
            order.filled_price = avg_price
            order.filled_notional_krw = total_qty * avg_price
            order.success = True

            db = SessionLocal()
            try:
                pos = db.query(TradePosition).filter(
                    TradePosition.market == market, TradePosition.status == "OPEN"
                ).first()
                if pos:
                    pos.status = "CLOSED"
                    db.commit()
            finally:
                db.close()
            logger.info("[live] SELL %s qty=%.6f @ %.2f", market, total_qty, avg_price)
            return order
        except Exception as e:
            order.error = f"exception: {e}"
            logger.exception("live sell failed: %s", e)
            return order

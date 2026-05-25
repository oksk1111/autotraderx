"""PaperBroker — in-memory broker that uses MarketDataStore as fill source.

Persistence: state mirrored to Postgres (`paper_account`, `paper_positions`) so
restarts don't wipe paper PnL.
"""
from __future__ import annotations

from typing import List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.marketdata import get_store
from app.models import PaperAccount, PaperPosition
from .base import Broker, Order, OrderSide, Position

logger = get_logger(__name__)


class PaperBroker:
    name = "paper"

    def __init__(self):
        self.s = get_settings()
        self.store = get_store()
        self._ensure_account()

    # -- persistence helpers --------------------------------------------------
    def _ensure_account(self) -> None:
        db = SessionLocal()
        try:
            acc = db.query(PaperAccount).first()
            if not acc:
                acc = PaperAccount(cash_krw=300_000.0, realized_pnl_krw=0.0)
                db.add(acc)
                db.commit()
        finally:
            db.close()

    def _load_account(self) -> PaperAccount:
        db = SessionLocal()
        try:
            acc = db.query(PaperAccount).first()
            if not acc:
                acc = PaperAccount(cash_krw=300_000.0)
                db.add(acc); db.commit(); db.refresh(acc)
            return acc
        finally:
            db.close()

    # -- broker interface -----------------------------------------------------
    def get_equity(self) -> float:
        db = SessionLocal()
        try:
            acc = db.query(PaperAccount).first()
            cash = acc.cash_krw if acc else 0.0
            positions = db.query(PaperPosition).filter(PaperPosition.status == "OPEN").all()
            mtm = 0.0
            for p in positions:
                t = self.store.get_ticker(p.market)
                px = t.trade_price if t else p.entry_price
                mtm += p.size * px
            return cash + mtm
        finally:
            db.close()

    def get_position(self, market: str) -> Optional[Position]:
        db = SessionLocal()
        try:
            p = db.query(PaperPosition).filter(
                PaperPosition.market == market, PaperPosition.status == "OPEN"
            ).first()
            if not p:
                return None
            return Position(market=p.market, qty=p.size, entry_price=p.entry_price,
                            stop_loss=p.stop_loss, take_profit=p.take_profit,
                            strategy=p.strategy)
        finally:
            db.close()

    def list_positions(self) -> List[Position]:
        db = SessionLocal()
        try:
            rows = db.query(PaperPosition).filter(PaperPosition.status == "OPEN").all()
            return [Position(market=p.market, qty=p.size, entry_price=p.entry_price,
                             stop_loss=p.stop_loss, take_profit=p.take_profit,
                             strategy=p.strategy) for p in rows]
        finally:
            db.close()

    def _fill_price(self, market: str, side: OrderSide) -> float:
        ob = self.store.get_orderbook(market)
        t = self.store.get_ticker(market)
        if ob and ob.units:
            u = ob.units[0]
            if side == OrderSide.BUY:
                base = u.ask_price
            else:
                base = u.bid_price
        else:
            base = t.trade_price if t else 0.0
        # add 0.05% slippage
        slip = self.s.slippage_est
        if side == OrderSide.BUY:
            return base * (1.0 + slip)
        return base * (1.0 - slip)

    def submit_market_buy(self, market: str, notional_krw: float, *,
                          stop_loss: float = 0.0, take_profit: float = 0.0,
                          strategy: str = "") -> Order:
        order = Order(side=OrderSide.BUY, market=market, requested_notional_krw=notional_krw, broker=self.name)
        if notional_krw <= 0:
            order.error = "notional<=0"
            return order
        price = self._fill_price(market, OrderSide.BUY)
        if price <= 0:
            order.error = "no price"
            return order
        fee = notional_krw * self.s.fee_rate
        spend = notional_krw + fee
        db = SessionLocal()
        try:
            acc = db.query(PaperAccount).first()
            if not acc or acc.cash_krw < spend:
                order.error = "insufficient cash (paper)"
                return order
            qty = notional_krw / price
            acc.cash_krw -= spend
            pos = PaperPosition(
                market=market, size=qty, entry_price=price,
                stop_loss=stop_loss, take_profit=take_profit,
                strategy=strategy, status="OPEN",
            )
            db.add(pos); db.commit()
            order.filled_qty = qty
            order.filled_price = price
            order.filled_notional_krw = notional_krw
            order.success = True
            logger.info("[paper] BUY %s qty=%.6f @ %.2f notional=%.0f fee=%.0f",
                        market, qty, price, notional_krw, fee)
            return order
        finally:
            db.close()

    def submit_market_sell(self, market: str, qty: float) -> Order:
        order = Order(side=OrderSide.SELL, market=market, requested_qty=qty, broker=self.name)
        price = self._fill_price(market, OrderSide.SELL)
        if price <= 0:
            order.error = "no price"
            return order
        db = SessionLocal()
        try:
            pos = db.query(PaperPosition).filter(
                PaperPosition.market == market, PaperPosition.status == "OPEN"
            ).first()
            if not pos:
                order.error = "no open position"
                return order
            qty = min(qty, pos.size)
            gross = qty * price
            fee = gross * self.s.fee_rate
            net = gross - fee
            pnl = (price - pos.entry_price) * qty - fee
            acc = db.query(PaperAccount).first()
            if acc:
                acc.cash_krw += net
                acc.realized_pnl_krw += pnl
            pos.size -= qty
            if pos.size <= 1e-12:
                pos.status = "CLOSED"
                pos.closed_price = price
                pos.closed_pnl_krw = pnl
            db.commit()
            order.filled_qty = qty
            order.filled_price = price
            order.filled_notional_krw = gross
            order.success = True
            logger.info("[paper] SELL %s qty=%.6f @ %.2f pnl=%.0f", market, qty, price, pnl)
            return order
        finally:
            db.close()

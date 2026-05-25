"""Event-driven bar-by-bar backtester.

Usage:
  python -m app.backtest.backtester --markets KRW-BTC,KRW-ETH --days 90 --strategy auto

CSV format expected:
  data/raw/KRW_BTC_minute1.csv  (or fallback to minute5 → resampled)
  columns: timestamp_utc, open, high, low, close, volume
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.marketdata.candles import Candle
from app.strategy import (
    MeanReversionStrategy, Regime, RegimeClassifier, TrendFollowingStrategy,
)
from .metrics import compute_metrics

logger = get_logger(__name__)


@dataclass
class BTPosition:
    market: str
    qty: float
    entry_price: float
    entry_bar: int
    stop: float
    target: float
    strategy: str


@dataclass
class BacktestResult:
    market: str
    equity_curve: List[float] = field(default_factory=list)
    trade_pnls: List[float] = field(default_factory=list)
    hold_bars: List[float] = field(default_factory=list)
    metrics: Optional[dict] = None


def _load_csv(path: Path, market: str) -> List[Candle]:
    if not path.exists():
        return []
    candles: List[Candle] = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ts = dt.datetime.fromisoformat(row.get("timestamp_utc") or row.get("datetime") or row["timestamp"])
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=dt.timezone.utc)
                candles.append(Candle(
                    market=market, timeframe="1m",
                    open_time_ms=int(ts.timestamp() * 1000),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume") or row.get("Volume") or 0.0),
                    closed=True,
                ))
            except Exception as e:
                logger.debug("skip row: %s", e)
                continue
    candles.sort(key=lambda c: c.open_time_ms)
    return candles


def _resample(candles: List[Candle], tf_minutes: int, market: str, tf_name: str) -> List[Candle]:
    if not candles:
        return []
    out: List[Candle] = []
    bucket_ms = tf_minutes * 60 * 1000
    cur: Optional[Candle] = None
    for c in candles:
        bucket = (c.open_time_ms // bucket_ms) * bucket_ms
        if cur is None or cur.open_time_ms != bucket:
            if cur is not None:
                cur.closed = True
                out.append(cur)
            cur = Candle(
                market=market, timeframe=tf_name, open_time_ms=bucket,
                open=c.open, high=c.high, low=c.low, close=c.close,
                volume=c.volume, closed=False,
            )
        else:
            cur.high = max(cur.high, c.high)
            cur.low = min(cur.low, c.low)
            cur.close = c.close
            cur.volume += c.volume
    if cur is not None:
        cur.closed = True
        out.append(cur)
    return out


class Backtester:
    def __init__(self, strategy_mode: str = "auto"):
        self.s = get_settings()
        self.strategy_mode = strategy_mode
        self.classifier = RegimeClassifier()
        self.trend = TrendFollowingStrategy()
        self.range = MeanReversionStrategy()

    def run_market(self, candles_1m: List[Candle], market: str, days: int) -> BacktestResult:
        if not candles_1m:
            return BacktestResult(market=market)
        # truncate to last N days
        cutoff_ms = int((dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).timestamp() * 1000)
        candles_1m = [c for c in candles_1m if c.open_time_ms >= cutoff_ms]
        candles_5m = _resample(candles_1m, 5, market, "5m")
        candles_15m = _resample(candles_1m, 15, market, "15m")

        equity = 1_000_000.0  # 1M KRW notional for backtest
        equity0 = equity
        result = BacktestResult(market=market)
        pos: Optional[BTPosition] = None

        fee = self.s.fee_rate
        slip = self.s.slippage_est

        # main loop on 1m bars; strategies read 5m via shared lookahead-safe slicing
        for i in range(60, len(candles_1m)):
            sub_1m = candles_1m[max(0, i - 240): i + 1]
            # find 5m / 15m subsets up to this bar's time
            t_ms = candles_1m[i].open_time_ms
            sub_5m = [c for c in candles_5m if c.open_time_ms <= t_ms][-200:]
            sub_15m = [c for c in candles_15m if c.open_time_ms <= t_ms][-200:]

            bar = candles_1m[i]
            mtm = pos.qty * bar.close if pos else 0.0
            equity_now = equity + (mtm - (pos.qty * pos.entry_price) if pos else 0.0)
            result.equity_curve.append(equity_now)

            # manage open position
            if pos is not None:
                exit_reason = ""
                if bar.low <= pos.stop:
                    exit_price = pos.stop * (1.0 - slip)
                    exit_reason = "stop"
                elif bar.high >= pos.target:
                    exit_price = pos.target * (1.0 - slip)
                    exit_reason = "target"
                elif pos.strategy == "trend_following" and (i - pos.entry_bar) > 48:  # 240m @ 5m = 48 bars; we use 1m so 240 bars
                    exit_price = bar.close * (1.0 - slip)
                    exit_reason = "time"
                elif pos.strategy == "mean_reversion" and (i - pos.entry_bar) > 90:
                    exit_price = bar.close * (1.0 - slip)
                    exit_reason = "time"
                if exit_reason:
                    gross = pos.qty * exit_price
                    cost = gross * fee
                    pnl = (exit_price - pos.entry_price) * pos.qty - cost - (pos.qty * pos.entry_price * fee)
                    equity += gross - cost
                    result.trade_pnls.append(pnl)
                    result.hold_bars.append(i - pos.entry_bar)
                    pos = None

            # new entry?
            if pos is None and equity > 0:
                reading = self.classifier.classify(sub_1m)
                chosen = None
                if self.strategy_mode == "auto":
                    if reading.regime == Regime.TREND:
                        chosen = self.trend
                    elif reading.regime == Regime.RANGE:
                        chosen = self.range
                elif self.strategy_mode == "trend":
                    chosen = self.trend
                elif self.strategy_mode == "range":
                    chosen = self.range
                if chosen is None:
                    continue
                sig = chosen.evaluate(market, sub_1m, sub_5m, sub_15m)
                if sig.action != "BUY" or sig.stop_price <= 0:
                    continue
                price = bar.close * (1.0 + slip)
                stop_dist = price - sig.stop_price
                if stop_dist <= 0:
                    continue
                risk_krw = equity * self.s.risk_per_trade
                qty = risk_krw / stop_dist
                notional = qty * price
                cap = equity * self.s.max_position_ratio
                if notional > cap:
                    notional = cap
                    qty = notional / price
                if notional < 6000:
                    continue
                fee_cost = notional * fee
                if equity < notional + fee_cost:
                    continue
                equity -= notional + fee_cost
                pos = BTPosition(
                    market=market, qty=qty, entry_price=price, entry_bar=i,
                    stop=sig.stop_price, target=sig.target_price, strategy=sig.strategy,
                )

        # finalize open position at last price
        if pos is not None:
            last = candles_1m[-1].close * (1.0 - slip)
            gross = pos.qty * last
            equity += gross - gross * fee
            pnl = (last - pos.entry_price) * pos.qty
            result.trade_pnls.append(pnl)
            result.hold_bars.append(len(candles_1m) - 1 - pos.entry_bar)

        if result.equity_curve:
            result.equity_curve.append(equity)
        metrics = compute_metrics(result.equity_curve, result.trade_pnls,
                                  [b for b in result.hold_bars])
        result.metrics = metrics.as_dict()
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description="AutoTraderX v5 backtester")
    parser.add_argument("--markets", default="KRW-BTC", help="comma separated")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--strategy", default="auto", choices=["auto", "trend", "range"])
    parser.add_argument("--data-dir", default=None)
    args = parser.parse_args()

    settings = get_settings()
    base = Path(args.data_dir or settings.backtest_data_dir)
    if not base.is_absolute():
        base = Path(__file__).resolve().parents[3] / base

    bt = Backtester(strategy_mode=args.strategy)
    out: Dict[str, dict] = {}
    for market in args.markets.split(","):
        market = market.strip()
        path = base / f"{market.replace('-', '_')}_minute1.csv"
        candles = _load_csv(path, market)
        if not candles:
            path5 = base / f"{market.replace('-', '_')}_minute5.csv"
            candles_5 = _load_csv(path5, market)
            if candles_5:
                # treat 5m as 1m proxy (worse resolution but works for smoke)
                candles = candles_5
        if not candles:
            logger.warning("no data for %s at %s", market, path)
            out[market] = {"error": f"no data at {path}"}
            continue
        res = bt.run_market(candles, market, args.days)
        out[market] = res.metrics or {}
        logger.info("%s metrics: %s", market, json.dumps(res.metrics, indent=2))

    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

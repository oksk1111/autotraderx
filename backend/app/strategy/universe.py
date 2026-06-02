"""Dynamic universe selection (v7.0) — cross-sectional momentum + liquidity.

Crypto is not a fixed-portfolio market: leadership rotates quickly. Instead of
hard-coding KRW-BTC / KRW-ETH, the engine periodically scans *all* KRW markets
on Upbit and keeps a short list of the most "promising" coins, defined as:

  1. Liquid enough to enter/exit cleanly  (24h traded value >= floor)
  2. Strong but not blown-off momentum     (positive 24h return, capped)
  3. Ranked cross-sectionally               (top-N by a blended score)

The network fetch (`select`) is intentionally thin; the ranking math lives in
`rank_candidates`, a pure function that is unit-tested without any I/O.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import requests

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_UPBIT_MARKET_ALL = "https://api.upbit.com/v1/market/all"
_UPBIT_TICKER = "https://api.upbit.com/v1/ticker"

# Stablecoins / wrapped assets we never want to "momentum trade".
_DEFAULT_BLACKLIST = {"KRW-USDT", "KRW-USDC", "KRW-DAI", "KRW-BUSD", "KRW-TUSD"}


@dataclass
class UniverseCandidate:
    market: str
    price: float
    change_rate_24h: float
    value_24h: float
    score: float


def rank_candidates(
    tickers: Sequence[Dict],
    *,
    min_value_24h: float,
    size: int,
    always_include: Sequence[str] = (),
    exclude: Sequence[str] = (),
    max_change_24h: float = 0.30,
) -> List[str]:
    """Pure ranking of Upbit ticker dicts into a target market list.

    Each ticker dict is expected to expose ``market``, ``signed_change_rate``
    and ``acc_trade_price_24h`` (the standard Upbit /v1/ticker fields).

    Selection rules:
      * Drop non-KRW, blacklisted and explicitly excluded markets.
      * Require 24h traded value >= ``min_value_24h`` (liquidity floor).
      * Drop blown-off names (24h change > ``max_change_24h``) to avoid
        buying euphoric tops.
      * Score = 24h momentum + a small liquidity bonus; rank descending.
      * ``always_include`` anchors are prepended (if they clear liquidity).
    """
    exclude_set = {m.upper() for m in exclude} | _DEFAULT_BLACKLIST
    anchors = [m for m in always_include]

    scored: List[UniverseCandidate] = []
    for t in tickers:
        market = str(t.get("market", ""))
        if not market.startswith("KRW-"):
            continue
        if market.upper() in exclude_set:
            continue
        value_24h = float(t.get("acc_trade_price_24h", 0.0) or 0.0)
        if value_24h < min_value_24h:
            continue
        change = float(t.get("signed_change_rate", 0.0) or 0.0)
        if change > max_change_24h:
            continue  # overheated / reversal risk
        # Blended score: momentum dominates, liquidity is a gentle tiebreaker.
        liq_bonus = math.log10(max(value_24h, 1.0)) / 100.0
        score = change + liq_bonus
        scored.append(UniverseCandidate(
            market=market,
            price=float(t.get("trade_price", 0.0) or 0.0),
            change_rate_24h=change,
            value_24h=value_24h,
            score=score,
        ))

    scored.sort(key=lambda c: c.score, reverse=True)

    # Anchors first (dedup), then fill with top momentum names up to `size`.
    result: List[str] = []
    liquid_markets = {c.market for c in scored}
    for a in anchors:
        if a in liquid_markets and a not in result:
            result.append(a)
    for c in scored:
        if len(result) >= max(size, len(result)):
            pass
        if c.market not in result:
            result.append(c.market)
        if len(result) >= size:
            break
    return result[:size] if size > 0 else result


class UniverseSelector:
    """Fetches Upbit market data and selects the active universe."""

    def __init__(self, settings=None, session: Optional[requests.Session] = None):
        self.s = settings or get_settings()
        self._session = session or requests.Session()
        self._cache: List[str] = []
        self._cache_ts: float = 0.0

    # ----------------------------------------------------------------- fetchers
    def _fetch_krw_markets(self) -> List[str]:
        try:
            resp = self._session.get(_UPBIT_MARKET_ALL, params={"isDetails": "false"}, timeout=10)
            data = resp.json()
        except Exception as exc:  # noqa
            logger.warning("universe market/all fetch failed: %s", exc)
            return []
        if not isinstance(data, list):
            return []
        return [row["market"] for row in data
                if isinstance(row, dict) and str(row.get("market", "")).startswith("KRW-")]

    def _fetch_tickers(self, markets: List[str]) -> List[Dict]:
        out: List[Dict] = []
        # Upbit allows comma-separated batches; chunk to stay within URL limits.
        for i in range(0, len(markets), 100):
            chunk = markets[i:i + 100]
            try:
                resp = self._session.get(
                    _UPBIT_TICKER, params={"markets": ",".join(chunk)}, timeout=10
                )
                data = resp.json()
            except Exception as exc:  # noqa
                logger.warning("universe ticker fetch failed: %s", exc)
                continue
            if isinstance(data, list):
                out.extend(d for d in data if isinstance(d, dict))
        return out

    # ------------------------------------------------------------------- select
    def select(self, force: bool = False) -> List[str]:
        """Return the target active universe (cached for refresh interval)."""
        now = time.time()
        ttl = max(int(self.s.universe_refresh_sec), 60)
        if not force and self._cache and (now - self._cache_ts) < ttl:
            return self._cache

        markets = self._fetch_krw_markets()
        if not markets:
            return self._cache or list(self.s.tracked_markets)
        tickers = self._fetch_tickers(markets)
        if not tickers:
            return self._cache or list(self.s.tracked_markets)

        selected = rank_candidates(
            tickers,
            min_value_24h=self.s.universe_min_value_24h,
            size=self.s.universe_size,
            always_include=self.s.universe_always_include,
            exclude=self.s.universe_exclude,
        )
        if not selected:
            # Liquidity floor too high or API hiccup — keep anchors at minimum.
            selected = list(self.s.universe_always_include) or list(self.s.tracked_markets)
        self._cache = selected
        self._cache_ts = now
        logger.info("universe selected (%d): %s", len(selected), selected)
        return selected

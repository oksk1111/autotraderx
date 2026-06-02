"""Tests for the v7.0 dynamic universe selection and active-market registry."""
import pytest

from app.marketdata.active import ActiveMarketRegistry
from app.strategy.universe import rank_candidates, UniverseSelector


def _ticker(market, change, value):
    return {"market": market, "signed_change_rate": change, "acc_trade_price_24h": value, "trade_price": 100.0}


def test_rank_filters_low_liquidity():
    tickers = [
        _ticker("KRW-BTC", 0.01, 100_000_000_000),
        _ticker("KRW-XYZ", 0.20, 1_000_000_000),  # below liquidity floor
    ]
    result = rank_candidates(tickers, min_value_24h=30_000_000_000, size=5)
    assert "KRW-BTC" in result
    assert "KRW-XYZ" not in result


def test_rank_excludes_stablecoins_and_overheated():
    tickers = [
        _ticker("KRW-USDT", 0.001, 500_000_000_000),  # stablecoin -> excluded
        _ticker("KRW-DOGE", 0.50, 80_000_000_000),    # +50% overheated -> excluded
        _ticker("KRW-SOL", 0.08, 90_000_000_000),     # healthy momentum
    ]
    result = rank_candidates(tickers, min_value_24h=30_000_000_000, size=5)
    assert "KRW-USDT" not in result
    assert "KRW-DOGE" not in result
    assert "KRW-SOL" in result


def test_rank_orders_by_momentum_and_caps_size():
    tickers = [
        _ticker("KRW-A", 0.02, 50_000_000_000),
        _ticker("KRW-B", 0.10, 50_000_000_000),
        _ticker("KRW-C", 0.05, 50_000_000_000),
        _ticker("KRW-D", 0.01, 50_000_000_000),
    ]
    result = rank_candidates(tickers, min_value_24h=30_000_000_000, size=2)
    assert len(result) == 2
    assert result[0] == "KRW-B"  # strongest momentum first


def test_rank_always_include_anchor():
    tickers = [
        _ticker("KRW-BTC", -0.02, 200_000_000_000),  # weak momentum but anchor
        _ticker("KRW-B", 0.10, 50_000_000_000),
        _ticker("KRW-C", 0.08, 50_000_000_000),
    ]
    result = rank_candidates(
        tickers, min_value_24h=30_000_000_000, size=3, always_include=["KRW-BTC"]
    )
    assert "KRW-BTC" in result


def test_registry_versioning():
    reg = ActiveMarketRegistry(["KRW-BTC"])
    assert reg.get() == ["KRW-BTC"]
    assert reg.version == 0
    # No-op set returns False, version unchanged
    assert reg.set(["KRW-BTC"]) is False
    assert reg.version == 0
    # Real change bumps version
    assert reg.set(["KRW-BTC", "KRW-ETH"]) is True
    assert reg.version == 1
    assert reg.get() == ["KRW-BTC", "KRW-ETH"]


def test_registry_dedupes():
    reg = ActiveMarketRegistry()
    reg.set(["KRW-BTC", "KRW-BTC", "KRW-ETH", ""])
    assert reg.get() == ["KRW-BTC", "KRW-ETH"]


def test_selector_uses_cache(monkeypatch):
    selector = UniverseSelector()
    calls = {"n": 0}

    def fake_fetch_markets():
        calls["n"] += 1
        return ["KRW-BTC", "KRW-ETH", "KRW-SOL"]

    def fake_fetch_tickers(markets):
        return [_ticker(m, 0.05, 100_000_000_000) for m in markets]

    monkeypatch.setattr(selector, "_fetch_krw_markets", fake_fetch_markets)
    monkeypatch.setattr(selector, "_fetch_tickers", fake_fetch_tickers)

    first = selector.select(force=True)
    second = selector.select()  # cached -> no new fetch
    assert first == second
    assert calls["n"] == 1


def test_engine_iterates_dynamic_markets(monkeypatch):
    """evaluate_all must sweep the dynamic registry, not the static config list."""
    import app.engine.trading_engine as te

    visited = []
    monkeypatch.setattr(te, "get_active_markets", lambda: ["KRW-SOL", "KRW-XRP"])

    engine = te.TradingEngine.__new__(te.TradingEngine)  # skip heavy __init__
    engine.evaluate_market = lambda m: visited.append(m)
    engine._snapshot_shadow = lambda: None
    engine._reset_daily_if_needed = lambda: None

    te.TradingEngine.evaluate_all(engine)
    assert visited == ["KRW-SOL", "KRW-XRP"]


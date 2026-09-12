from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from crypto_market_intel.config import Settings
from crypto_market_intel.types import Bar, Instrument, Ticker, Trade


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("CONTRACT_VERSION", "HM_CRYPTO_V1")
    monkeypatch.setenv("TRADING_ENV", "DEMO")
    monkeypatch.setenv("MARKET_MODE", "DERIVATIVES")
    monkeypatch.setenv("BREAKOUT_PERCENT_WINDOWS_SEC", "30,60")
    monkeypatch.setenv("BREAKOUT_PERCENT_THRESHOLDS", "0.5,1.0")
    monkeypatch.setenv("BREAKOUT_MIN_PRELIM_SCORE", "0.60")
    return Settings.from_env()


def dt(sec: int) -> datetime:
    return datetime.fromtimestamp(sec, tz=timezone.utc)


def trade(sec: int, price: str, qty: str, side: str, symbol: str = "BTCUSDT") -> Trade:
    return Trade(symbol, dt(sec), Decimal(price), Decimal(qty), side)


def bar(sec: int, o: str, h: str, l: str, c: str, v: str = "10") -> Bar:
    start = dt(sec)
    return Bar(start, dt(sec + 60), Decimal(o), Decimal(h), Decimal(l), Decimal(c), Decimal(v), Decimal(v) * Decimal(c))


def instrument(symbol: str, quote: str = "USDT", launch_sec: int = 1) -> Instrument:
    return Instrument(symbol, symbol.removesuffix(quote), quote, "Trading", dt(launch_sec), Decimal("0.01"), Decimal("0.001"), Decimal("0.001"), Decimal("5"), False, None, {})


def ticker(symbol: str, pct: str, turnover: str, volume: str = "10") -> Ticker:
    return Ticker(symbol, Decimal("100"), Decimal(pct), Decimal(volume), Decimal(turnover), Decimal("99"), Decimal("101"), Decimal("100"), Decimal("100"), Decimal("0.0001"), None, {})

from __future__ import annotations

from datetime import datetime, timezone

from crypto_market_intel.scanner import rank_universe
from conftest import instrument, ticker


def test_scanner_ranks_gainers_losers_and_turnover(settings) -> None:
    instruments = [instrument("AAAUSDT"), instrument("BBBUSDT"), instrument("CCCUSDT"), instrument("DDDUSDT")]
    tickers = [ticker("AAAUSDT", "0.10", "100"), ticker("BBBUSDT", "-0.20", "500"), ticker("CCCUSDT", "0.30", "300"), ticker("DDDUSDT", "-0.05", "1000")]
    result = rank_universe(instruments, tickers, settings, datetime(2026, 9, 12, tzinfo=timezone.utc))
    assert result.gainers[:2] == ("CCCUSDT", "AAAUSDT")
    assert result.losers[:2] == ("BBBUSDT", "DDDUSDT")
    assert result.highest_turnover[:2] == ("DDDUSDT", "BBBUSDT")
    assert len(result.promoted) == len(set(result.promoted))

from __future__ import annotations

import os

import pytest

from crypto_market_intel.bybit import BybitV5PublicAdapter
from crypto_market_intel.config import Settings


@pytest.mark.live
def test_opt_in_bybit_public_ticker_smoke() -> None:
    if os.getenv("RUN_LIVE_BYBIT_SMOKE") != "1":
        pytest.skip("opt-in only: set RUN_LIVE_BYBIT_SMOKE=1")
    adapter = BybitV5PublicAdapter(Settings.from_env())
    try:
        rows = adapter.tickers()
        assert rows
        assert all(row.symbol and row.last_price > 0 for row in rows[:10])
    finally:
        adapter.close()

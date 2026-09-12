from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from crypto_market_intel.contracts.models import DataQuality, MarketMode
from crypto_market_intel.quality import SourceFreshness, assess_data_quality
from crypto_market_intel.regime import classify_regime
from crypto_market_intel.snapshot import derivatives_context
from conftest import bar


def test_balance_detector_distinguishes_range_from_trend() -> None:
    ranging = [bar(1000+i*60, "100", "102", "98", "100.5" if i%2==0 else "99.5") for i in range(20)]
    trend = [bar(3000+i*60, str(100+i*2), str(102+i*2), str(100+i*2), str(101.8+i*2)) for i in range(20)]
    range_result = classify_regime(ranging)
    trend_result = classify_regime(trend)
    assert range_result["type"].value in {"BALANCE", "RANGE"}
    assert trend_result["type"].value == "TREND_EXPANSION"


def test_data_freshness_good_stale_invalid() -> None:
    now = datetime(2026,9,12,tzinfo=timezone.utc)
    good, reasons = assess_data_quality([SourceFreshness("trades", now-timedelta(seconds=1), 5000)], now=now)
    assert good == DataQuality.GOOD and not reasons
    stale, _ = assess_data_quality([SourceFreshness("trades", now-timedelta(seconds=10), 5000)], now=now)
    assert stale == DataQuality.STALE
    invalid, reasons = assess_data_quality([SourceFreshness("orderbook", now, 5000)], sequence_gap=True, orderbook_valid=False, now=now)
    assert invalid == DataQuality.INVALID
    assert "orderbook_sequence_gap" in reasons


def test_spot_derivatives_context_is_null_not_fake_zero() -> None:
    ctx = derivatives_context(MarketMode.SPOT, {}, None, None)
    assert ctx is not None
    assert ctx["mark_price"] is None
    assert ctx["open_interest"] is None
    assert ctx["funding_rate"] is None
    assert ctx["liquidation_intensity"] is None
    assert ctx["availability"]["derivatives_context"] is False

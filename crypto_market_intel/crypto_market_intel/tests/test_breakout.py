from __future__ import annotations

from decimal import Decimal

from crypto_market_intel.breakout import GlobalBreakoutScout
from conftest import dt


def test_percentage_breakout_promotes_to_deep_watch(settings) -> None:
    scout = GlobalBreakoutScout(settings)
    scout.ingest("BTCUSDT", Decimal("100"), Decimal("10"), dt(1000))
    scout.ingest("BTCUSDT", Decimal("100.1"), Decimal("10"), dt(1015))
    alerts = scout.ingest("BTCUSDT", Decimal("101"), Decimal("40"), dt(1030))
    assert any(a.detector_type == "PERCENT_ACCELERATION" and a.direction.value == "LONG" for a in alerts)
    assert all(len(a.snapshot_id) == 32 for a in alerts)
    assert scout.watch_registry.is_watched("BTCUSDT", dt(1031))


def test_major_structure_break_fixture(settings) -> None:
    scout = GlobalBreakoutScout(settings)
    scout.update_structure("ETHUSDT", Decimal("2000"), Decimal("1800"), Decimal("0.8"))
    scout.ingest("ETHUSDT", Decimal("1990"), Decimal("10"), dt(1000))
    alerts = scout.ingest("ETHUSDT", Decimal("2010"), Decimal("10"), dt(1001))
    assert any(a.detector_type == "MAJOR_STRUCTURE_BREAK" for a in alerts)
    assert scout.watch_registry.is_watched("ETHUSDT", dt(1002))


def test_range_key_level_and_trendline_breaks(settings) -> None:
    scout = GlobalBreakoutScout(settings)
    scout.update_breakout_context("SOLUSDT", range_high=Decimal("110"), range_low=Decimal("90"), key_levels=(Decimal("105"),), trendlines=((Decimal("0"), Decimal("108")),))
    scout.ingest("SOLUSDT", Decimal("104"), Decimal("10"), dt(1000))
    alerts = scout.ingest("SOLUSDT", Decimal("111"), Decimal("20"), dt(1001))
    kinds = {a.detector_type for a in alerts}
    assert {"RANGE_BREAK", "KEY_LEVEL_BREAK", "TRENDLINE_BREAK"}.issubset(kinds)

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from crypto_market_intel.breakout import GlobalBreakoutScout
from crypto_market_intel.engine import MarketIntelEngine
from crypto_market_intel.storage import LocalArchive


class _NoNetworkAdapter:
    pass


def test_archive_survives_restart(tmp_path: Path) -> None:
    event = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
    first = LocalArchive(tmp_path)
    first.append("features", event, "BTCUSDT", {"state":"GOOD"})
    first.close()
    second = LocalArchive(tmp_path)
    try:
        rows = list(second.replay("features", "BTCUSDT"))
        assert len(rows) == 1 and rows[0]["payload"]["state"] == "GOOD"
    finally:
        second.close()


def test_deep_topics_are_only_for_promoted_symbols(settings) -> None:
    engine = MarketIntelEngine(settings, adapter=_NoNetworkAdapter())  # type: ignore[arg-type]
    engine.scout.watch_registry.promote("BTCUSDT", datetime(2099,1,1,tzinfo=timezone.utc), "breakout")
    topics = engine.deep_public_topics(datetime(2026,9,12,tzinfo=timezone.utc))
    assert "publicTrade.BTCUSDT" in topics
    assert "orderbook.50.BTCUSDT" in topics
    assert "allLiquidation.BTCUSDT" in topics
    assert all("ETHUSDT" not in topic for topic in topics)

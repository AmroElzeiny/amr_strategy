from __future__ import annotations

from datetime import datetime, timezone

from crypto_market_intel.storage import LocalArchive


def test_local_replay_is_readable_and_ordered(tmp_path) -> None:
    archive = LocalArchive(tmp_path)
    try:
        archive.append("public_trades", datetime(2026,9,12,10,0,1,tzinfo=timezone.utc), "BTCUSDT", {"price":"101","side":"Buy"})
        archive.append("public_trades", datetime(2026,9,12,10,0,2,tzinfo=timezone.utc), "BTCUSDT", {"price":"102","side":"Sell"})
        rows = list(archive.replay("public_trades", "BTCUSDT"))
        assert [r["payload"]["price"] for r in rows] == ["101","102"]
    finally:
        archive.close()

from __future__ import annotations

from pathlib import Path

import pytest

from crypto_market_intel.orderbook import SequenceGapError
from crypto_market_intel.storage import LocalArchive
from crypto_market_intel.stream_state import DeepMarketStreamState


def test_stream_state_archives_real_trade_and_orderbook_delta(tmp_path: Path) -> None:
    archive = LocalArchive(tmp_path)
    state = DeepMarketStreamState("BTCUSDT", orderbook_stale_ms=3000, archive=archive)
    try:
        state.process({
            "topic": "orderbook.50.BTCUSDT", "type": "snapshot", "ts": 1000, "cts": 1000,
            "data": {"u": 10, "seq": 20, "b": [["100", "2"]], "a": [["101", "3"]]},
        })
        state.process({
            "topic": "orderbook.50.BTCUSDT", "type": "delta", "ts": 1100, "cts": 1100,
            "data": {"u": 11, "seq": 21, "b": [["100", "4"]], "a": [["101", "0"], ["102", "1"]]},
        })
        state.process({
            "topic": "publicTrade.BTCUSDT", "ts": 1200,
            "data": [{"T": 1200, "s": "BTCUSDT", "S": "Buy", "v": "0.5", "p": "101.5", "i": "t1"}],
        })
        assert state.orderbook.bids[state.orderbook.metrics().best_bid] == 4
        assert state.recent_trades()[0].taker_side == "Buy"
        archived_book = list(archive.replay("orderbook", "BTCUSDT"))
        assert len(archived_book) == 2
        assert archived_book[-1]["payload"]["stream_message"]["type"] == "delta"
    finally:
        archive.close()


def test_reconnect_forces_orderbook_resync() -> None:
    state = DeepMarketStreamState("BTCUSDT", orderbook_stale_ms=3000)
    state.process({
        "topic": "orderbook.50.BTCUSDT", "type": "snapshot", "ts": 1000,
        "data": {"u": 10, "seq": 20, "b": [["100", "2"]], "a": [["101", "3"]]},
    })
    state.mark_reconnect()
    assert state.orderbook.needs_resync is True
    assert state.orderbook.diagnostic()["needs_resync"] is True
    with pytest.raises(SequenceGapError):
        state.process({
            "topic": "orderbook.50.BTCUSDT", "type": "delta", "ts": 1200,
            "data": {"u": 12, "seq": 22, "b": [["100", "3"]], "a": []},
        })

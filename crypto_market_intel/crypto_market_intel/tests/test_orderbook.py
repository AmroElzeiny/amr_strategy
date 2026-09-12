from __future__ import annotations

from decimal import Decimal

import pytest

from crypto_market_intel.orderbook import LocalOrderBook, SequenceGapError


def test_snapshot_delta_reconstruction_and_reset() -> None:
    book = LocalOrderBook(stale_ms=5000)
    book.apply_message({"type":"snapshot","ts":1000,"data":{"u":10,"seq":100,"b":[["100","2"],["99","5"]],"a":[["101","3"],["102","4"]]}})
    book.apply_message({"type":"delta","ts":1100,"data":{"u":11,"seq":101,"b":[["100","3"],["99","0"]],"a":[["101","2"],["103","7"]]}})
    assert book.bids == {Decimal("100"): Decimal("3")}
    assert book.asks[Decimal("103")] == Decimal("7")
    assert book.metrics().best_bid == Decimal("100")
    book.apply_message({"type":"snapshot","ts":1200,"data":{"u":20,"seq":200,"b":[["98","1"]],"a":[["99","1"]]}})
    assert set(book.bids) == {Decimal("98")}


def test_sequence_regression_marks_degraded_resync_required() -> None:
    book = LocalOrderBook()
    book.apply_message({"type":"snapshot","ts":1000,"data":{"u":10,"seq":100,"b":[["100","2"]],"a":[["101","3"]]}})
    with pytest.raises(SequenceGapError):
        book.apply_message({"type":"delta","ts":1100,"data":{"u":9,"seq":99,"b":[],"a":[]}})
    assert not book.valid
    assert book.needs_resync
    assert book.gap_count == 1


def test_fresh_snapshot_resyncs_after_gap() -> None:
    book = LocalOrderBook()
    book.apply_message({"type":"snapshot","ts":1000,"data":{"u":10,"seq":100,"b":[["100","2"]],"a":[["101","3"]]}})
    book.mark_transport_gap("disconnect")
    assert book.needs_resync
    book.apply_message({"type":"snapshot","ts":1200,"data":{"u":20,"seq":200,"b":[["100","4"]],"a":[["101","2"]]}})
    assert book.valid and not book.needs_resync
    assert book.resync_count == 1

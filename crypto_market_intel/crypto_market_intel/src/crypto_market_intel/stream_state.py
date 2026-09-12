from __future__ import annotations

from collections import deque
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from .bybit import parse_liquidation_message, parse_public_trade_message
from .orderbook import LocalOrderBook, SequenceGapError
from .storage import LocalArchive
from .types import Trade


class DeepMarketStreamState:
    """State for one promoted symbol's deep public Bybit stream.

    The state deliberately contains no order/private-account methods. A disconnect or
    evidence of a lost order-book frame invalidates the local book and requires a fresh
    snapshot before deltas can be accepted again.
    """

    def __init__(
        self,
        symbol: str,
        *,
        orderbook_stale_ms: int,
        archive: LocalArchive | None = None,
        max_trades: int = 20_000,
        max_liquidations: int = 5_000,
    ) -> None:
        self.symbol = symbol
        self.orderbook = LocalOrderBook(orderbook_stale_ms)
        self.archive = archive
        self.trades: deque[Trade] = deque(maxlen=max_trades)
        self.liquidations: deque[dict[str, Any]] = deque(maxlen=max_liquidations)
        self.websocket_reconnects = 0
        self.last_message_at: datetime | None = None

    def mark_reconnect(self, reason: str = "websocket_reconnect") -> None:
        self.websocket_reconnects += 1
        self.orderbook.mark_transport_gap(reason)

    def process(self, message: dict[str, Any]) -> None:
        topic = str(message.get("topic") or "")
        event = _message_time(message)
        self.last_message_at = event
        if topic.startswith("publicTrade."):
            rows = parse_public_trade_message(message)
            for trade in rows:
                if trade.symbol != self.symbol:
                    continue
                self.trades.append(trade)
                if self.archive is not None:
                    self.archive.append("public_trades", trade.time, trade.symbol, asdict(trade))
            return
        if topic.startswith("orderbook."):
            try:
                self.orderbook.apply_message(message)
            except SequenceGapError:
                if self.archive is not None:
                    self.archive.append("orderbook", event, self.symbol, {"stream_message": message, "reconstruction_state": "RESYNC_REQUIRED"})
                raise
            if self.archive is not None:
                self.archive.append(
                    "orderbook",
                    event,
                    self.symbol,
                    {"stream_message": message, "reconstruction_state": "VALID" if self.orderbook.valid else "DEGRADED"},
                )
            return
        if topic.startswith("allLiquidation."):
            for row in parse_liquidation_message(message):
                if row.get("symbol") != self.symbol:
                    continue
                self.liquidations.append(row)
            return

    def recent_trades(self) -> list[Trade]:
        return list(self.trades)

    def liquidation_rows(self) -> list[dict[str, Any]]:
        return list(self.liquidations)

    def quality_inputs(self) -> dict[str, Any]:
        return {
            "websocket_reconnects": self.websocket_reconnects,
            "orderbook_gap_count": self.orderbook.gap_count,
            "orderbook_valid": self.orderbook.valid,
            "orderbook_needs_resync": self.orderbook.needs_resync,
            "orderbook_stale": self.orderbook.is_stale(),
        }


def _message_time(message: dict[str, Any]) -> datetime:
    raw = message.get("cts") if message.get("cts") is not None else message.get("ts")
    if raw is None:
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(int(raw) / 1000, tz=timezone.utc)

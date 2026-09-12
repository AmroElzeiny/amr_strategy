from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


class SequenceGapError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BookMetrics:
    best_bid: Decimal | None
    best_ask: Decimal | None
    spread: Decimal | None
    bid_qty: Decimal
    ask_qty: Decimal
    imbalance: Decimal | None
    liquidity_walls: tuple[dict[str, str], ...]


class LocalOrderBook:
    """Bybit L2 snapshot+delta reconstruction with explicit gap/staleness state."""

    def __init__(self, stale_ms: int = 3000, wall_multiple: Decimal = Decimal("3")) -> None:
        self.stale_ms = stale_ms
        self.wall_multiple = wall_multiple
        self.bids: dict[Decimal, Decimal] = {}
        self.asks: dict[Decimal, Decimal] = {}
        self.last_u: int | None = None
        self.last_seq: int | None = None
        self.last_event_ms: int | None = None
        self.valid = False
        self.needs_resync = True
        self.gap_count = 0
        self.snapshot_count = 0
        self.delta_count = 0
        self.resync_count = 0
        self.persistence: dict[tuple[str, Decimal], int] = {}
        self.pulled: list[dict[str, str]] = []
        self.added: list[dict[str, str]] = []

    def reset(self) -> None:
        self.bids.clear(); self.asks.clear(); self.persistence.clear()
        self.pulled.clear(); self.added.clear()
        self.last_u = None; self.last_seq = None; self.valid = False; self.needs_resync = True

    def apply_message(self, message: dict[str, Any]) -> None:
        kind = str(message.get("type") or "")
        data = message.get("data")
        if not isinstance(data, dict):
            raise ValueError("orderbook_data_not_object")
        raw_event = message.get("cts") if message.get("cts") is not None else message.get("ts")
        if raw_event is None:
            raise ValueError("orderbook_event_timestamp_missing")
        if kind == "snapshot":
            self.apply_snapshot(data, event_ms=int(raw_event))
        elif kind == "delta":
            self.apply_delta(data, event_ms=int(raw_event))
        else:
            raise ValueError(f"unsupported_orderbook_message_type:{kind}")

    def apply_snapshot(self, data: dict[str, Any], event_ms: int) -> None:
        was_resync = self.needs_resync and self.gap_count > 0
        if data.get("u") is None or data.get("seq") is None:
            raise ValueError("orderbook_snapshot_sequence_missing")
        self.bids = self._parse_side(data.get("b"))
        self.asks = self._parse_side(data.get("a"))
        self.last_u = int(data["u"])
        self.last_seq = int(data["seq"])
        self.last_event_ms = event_ms
        self.valid = True
        self.needs_resync = False
        self.snapshot_count += 1
        if was_resync:
            self.resync_count += 1
        self.persistence = {("bid", p): 1 for p in self.bids} | {("ask", p): 1 for p in self.asks}
        self.pulled.clear(); self.added.clear()

    def apply_delta(self, data: dict[str, Any], event_ms: int) -> None:
        if not self.valid or self.needs_resync:
            raise SequenceGapError("delta_without_valid_snapshot")
        if data.get("u") is None or data.get("seq") is None:
            self.mark_transport_gap("delta_sequence_missing")
            raise SequenceGapError("delta_sequence_missing")
        u = int(data["u"])
        seq = int(data["seq"])
        # Bybit does not promise +1 for every websocket push. Regression or duplicate update-id is invalid,
        # and a service restart u=1 requires a fresh snapshot. Cross-seq regression is also invalid.
        if u == 1 or (self.last_u is not None and u <= self.last_u) or (self.last_seq is not None and seq < self.last_seq):
            self.valid = False; self.needs_resync = True; self.gap_count += 1
            raise SequenceGapError(f"orderbook_sequence_gap:last_u={self.last_u}:u={u}:last_seq={self.last_seq}:seq={seq}")
        self._apply_side("bid", self.bids, data.get("b"))
        self._apply_side("ask", self.asks, data.get("a"))
        self.last_u = u; self.last_seq = seq; self.last_event_ms = event_ms
        self.delta_count += 1

    @staticmethod
    def _parse_side(rows: Any) -> dict[Decimal, Decimal]:
        if not isinstance(rows, list):
            return {}
        out: dict[Decimal, Decimal] = {}
        for row in rows:
            if not isinstance(row, list) or len(row) < 2:
                continue
            price, qty = Decimal(str(row[0])), Decimal(str(row[1]))
            if qty > 0:
                out[price] = qty
        return out

    def _apply_side(self, name: str, side: dict[Decimal, Decimal], rows: Any) -> None:
        if not isinstance(rows, list):
            return
        for row in rows:
            if not isinstance(row, list) or len(row) < 2:
                continue
            price, qty = Decimal(str(row[0])), Decimal(str(row[1]))
            old = side.get(price)
            if qty == 0:
                if old is not None:
                    self.pulled.append({"side": name, "price": format(price, "f"), "qty": format(old, "f")})
                side.pop(price, None)
                self.persistence.pop((name, price), None)
            else:
                if old is None or qty > old:
                    self.added.append({"side": name, "price": format(price, "f"), "qty": format(qty - (old or 0), "f")})
                side[price] = qty
                self.persistence[(name, price)] = self.persistence.get((name, price), 0) + 1

    def mark_transport_gap(self, reason: str = "transport_gap") -> None:
        """Fail closed after disconnect/lost-frame evidence; a fresh snapshot is mandatory."""
        self.valid = False
        self.needs_resync = True
        self.gap_count += 1
        self.pulled.append({"side": "diagnostic", "price": "", "qty": reason})

    def is_stale(self, now_ms: int | None = None) -> bool:
        now_ms = now_ms if now_ms is not None else int(datetime.now(timezone.utc).timestamp() * 1000)
        return self.last_event_ms is None or now_ms - self.last_event_ms > self.stale_ms

    def metrics(self, depth: int = 20) -> BookMetrics:
        bid_prices = sorted(self.bids, reverse=True)[:depth]
        ask_prices = sorted(self.asks)[:depth]
        bid_qty = sum((self.bids[p] for p in bid_prices), Decimal("0"))
        ask_qty = sum((self.asks[p] for p in ask_prices), Decimal("0"))
        total = bid_qty + ask_qty
        imbalance = (bid_qty - ask_qty) / total if total > 0 else None
        walls: list[dict[str, str]] = []
        for name, prices, side in (("bid", bid_prices, self.bids), ("ask", ask_prices, self.asks)):
            quantities = [side[p] for p in prices]
            if not quantities:
                continue
            avg = sum(quantities, Decimal("0")) / Decimal(len(quantities))
            for p in prices:
                if avg > 0 and side[p] >= avg * self.wall_multiple:
                    walls.append({"side": name, "price": format(p, "f"), "qty": format(side[p], "f"), "persistence": str(self.persistence.get((name, p), 0))})
        best_bid = bid_prices[0] if bid_prices else None
        best_ask = ask_prices[0] if ask_prices else None
        spread = best_ask - best_bid if best_bid is not None and best_ask is not None else None
        return BookMetrics(best_bid, best_ask, spread, bid_qty, ask_qty, imbalance, tuple(walls))

    def diagnostic(self, projected_target: Decimal | None = None) -> dict[str, Any]:
        metrics = self.metrics()
        walls_ahead: list[dict[str, str]] = []
        if projected_target is not None:
            for wall in metrics.liquidity_walls:
                price = Decimal(wall["price"])
                if (wall["side"] == "ask" and price <= projected_target) or (wall["side"] == "bid" and price >= projected_target):
                    walls_ahead.append(wall)
        ephemeral: list[dict[str, str]] = []
        for row in self.pulled[-50:]:
            if row.get("side") not in {"bid", "ask"} or not row.get("price"):
                continue
            price = Decimal(row["price"])
            if int(self.persistence.get((row["side"], price), 0)) <= 1:
                ephemeral.append(row)
        mid = None
        if metrics.best_bid is not None and metrics.best_ask is not None:
            mid = (metrics.best_bid + metrics.best_ask) / Decimal("2")
        wall_distances: list[dict[str, str]] = []
        if mid is not None and mid > 0:
            for wall in metrics.liquidity_walls:
                wall_price = Decimal(wall["price"])
                distance_bps = abs(wall_price - mid) / mid * Decimal("10000")
                wall_distances.append({**wall, "distance_bps": format(distance_bps, "f")})
        added_qty = sum((Decimal(x["qty"]) for x in self.added[-50:] if x.get("qty")), Decimal("0"))
        pulled_qty = sum((Decimal(x["qty"]) for x in self.pulled[-50:] if x.get("side") in {"bid", "ask"} and x.get("qty")), Decimal("0"))
        migration = {
            "added_qty": added_qty,
            "pulled_qty": pulled_qty,
            "net_added_minus_pulled": added_qty - pulled_qty,
            "latest_added": self.added[-1] if self.added else None,
            "latest_pulled": next((x for x in reversed(self.pulled) if x.get("side") in {"bid", "ask"}), None),
        }
        return {
            "valid": self.valid,
            "needs_resync": self.needs_resync,
            "stale": self.is_stale(),
            "gap_count": self.gap_count,
            "resync_count": self.resync_count,
            "last_u": self.last_u,
            "last_seq": self.last_seq,
            "best_bid": metrics.best_bid,
            "best_ask": metrics.best_ask,
            "spread": metrics.spread,
            "book_imbalance": metrics.imbalance,
            "liquidity_walls": list(metrics.liquidity_walls),
            "distance_to_wall": wall_distances,
            "liquidity_migration": migration,
            "added_liquidity": self.added[-50:],
            "pulled_liquidity": self.pulled[-50:],
            "spoof_like_ephemeral_diagnostic": ephemeral,
            "liquidity_ahead_of_projected_target": walls_ahead,
            "scope_note": "Public L2 book excludes some liquidity classes such as RPI and is not a claim of total market liquidity.",
        }

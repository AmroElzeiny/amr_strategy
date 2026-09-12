from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .types import Bar, Trade


def build_trade_bars(trades: list[Trade], seconds: int) -> list[Bar]:
    if seconds <= 0:
        raise ValueError("seconds_must_be_positive")
    buckets: dict[int, list[Trade]] = defaultdict(list)
    for trade in trades:
        key = int(trade.time.timestamp()) // seconds * seconds
        buckets[key].append(trade)
    bars: list[Bar] = []
    for key in sorted(buckets):
        rows = sorted(buckets[key], key=lambda t: t.time)
        prices = [x.price for x in rows]
        buy = sum((x.qty for x in rows if x.taker_side == "Buy"), Decimal("0"))
        sell = sum((x.qty for x in rows if x.taker_side == "Sell"), Decimal("0"))
        volume = buy + sell
        turnover = sum((x.price * x.qty for x in rows), Decimal("0"))
        start = datetime.fromtimestamp(key, tz=timezone.utc)
        bars.append(Bar(start, start + timedelta(seconds=seconds), prices[0], max(prices), min(prices), prices[-1], volume, turnover, buy, sell))
    return bars

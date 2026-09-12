from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


def ms_to_dt(value: int | str) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)


@dataclass(frozen=True, slots=True)
class Instrument:
    symbol: str
    base_coin: str
    quote_coin: str
    status: str
    launch_time: datetime | None
    tick_size: Decimal
    qty_step: Decimal
    min_qty: Decimal | None
    min_notional: Decimal | None
    is_pre_listing: bool
    symbol_type: str | None
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Ticker:
    symbol: str
    last_price: Decimal
    price_24h_pct: Decimal
    volume_24h: Decimal
    turnover_24h: Decimal
    bid: Decimal | None
    ask: Decimal | None
    mark_price: Decimal | None
    index_price: Decimal | None
    funding_rate: Decimal | None
    next_funding_time: datetime | None
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Trade:
    symbol: str
    time: datetime
    price: Decimal
    qty: Decimal
    taker_side: str
    trade_id: str | None = None

    @property
    def signed_qty(self) -> Decimal:
        return self.qty if self.taker_side == "Buy" else -self.qty


@dataclass(frozen=True, slots=True)
class Bar:
    start: datetime
    end: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    turnover: Decimal
    buy_volume: Decimal = Decimal("0")
    sell_volume: Decimal = Decimal("0")

    @property
    def delta(self) -> Decimal:
        return self.buy_volume - self.sell_volume

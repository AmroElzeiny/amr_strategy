from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Iterable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
import websockets

from .config import Settings
from .contracts.models import MarketMode
from .types import Bar, Instrument, Ticker, Trade, ms_to_dt


class BybitAPIError(RuntimeError):
    pass


class BybitV5PublicAdapter:
    """Actual Bybit V5 public-market adapter. It has no authenticated/order methods."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.base_url = settings.bybit_public_rest_base.rstrip("/")
        self._owns_client = client is None
        self.client = client or httpx.Client(base_url=self.base_url, timeout=10.0)
        self._last_http_call = 0.0
        self.source_timestamps: dict[str, datetime] = {}

    @property
    def category(self) -> str:
        return "spot" if self.settings.market_mode == MarketMode.SPOT else "linear"

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.settings.bybit_http_max_rps <= 0:
            raise ValueError("BYBIT_HTTP_MAX_RPS must be positive")
        min_interval = 1.0 / self.settings.bybit_http_max_rps
        elapsed = time.monotonic() - self._last_http_call
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        response = self.client.get(path, params=params)
        self._last_http_call = time.monotonic()
        response.raise_for_status()
        payload = response.json()
        if int(payload.get("retCode", -1)) != 0:
            raise BybitAPIError(f"{path}: {payload.get('retCode')} {payload.get('retMsg')}")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise BybitAPIError(f"{path}: result_not_object")
        raw_time = payload.get("time")
        self.source_timestamps[path] = ms_to_dt(raw_time) if raw_time not in {None, ""} else datetime.now(timezone.utc)
        return result

    def instruments(self) -> list[Instrument]:
        params: dict[str, Any] = {"category": self.category, "status": "Trading"}
        # Spot does not support cursor pagination. Linear does and currently exceeds default page size.
        if self.category != "spot":
            params["limit"] = 1000
        rows: list[dict[str, Any]] = []
        cursor = ""
        seen_cursors: set[str] = set()
        while True:
            if cursor:
                params["cursor"] = cursor
            result = self._get("/v5/market/instruments-info", params)
            page = result.get("list")
            if not isinstance(page, list):
                raise BybitAPIError("instruments:list_not_array")
            rows.extend(x for x in page if isinstance(x, dict))
            if self.category == "spot":
                break
            next_cursor = str(result.get("nextPageCursor") or "")
            if not next_cursor:
                break
            if next_cursor in seen_cursors:
                raise BybitAPIError("instruments:cursor_cycle_detected")
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        return [self._parse_instrument(row) for row in rows]

    @staticmethod
    def _parse_instrument(row: dict[str, Any]) -> Instrument:
        price_filter = row.get("priceFilter") or {}
        lot = row.get("lotSizeFilter") or {}
        launch = row.get("launchTime")
        min_notional = lot.get("minNotionalValue") or lot.get("minOrderAmt")
        tick_raw = price_filter.get("tickSize")
        qty_raw = lot.get("qtyStep") or lot.get("basePrecision")
        if tick_raw in {None, ""} or qty_raw in {None, ""}:
            raise BybitAPIError(f"instrument_precision_missing:{row.get('symbol')}")
        return Instrument(
            symbol=str(row["symbol"]),
            base_coin=str(row.get("baseCoin") or ""),
            quote_coin=str(row.get("quoteCoin") or ""),
            status=str(row.get("status") or ""),
            launch_time=ms_to_dt(launch) if launch not in {None, ""} else None,
            tick_size=Decimal(str(tick_raw)),
            qty_step=Decimal(str(qty_raw)),
            min_qty=(Decimal(str(lot["minOrderQty"])) if lot.get("minOrderQty") not in {None, ""} else None),
            min_notional=(Decimal(str(min_notional)) if min_notional not in {None, ""} else None),
            is_pre_listing=bool(row.get("isPreListing", False)),
            symbol_type=(str(row.get("symbolType")) if row.get("symbolType") not in {None, ""} else None),
            raw=row,
        )

    def tickers(self) -> list[Ticker]:
        result = self._get("/v5/market/tickers", {"category": self.category})
        rows = result.get("list")
        if not isinstance(rows, list):
            raise BybitAPIError("tickers:list_not_array")
        return [self._parse_ticker(row) for row in rows if isinstance(row, dict)]

    @staticmethod
    def _required_decimal(row: dict[str, Any], name: str) -> Decimal:
        value = row.get(name)
        if value in {None, ""}:
            raise BybitAPIError(f"ticker_required_field_missing:{name}:{row.get('symbol')}")
        return Decimal(str(value))

    @staticmethod
    def _optional_decimal(row: dict[str, Any], name: str) -> Decimal | None:
        value = row.get(name)
        return None if value in {None, ""} else Decimal(str(value))

    def _parse_ticker(self, row: dict[str, Any]) -> Ticker:
        next_funding = row.get("nextFundingTime")
        return Ticker(
            symbol=str(row["symbol"]),
            last_price=self._required_decimal(row, "lastPrice"),
            price_24h_pct=self._required_decimal(row, "price24hPcnt"),
            volume_24h=self._required_decimal(row, "volume24h"),
            turnover_24h=self._required_decimal(row, "turnover24h"),
            bid=self._optional_decimal(row, "bid1Price"),
            ask=self._optional_decimal(row, "ask1Price"),
            mark_price=self._optional_decimal(row, "markPrice"),
            index_price=self._optional_decimal(row, "indexPrice"),
            funding_rate=self._optional_decimal(row, "fundingRate"),
            next_funding_time=(ms_to_dt(next_funding) if next_funding not in {None, ""} else None),
            raw=row,
        )

    def klines(self, symbol: str, interval: str, limit: int = 200) -> list[Bar]:
        result = self._get(
            "/v5/market/kline",
            {"category": self.category, "symbol": symbol, "interval": interval, "limit": limit},
        )
        rows = result.get("list") or []
        bars: list[Bar] = []
        interval_ms = _bybit_interval_ms(interval)
        for row in reversed(rows):
            start = ms_to_dt(row[0])
            bars.append(
                Bar(
                    start=start,
                    end=datetime.fromtimestamp((int(row[0]) + interval_ms) / 1000, tz=timezone.utc),
                    open=Decimal(row[1]), high=Decimal(row[2]), low=Decimal(row[3]), close=Decimal(row[4]),
                    volume=Decimal(row[5]), turnover=Decimal(row[6]),
                )
            )
        return bars

    def recent_trades(self, symbol: str, limit: int = 1000) -> list[Trade]:
        result = self._get(
            "/v5/market/recent-trade",
            {"category": self.category, "symbol": symbol, "limit": limit},
        )
        rows = result.get("list") or []
        trades = [
            Trade(
                symbol=str(row["symbol"]),
                time=ms_to_dt(row["time"]),
                price=Decimal(str(row["price"])),
                qty=Decimal(str(row["size"])),
                taker_side=str(row["side"]),
                trade_id=str(row.get("execId") or "") or None,
            )
            for row in rows if isinstance(row, dict)
        ]
        return sorted(trades, key=lambda x: x.time)

    def orderbook_snapshot(self, symbol: str, limit: int = 200) -> dict[str, Any]:
        return self._get(
            "/v5/market/orderbook",
            {"category": self.category, "symbol": symbol, "limit": limit},
        )

    def open_interest(self, symbol: str, interval: str = "5min", limit: int = 2) -> list[dict[str, Any]] | None:
        if self.settings.market_mode == MarketMode.SPOT:
            return None
        result = self._get(
            "/v5/market/open-interest",
            {"category": "linear", "symbol": symbol, "intervalTime": interval, "limit": limit},
        )
        rows = result.get("list")
        return list(rows) if isinstance(rows, list) else []

    def funding_history(self, symbol: str, limit: int = 2) -> list[dict[str, Any]] | None:
        if self.settings.market_mode == MarketMode.SPOT:
            return None
        result = self._get(
            "/v5/market/funding/history",
            {"category": "linear", "symbol": symbol, "limit": limit},
        )
        rows = result.get("list")
        return list(rows) if isinstance(rows, list) else []

    async def stream_public(self, topics: Iterable[str]) -> AsyncIterator[dict[str, Any]]:
        """Opt-in live stream. No test invokes this path."""
        url = self.settings.bybit_public_ws_url()
        async with websockets.connect(url, ping_interval=None, close_timeout=5) as ws:
            await ws.send(json.dumps({"op": "subscribe", "args": list(topics)}))

            async def heartbeat() -> None:
                while True:
                    await asyncio.sleep(20)
                    await ws.send(json.dumps({"op": "ping"}))

            task = asyncio.create_task(heartbeat())
            try:
                async for raw in ws:
                    msg = json.loads(raw)
                    if isinstance(msg, dict):
                        yield msg
            finally:
                task.cancel()


def parse_public_trade_message(message: dict[str, Any]) -> list[Trade]:
    rows = message.get("data")
    if not isinstance(rows, list):
        return []
    trades: list[Trade] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        trades.append(
            Trade(
                symbol=str(row["s"]), time=ms_to_dt(row["T"]), price=Decimal(str(row["p"])),
                qty=Decimal(str(row["v"])), taker_side=str(row["S"]),
                trade_id=str(row.get("i") or "") or None,
            )
        )
    return trades


def _bybit_interval_ms(interval: str) -> int:
    table = {"D": 86_400_000, "W": 604_800_000, "M": 2_592_000_000}
    if interval in table:
        return table[interval]
    return int(interval) * 60_000


def parse_liquidation_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    rows = message.get("data")
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append({
            "time": ms_to_dt(row["T"]),
            "symbol": str(row["s"]),
            "liquidated_position_side": "LONG" if str(row["S"]) == "Buy" else "SHORT",
            "qty": Decimal(str(row["v"])),
            "bankruptcy_price": Decimal(str(row["p"])),
        })
    return out

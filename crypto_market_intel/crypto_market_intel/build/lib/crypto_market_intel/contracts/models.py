from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

CONTRACT_VERSION = "HM_CRYPTO_V1"


class Exchange(StrEnum):
    BYBIT = "BYBIT"
    BINANCE = "BINANCE"


class TradingEnvironment(StrEnum):
    DEMO = "DEMO"
    REAL = "REAL"


class MarketMode(StrEnum):
    SPOT = "SPOT"
    DERIVATIVES = "DERIVATIVES"


class PatternType(StrEnum):
    PRE_BREAKOUT = "PRE_BREAKOUT"
    BREAKOUT = "BREAKOUT"
    CONTINUATION = "CONTINUATION"
    REVERSAL = "REVERSAL"


class Direction(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"
    NONE = "NONE"


class OrderIntent(StrEnum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    REDUCE = "REDUCE"
    NONE = "NONE"


class DecisionState(StrEnum):
    NO_TRADE = "NO_TRADE"
    WATCH = "WATCH"
    ARMED = "ARMED"
    ENTER = "ENTER"


class RegimeType(StrEnum):
    TREND_EXPANSION = "TREND_EXPANSION"
    HEALTHY_PULLBACK = "HEALTHY_PULLBACK"
    BALANCE = "BALANCE"
    FAILED_BREAKOUT = "FAILED_BREAKOUT"
    REVERSAL_RISK = "REVERSAL_RISK"
    RANGE = "RANGE"
    UNKNOWN = "UNKNOWN"


class DataQuality(StrEnum):
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    INVALID = "INVALID"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_serializer("*", when_used="json", check_fields=False)
    def _serialize_decimal_and_dt(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, datetime):
            return iso_utc(value)
        return value


class BreakoutAlert(StrictModel):
    alert_id: str
    snapshot_id: str
    symbol: str
    direction: Direction
    detector_type: str
    event_time_utc: datetime
    reference_level: Decimal | None
    break_price: Decimal
    move_pct: Decimal | None
    window_sec: int | None
    volume_acceleration: Decimal | None
    structure_strength: Decimal | None
    preliminary_score: Decimal
    promotion_reason: str
    watch_until_utc: datetime


class KeyLevel(StrictModel):
    price: Decimal
    type: str
    timeframe: str
    strength: Decimal
    touch_count: int
    first_seen: datetime
    last_seen: datetime
    broken: bool
    reclaimed: bool


class MarketSnapshot(StrictModel):
    contract_version: Literal["HM_CRYPTO_V1"]
    snapshot_id: str
    created_at_utc: datetime
    event_time_utc: datetime
    exchange: Exchange
    environment: TradingEnvironment
    market_mode: MarketMode
    symbol: str
    instrument: dict[str, Any]
    ticker: dict[str, Any]
    timeframes: dict[str, Any]
    structure: dict[str, Any]
    levels: list[dict[str, Any]]
    volume_profile: dict[str, Any]
    orderflow: dict[str, Any]
    orderbook: dict[str, Any]
    derivatives: dict[str, Any] | None
    regime: dict[str, Any]
    breakout_alert: BreakoutAlert | None
    data_quality: DataQuality
    quality_reasons: list[str]
    feature_versions: dict[str, str]
    source_timestamps: dict[str, datetime | None]

    @field_validator("contract_version")
    @classmethod
    def _version_is_frozen(cls, value: str) -> str:
        if value != CONTRACT_VERSION:
            raise ValueError("contract_version_mismatch")
        return value

    def canonical_json(self) -> str:
        payload = self.model_dump(mode="json")
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def integrity_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


class TradeIntent(StrictModel):
    contract_version: Literal["HM_CRYPTO_V1"]
    signal_id: str
    snapshot_id: str
    created_at_utc: datetime
    exchange: Exchange
    environment: TradingEnvironment
    market_mode: MarketMode
    symbol: str
    pattern_type: PatternType
    direction: Direction
    order_intent: OrderIntent
    decision: DecisionState
    thesis_id: str
    attempt_no: int
    deterministic_confidence: Decimal
    ai_confidence: Decimal | None
    final_confidence: Decimal
    entry_plan: dict[str, Any]
    invalidation: dict[str, Any]
    targets: list[dict[str, Any]]
    projected_extension_target: Decimal | None
    risk_reward: Decimal | None
    penalties: list[dict[str, Any]]
    blockers: list[str]
    evidence: list[dict[str, Any]]
    ttl_ms: int
    config_version: str
    strategy_version: str
    ai_metadata: dict[str, Any] | None
    integrity_hash: str


class ExecutionReport(StrictModel):
    contract_version: Literal["HM_CRYPTO_V1"]
    execution_id: str
    signal_id: str
    created_at_utc: datetime
    exchange: Exchange
    environment: TradingEnvironment
    market_mode: MarketMode
    symbol: str
    approved: bool
    reason_codes: list[str]
    final_qty: Decimal | None
    final_notional: Decimal | None
    leverage: Decimal | None
    margin_mode: str | None
    order_ids: list[str]
    order_link_ids: list[str]
    order_state: str
    fill_state: str
    avg_fill_price: Decimal | None
    fees: Decimal | None
    realized_pnl: Decimal | None
    stop_state: str
    take_profit_state: str
    risk_snapshot_before: dict[str, Any]
    risk_snapshot_after: dict[str, Any]
    daily_loss_lock: bool
    max_loss_lock: bool
    reconciled: bool
    integrity_hash: str


def schema_sha256(schema_path: str) -> str:
    with open(schema_path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()

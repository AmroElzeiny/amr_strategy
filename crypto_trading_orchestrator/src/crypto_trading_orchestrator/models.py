from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Any

from .canonical import canonical_hash, utc_text


class RuntimeState(StrEnum):
    BOOT = "BOOT"
    CONFIG_VALIDATE = "CONFIG_VALIDATE"
    PACKAGE_DISCOVERY = "PACKAGE_DISCOVERY"
    CONTRACT_VALIDATE = "CONTRACT_VALIDATE"
    EXCHANGE_MODE_VALIDATE = "EXCHANGE_MODE_VALIDATE"
    RISK_EXECUTION_RECONCILE = "RISK_EXECUTION_RECONCILE"
    MARKET_DATA_START = "MARKET_DATA_START"
    SCANNER_START = "SCANNER_START"
    READY = "READY"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"


class HealthState(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    BLOCK_NEW_ENTRIES = "BLOCK_NEW_ENTRIES"
    EMERGENCY = "EMERGENCY"


class SymbolState(StrEnum):
    DISCOVERED = "DISCOVERED"
    SCANNED = "SCANNED"
    PROMOTED = "PROMOTED"
    DEEP_WATCH = "DEEP_WATCH"
    ARMED = "ARMED"
    IN_TRADE = "IN_TRADE"
    COOLDOWN = "COOLDOWN"
    DEMOTED = "DEMOTED"


class Priority(IntEnum):
    EMERGENCY = 0
    EXECUTION_PROTECTION = 1
    RISK_RECONCILIATION = 2
    STRATEGY_ENTER = 3
    MARKET_DEEP_WATCH = 4
    SCANNER = 5
    RESEARCH = 6


class EventType(StrEnum):
    MARKET_SNAPSHOT_READY = "MARKET_SNAPSHOT_READY"
    BREAKOUT_ALERT = "BREAKOUT_ALERT"
    SYMBOL_PROMOTED = "SYMBOL_PROMOTED"
    SYMBOL_DEMOTED = "SYMBOL_DEMOTED"
    STRATEGY_NO_TRADE = "STRATEGY_NO_TRADE"
    STRATEGY_WATCH = "STRATEGY_WATCH"
    STRATEGY_ARMED = "STRATEGY_ARMED"
    STRATEGY_ENTER = "STRATEGY_ENTER"
    RISK_APPROVED = "RISK_APPROVED"
    RISK_REJECTED = "RISK_REJECTED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_ACKNOWLEDGED = "ORDER_ACKNOWLEDGED"
    ORDER_PARTIAL_FILL = "ORDER_PARTIAL_FILL"
    ORDER_FILLED = "ORDER_FILLED"
    POSITION_PROTECTED = "POSITION_PROTECTED"
    POSITION_REDUCED = "POSITION_REDUCED"
    POSITION_CLOSED = "POSITION_CLOSED"
    DAILY_LOSS_LOCK = "DAILY_LOSS_LOCK"
    MAX_LOSS_LOCK = "MAX_LOSS_LOCK"
    EXECUTION_HEALTH_LOCK = "EXECUTION_HEALTH_LOCK"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    RECONCILIATION_COMPLETE = "RECONCILIATION_COMPLETE"
    LEARNING_OUTCOME_READY = "LEARNING_OUTCOME_READY"
    EXECUTION_ERROR = "EXECUTION_ERROR"


@dataclass(frozen=True)
class Event:
    event_type: EventType
    priority: Priority
    runtime_session_id: str
    package: str
    symbol: str = ""
    snapshot_id: str = ""
    signal_id: str = ""
    thesis_id: str = ""
    execution_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=utc_text)
    event_id: str = ""

    def __post_init__(self) -> None:
        if not self.event_id:
            material = {
                "event_type": self.event_type,
                "runtime_session_id": self.runtime_session_id,
                "package": self.package,
                "symbol": self.symbol,
                "snapshot_id": self.snapshot_id,
                "signal_id": self.signal_id,
                "execution_id": self.execution_id,
                "payload": self.payload,
                "timestamp": self.timestamp,
            }
            object.__setattr__(self, "event_id", "evt_" + canonical_hash(material)[:28])


@dataclass(frozen=True)
class PackageIdentity:
    role: str
    distribution: str
    import_name: str
    version: str
    contract_version: str
    schema_hash: str
    build_hash: str
    path: str


@dataclass(frozen=True)
class InstrumentIdentity:
    exchange: str
    market_mode: str
    symbol: str
    product: str
    settle_asset: str

    @property
    def key(self) -> str:
        return f"{self.exchange}:{self.market_mode}:{self.product}:{self.symbol}:{self.settle_asset}"


@dataclass
class WatchRecord:
    symbol: str
    state: SymbolState
    priority: float
    expires_at_utc: str | None = None
    alert_id: str = ""
    updated_at_utc: str = field(default_factory=utc_text)

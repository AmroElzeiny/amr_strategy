from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
from hashlib import sha256
from typing import Any, Mapping

from ..config import StrategyConfig
from ..models import CONTRACT_VERSION, canonical_hash, canonical_json, decimal_from, dotted_get

EXCHANGES = {"BYBIT", "BINANCE"}
ENVIRONMENTS = {"DEMO", "REAL"}
MARKET_MODES = {"SPOT", "DERIVATIVES"}
REGIMES = {
    "TREND_EXPANSION",
    "HEALTHY_PULLBACK",
    "BALANCE",
    "FAILED_BREAKOUT",
    "REVERSAL_RISK",
    "RANGE",
    "UNKNOWN",
}
DATA_QUALITIES = {"GOOD", "DEGRADED", "STALE", "INVALID"}
REQUIRED_TOP_LEVEL = (
    "contract_version",
    "snapshot_id",
    "created_at_utc",
    "event_time_utc",
    "exchange",
    "environment",
    "market_mode",
    "symbol",
    "instrument",
    "ticker",
    "timeframes",
    "structure",
    "levels",
    "volume_profile",
    "orderflow",
    "orderbook",
    "derivatives",
    "regime",
    "breakout_alert",
    "data_quality",
    "quality_reasons",
    "feature_versions",
    "source_timestamps",
)
DECIMAL_PATHS = (
    "ticker.last_price",
    "ticker.bid",
    "ticker.ask",
    "structure.impulse.origin_price",
    "structure.impulse.end_price",
    "structure.reengagement_origin",
    "levels.reference_level",
    "levels.entry_reference",
    "levels.invalidation_price",
)


def parse_utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field}:utc_z_required")
    try:
        dt = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field}:invalid_timestamp") from exc
    if dt.utcoffset() != timezone.utc.utcoffset(dt):
        raise ValueError(f"{field}:utc_required")
    return dt


@dataclass(frozen=True)
class SnapshotValidation:
    valid: bool
    frozen: dict[str, Any]
    snapshot_hash: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    age_ms: int
    stale_sources: tuple[str, ...]


def schema_sha256() -> str:
    path = Path(__file__).resolve().parents[1] / "contracts" / "schema.json"
    return sha256(path.read_bytes()).hexdigest()


def validate_market_snapshot(
    snapshot: Mapping[str, Any],
    config: StrategyConfig | None = None,
    *,
    now_utc: datetime | None = None,
) -> SnapshotValidation:
    cfg = config or StrategyConfig.from_env()
    if not isinstance(snapshot, Mapping):
        raise ValueError("snapshot:not_object")
    missing = [name for name in REQUIRED_TOP_LEVEL if name not in snapshot]
    if missing:
        raise ValueError("snapshot:missing_required:" + ",".join(missing))
    if snapshot.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("CONTRACT_MISMATCH")
    if snapshot.get("exchange") not in EXCHANGES:
        raise ValueError("snapshot:exchange_enum")
    if snapshot.get("environment") not in ENVIRONMENTS:
        raise ValueError("snapshot:environment_enum")
    if snapshot.get("market_mode") not in MARKET_MODES:
        raise ValueError("snapshot:market_mode_enum")
    if not isinstance(snapshot.get("regime"), Mapping) or snapshot["regime"].get("type") not in REGIMES:
        raise ValueError("snapshot:regime_enum")
    if snapshot.get("data_quality") not in DATA_QUALITIES:
        raise ValueError("snapshot:data_quality_enum")
    for name in (
        "instrument",
        "ticker",
        "timeframes",
        "structure",
        "levels",
        "volume_profile",
        "orderflow",
        "orderbook",
        "derivatives",
        "regime",
        "breakout_alert",
        "feature_versions",
        "source_timestamps",
    ):
        if not isinstance(snapshot.get(name), Mapping):
            raise ValueError(f"snapshot:{name}_not_object")
    if not snapshot["timeframes"]:
        raise ValueError("snapshot:timeframes_empty")
    if not isinstance(snapshot.get("quality_reasons"), list):
        raise ValueError("snapshot:quality_reasons_not_array")

    created = parse_utc(snapshot["created_at_utc"], field="created_at_utc")
    event = parse_utc(snapshot["event_time_utc"], field="event_time_utc")
    if created < event:
        raise ValueError("snapshot:created_before_event")
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age_ms = max(0, int((now - event).total_seconds() * 1000))

    for path in DECIMAL_PATHS:
        raw = dotted_get(snapshot, path)
        if raw is not None:
            if not isinstance(raw, str):
                raise ValueError(f"{path}:decimal_must_be_string")
            decimal_from(raw, name=path)

    stale_sources: list[str] = []
    source_times = snapshot.get("source_timestamps", {})
    for source, raw_time in source_times.items():
        if raw_time is None:
            continue
        source_dt = parse_utc(raw_time, field=f"source_timestamps.{source}")
        if source_dt > event:
            raise ValueError(f"snapshot:future_lineage:{source}")
        source_age_ms = int((event - source_dt).total_seconds() * 1000)
        if source_age_ms > cfg.max_source_age_ms:
            stale_sources.append(str(source))

    blockers: list[str] = []
    warnings: list[str] = []
    quality = str(snapshot["data_quality"])
    if quality == "INVALID":
        blockers.append("INVALID_DATA")
    if quality == "STALE":
        if cfg.fail_on_stale_critical_data:
            blockers.append("CRITICAL_DATA_STALE")
        else:
            warnings.append("STALE_DATA")
    if quality == "DEGRADED":
        warnings.append("DEGRADED_DATA")
        if not cfg.degraded_enter_allowed:
            blockers.append("DEGRADED_DATA_ENTER_BLOCK")
    if age_ms > cfg.max_snapshot_age_ms:
        blockers.append("SIGNAL_EXPIRED")
    if stale_sources and cfg.fail_on_stale_critical_data:
        blockers.append("CRITICAL_SOURCE_STALE")

    frozen = json.loads(canonical_json(dict(snapshot)))
    return SnapshotValidation(
        valid=not blockers,
        frozen=frozen,
        snapshot_hash=canonical_hash(frozen),
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
        age_ms=age_ms,
        stale_sources=tuple(sorted(stale_sources)),
    )

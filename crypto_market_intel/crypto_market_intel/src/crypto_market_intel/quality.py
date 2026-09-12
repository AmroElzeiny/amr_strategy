from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .contracts.models import DataQuality


@dataclass(frozen=True, slots=True)
class SourceFreshness:
    name: str
    timestamp: datetime | None
    stale_ms: int
    required: bool = True


def assess_data_quality(
    sources: list[SourceFreshness],
    *,
    sequence_gap: bool = False,
    orderbook_valid: bool = True,
    missing_fields: list[str] | None = None,
    degraded_reasons: list[str] | None = None,
    reconnects: int = 0,
    now: datetime | None = None,
) -> tuple[DataQuality, list[str]]:
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []
    invalid = False
    stale_required = False
    degraded = False
    for source in sources:
        if source.timestamp is None:
            if source.required:
                reasons.append(f"missing_source:{source.name}")
                invalid = True
            else:
                reasons.append(f"unavailable_optional_source:{source.name}")
                degraded = True
            continue
        age_ms = int((now - source.timestamp).total_seconds() * 1000)
        if age_ms > source.stale_ms:
            reasons.append(f"stale_source:{source.name}:{age_ms}ms")
            if source.required:
                stale_required = True
            else:
                degraded = True
    if sequence_gap:
        reasons.append("orderbook_sequence_gap")
        invalid = True
    if not orderbook_valid:
        reasons.append("orderbook_invalid_or_resync_required")
        invalid = True
    for field in missing_fields or []:
        reasons.append(f"missing_field:{field}")
        degraded = True
    for reason in degraded_reasons or []:
        reasons.append(reason)
        degraded = True
    if reconnects:
        reasons.append(f"websocket_reconnects:{reconnects}")
        degraded = True
    if invalid:
        return DataQuality.INVALID, reasons
    if stale_required:
        return DataQuality.STALE, reasons
    if degraded:
        return DataQuality.DEGRADED, reasons
    return DataQuality.GOOD, reasons

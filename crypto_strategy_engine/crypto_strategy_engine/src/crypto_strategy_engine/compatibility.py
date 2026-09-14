"""Strategy-owned normalization for the Package-1 HM_CRYPTO_V1 producer variant.

The market package emits observations.  This module interprets those observations only
inside the strategy authority; it never mutates the producer payload.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _n01(value: Any, default: float = 0.0) -> float:
    number = _decimal(value)
    if number is None:
        return default
    return float(max(Decimal("0"), min(Decimal("1"), number)))


def _text(value: Any) -> str | None:
    number = _decimal(value)
    return None if number is None else format(number, "f")


def _bars(snapshot: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    frames = snapshot.get("timeframes")
    if not isinstance(frames, Mapping):
        return []
    for name in ("5m", "3m", "1m", "15m"):
        rows = frames.get(name)
        if isinstance(rows, list) and rows:
            return [row for row in rows if isinstance(row, Mapping)]
    for rows in frames.values():
        if isinstance(rows, list) and rows:
            return [row for row in rows if isinstance(row, Mapping)]
    return []


def _bar_range(row: Mapping[str, Any]) -> Decimal:
    high, low = _decimal(row.get("high")), _decimal(row.get("low"))
    return abs(high - low) if high is not None and low is not None else Decimal("0")


def _comparative_pullback(snapshot: Mapping[str, Any]) -> dict[str, float]:
    rows = _bars(snapshot)
    if len(rows) < 4:
        return {}
    split = max(2, len(rows) - min(3, len(rows) // 2))
    impulse, pullback = rows[:split], rows[split:]
    impulse_range = max((_bar_range(row) for row in impulse), default=Decimal("0"))
    pullback_range = max((_bar_range(row) for row in pullback), default=Decimal("0"))
    if impulse_range <= 0:
        return {}
    depth = float(min(Decimal("1.25"), pullback_range / impulse_range))
    duration = min(1.25, len(pullback) / max(1, len(impulse)))
    return {
        "pullback_depth_ratio": depth,
        "pullback_duration_ratio": duration,
        "pullback_velocity_ratio": depth,
        "pullback_displacement_ratio": depth,
        "pullback_overlap": depth,
        "countertrend_structure_damage": depth,
    }


def _direction(snapshot: Mapping[str, Any]) -> str:
    alert = snapshot.get("breakout_alert")
    if isinstance(alert, Mapping):
        direction = str(alert.get("direction") or "").upper()
        if direction in {"LONG", "SHORT"}:
            return direction
    structure = snapshot.get("structure")
    if isinstance(structure, Mapping):
        events = structure.get("events")
        if isinstance(events, list):
            for event in reversed(events):
                if isinstance(event, Mapping):
                    direction = str(event.get("direction") or "").upper()
                    if direction in {"LONG", "SHORT"}:
                        return direction
    return "NONE"


def _level_payload(snapshot: Mapping[str, Any], direction: str) -> dict[str, Any]:
    raw_levels = snapshot.get("levels")
    if isinstance(raw_levels, Mapping):
        return deepcopy(dict(raw_levels))
    levels = [dict(row) for row in raw_levels or [] if isinstance(row, Mapping)]
    ticker = snapshot.get("ticker") if isinstance(snapshot.get("ticker"), Mapping) else {}
    structure = snapshot.get("structure") if isinstance(snapshot.get("structure"), Mapping) else {}
    alert = snapshot.get("breakout_alert") if isinstance(snapshot.get("breakout_alert"), Mapping) else {}
    entry = _decimal(ticker.get("last_price")) or _decimal(alert.get("break_price"))
    candidates = [(_decimal(row.get("price")), row) for row in levels]
    candidates = [(price, row) for price, row in candidates if price is not None]
    if direction == "LONG" and entry is not None:
        stop_candidates = [price for price, _ in candidates if price < entry]
        stop = max(stop_candidates, default=_decimal(structure.get("major_low")))
        obstacles = [(price, row) for price, row in candidates if price > entry]
        obstacles.sort(key=lambda item: item[0])
    elif direction == "SHORT" and entry is not None:
        stop_candidates = [price for price, _ in candidates if price > entry]
        stop = min(stop_candidates, default=_decimal(structure.get("major_high")))
        obstacles = [(price, row) for price, row in candidates if price < entry]
        obstacles.sort(key=lambda item: item[0], reverse=True)
    else:
        stop, obstacles = None, []
    reference = _decimal(alert.get("reference_level")) or entry
    score = _n01(alert.get("preliminary_score"), 0.5)
    retests = [
        {
            "type": str(row.get("type") or "KEY_LEVEL"),
            "root_event": f"market_level:{index}",
            "reliability": _n01(row.get("strength"), 0.5),
            "freshness": 1.0,
            "structural_significance": _n01(row.get("strength"), 0.5),
            "price": _text(price),
        }
        for index, (price, row) in enumerate(candidates)
    ]
    expiry = alert.get("watch_until_utc")
    if expiry is None and isinstance(snapshot.get("event_time_utc"), str):
        try:
            value = datetime.fromisoformat(str(snapshot["event_time_utc"]).replace("Z", "+00:00"))
            expiry = (value.astimezone(timezone.utc) + timedelta(seconds=45)).isoformat().replace("+00:00", "Z")
        except ValueError:
            expiry = None
    return {
        "raw_levels": levels,
        "entry_reference": _text(entry),
        "entry_zone_low": _text(entry),
        "entry_zone_high": _text(entry),
        "trigger_price": _text(_decimal(alert.get("break_price")) or entry),
        "entry_expiry_utc": expiry,
        "max_chase_distance": None,
        "preferred_execution_style": "PASSIVE_WHEN_POSSIBLE",
        "invalidation_price": _text(stop),
        "reference_level": _text(reference),
        "retest_locations": retests,
        "obstacles": [
            {"price": _text(price), "strength": _n01(row.get("strength"), 0.5), "type": str(row.get("type") or "KEY_LEVEL")}
            for price, row in obstacles
        ],
        "liquidity_context_score": score,
        "target_room_score": 0.8 if obstacles else 0.5,
        "liquidity_sweep_reclaim": bool(structure.get("liquidity_events") or structure.get("reclaims")),
        "breakout_event_id": alert.get("alert_id"),
        "major_structure_event_id": alert.get("snapshot_id"),
    }


def _alert_payload(snapshot: Mapping[str, Any], direction: str) -> dict[str, Any]:
    raw = snapshot.get("breakout_alert")
    if not isinstance(raw, Mapping):
        return {}
    alert = deepcopy(dict(raw))
    detector = str(raw.get("detector_type") or raw.get("breakout_type") or "").upper()
    type_map = {
        "PERCENT_ACCELERATION": "COMPRESSION_BREAK",
        "MAJOR_STRUCTURE_BREAK": "MAJOR_STRUCTURE_BREAK",
        "RANGE_BREAK": "RANGE_BREAK",
        "KEY_LEVEL_BREAK": "KEY_LEVEL_BREAK",
        "TRENDLINE_BREAK": "TRENDLINE_BREAK",
    }
    score = _n01(raw.get("preliminary_score"), 0.0)
    structure = snapshot.get("structure") if isinstance(snapshot.get("structure"), Mapping) else {}
    alert.update(
        {
            "direction": direction,
            "breakout_type": type_map.get(detector, detector if detector else ""),
            "breakout_completed": True,
            "level_strength": _n01(raw.get("structure_strength"), score),
            "breakout_score": score,
            "acceptance_score": 1.0 if structure.get("acceptance_outside_range") else score,
            "follow_through_score": score,
            "compression_score": 1.0 if structure.get("compression") else score,
            "directional_pressure": score,
            "progress_per_unit_volume": score,
            "directional_volume_score": min(1.0, _n01(raw.get("volume_acceleration"), score)),
            "value_location_score": score,
            "swing_contraction_score": 0.7 if structure.get("pullback") else score,
            "micro_pullback_quality": 0.7 if structure.get("pullback") else score,
            "pullback_count": 1 if structure.get("pullback") else 0,
            "major_reset": False,
        }
    )
    return alert


def normalize_market_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Return a strategy-internal normalized copy of either HM_CRYPTO_V1 variant."""
    # Package 2's native mapping-shaped evidence is already authoritative.  Only
    # adapt the Package 1 producer variant (list-shaped levels); touching native
    # evidence would change strategy semantics and is therefore forbidden.
    if isinstance(snapshot.get("levels"), Mapping):
        return deepcopy(dict(snapshot))
    normalized = deepcopy(dict(snapshot))
    direction = _direction(snapshot)
    normalized["levels"] = _level_payload(snapshot, direction)
    normalized["breakout_alert"] = _alert_payload(snapshot, direction)
    if normalized.get("derivatives") is None:
        normalized["derivatives"] = {"availability": "UNAVAILABLE"}
    structure = deepcopy(dict(normalized.get("structure") or {}))
    alert = normalized["breakout_alert"]
    score = _n01(alert.get("breakout_score"), 0.0)
    metrics = structure.get("metrics") if isinstance(structure.get("metrics"), Mapping) else {}
    structure.update(
        {
            "qualified_impulse_score": structure.get("qualified_impulse_score", score),
            "displacement_score": structure.get("displacement_score", score if structure.get("displacement") else 0.0),
            "expansion_score": structure.get("expansion_score", 1.0 if structure.get("expansion") else score),
            "follow_through_score": structure.get("follow_through_score", score),
            "major_structure_quality": structure.get("major_structure_quality", _n01(alert.get("level_strength"), score)),
            "acceptance_inside_prior_range": structure.get("acceptance_inside_prior_range", bool(structure.get("acceptance_back_inside_range"))),
            "return_inside_prior_range": structure.get("return_inside_prior_range", bool(structure.get("failed_breaks"))),
            "reclaim": structure.get("reclaim", bool(structure.get("reclaims"))),
            "micro_bos": structure.get("micro_bos", bool(structure.get("events"))),
            "micro_choch_main_trend": structure.get("micro_choch_main_trend", bool(structure.get("events"))),
            "directional_displacement_restart": structure.get("directional_displacement_restart", bool(structure.get("displacement"))),
            "failed_countertrend_progress_score": structure.get("failed_countertrend_progress_score", score),
            "htf_context_score": structure.get("htf_context_score", _n01((normalized.get("regime") or {}).get("confidence"), 0.5)),
            "timing_score": structure.get("timing_score", score),
            "extension_decay": structure.get("extension_decay", _n01(metrics.get("extension_decay"), 0.0)),
            "impulse": structure.get("impulse", {"origin_price": _text(alert.get("reference_level")), "end_price": _text(alert.get("break_price"))}),
            "reengagement_origin": structure.get("reengagement_origin", normalized["levels"].get("entry_reference")),
        }
    )
    for key, value in _comparative_pullback(snapshot).items():
        structure.setdefault(key, value)
    normalized["structure"] = structure
    orderflow = deepcopy(dict(normalized.get("orderflow") or {}))
    delta = _decimal(orderflow.get("delta")) or Decimal("0")
    aligned = (delta >= 0 and direction == "LONG") or (delta <= 0 and direction == "SHORT")
    absorption = orderflow.get("absorption") if isinstance(orderflow.get("absorption"), Mapping) else {}
    orderflow.update(
        {
            "directional_delta_score": orderflow.get("directional_delta_score", 0.75 if aligned else 0.25),
            "imbalance_score": orderflow.get("imbalance_score", _n01(orderflow.get("imbalance"), 0.5)),
            "trade_velocity_score": orderflow.get("trade_velocity_score", 0.6),
            "opposing_failure_score": orderflow.get("opposing_failure_score", 0.7 if structure.get("reclaim") else 0.4),
            "absorption_score": orderflow.get("absorption_score", 0.8 if absorption.get("detected") else 0.3),
            "delta_flip": orderflow.get("delta_flip", aligned),
            "pullback_volume_ratio": orderflow.get("pullback_volume_ratio", 0.5),
            "pullback_delta_ratio": orderflow.get("pullback_delta_ratio", 0.5),
        }
    )
    normalized["orderflow"] = orderflow
    volume = deepcopy(dict(normalized.get("volume_profile") or {}))
    migration = _decimal(volume.get("value_migration"))
    volume.setdefault("value_migration_score", min(1.0, float(abs(migration))) if migration is not None else 0.5)
    volume.setdefault("poc_migration_score", volume["value_migration_score"])
    normalized["volume_profile"] = volume
    versions = deepcopy(dict(normalized.get("feature_versions") or {}))
    versions["strategy_input_normalization"] = "HM_P1_TO_P2_V1"
    normalized["feature_versions"] = versions
    return normalized

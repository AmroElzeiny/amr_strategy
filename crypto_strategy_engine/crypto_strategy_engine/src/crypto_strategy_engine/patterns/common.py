from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ..models import clamp, dotted_get

PATTERN_NORMALIZATION_VERSION = "HM_PATTERN_NORMALIZATION_V1"


def n01(snapshot: Mapping[str, Any], path: str) -> float | None:
    raw = dotted_get(snapshot, path)
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError):
        return None


def bool_score(snapshot: Mapping[str, Any], path: str) -> float | None:
    raw = dotted_get(snapshot, path)
    if raw is None:
        return None
    if isinstance(raw, bool):
        return 100.0 if raw else 0.0
    value = n01(snapshot, path)
    return None if value is None else value * 100.0


def score(snapshot: Mapping[str, Any], path: str) -> float | None:
    value = n01(snapshot, path)
    return None if value is None else value * 100.0


def average(values: list[float | None], *, missing_ok: bool = True) -> float | None:
    observed = [value for value in values if value is not None]
    if not observed:
        return None
    if not missing_ok and len(observed) != len(values):
        return None
    return sum(observed) / len(observed)


def inverse_ratio(value: float | None, *, preferred_max: float = 0.65) -> float | None:
    if value is None:
        return None
    return clamp((1.0 - min(1.25, value) / max(preferred_max, 0.01)) * 100.0)


@dataclass
class PatternDraft:
    pattern_type: str
    direction: str
    branch: str
    eligible: bool
    component_scores: dict[str, float] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    missing_critical: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    entry_plan: dict[str, Any] = field(default_factory=dict)
    invalidation: dict[str, Any] = field(default_factory=dict)
    maturity: float = 0.0


def direction_from(snapshot: Mapping[str, Any]) -> str:
    direction = str(dotted_get(snapshot, "breakout_alert.direction", "NONE")).upper()
    return direction if direction in {"LONG", "SHORT"} else "NONE"


def base_entry_plan(snapshot: Mapping[str, Any], *, entry_type: str, trigger: str) -> dict[str, Any]:
    return {
        "entry_type": entry_type,
        "entry_reference": dotted_get(snapshot, "levels.entry_reference"),
        "entry_zone_low": dotted_get(snapshot, "levels.entry_zone_low"),
        "entry_zone_high": dotted_get(snapshot, "levels.entry_zone_high"),
        "trigger_condition": trigger,
        "trigger_price_if_any": dotted_get(snapshot, "levels.trigger_price"),
        "entry_expiry": dotted_get(snapshot, "levels.entry_expiry_utc"),
        "max_chase_distance": dotted_get(snapshot, "levels.max_chase_distance"),
        "preferred_execution_style": dotted_get(snapshot, "levels.preferred_execution_style", "PASSIVE_WHEN_POSSIBLE"),
    }


def base_invalidation(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    modes = dotted_get(snapshot, "structure.invalidation_modes")
    if not isinstance(modes, list) or not modes:
        modes = ["STRUCTURAL_ACCEPTANCE", "MICRO_BAR_CLOSE"]
    return {
        "price": dotted_get(snapshot, "levels.invalidation_price"),
        "conditions": [
            "loss_of_breakout_or_retest_level",
            "major_structure_failure",
            "acceptance_back_into_old_range",
            "regime_change",
            "opposing_displacement",
            "thesis_timeout",
        ],
        "confirmation_modes": modes,
        "persistence_seconds": dotted_get(snapshot, "structure.invalidation_persistence_seconds", 3),
    }

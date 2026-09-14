from __future__ import annotations

from typing import Any, Mapping

from ..config import StrategyConfig
from ..models import dotted_get
from .common import (
    PatternDraft,
    average,
    base_entry_plan,
    base_invalidation,
    bool_score,
    direction_from,
    inverse_ratio,
    n01,
    score,
)


def _location_score(snapshot: Mapping[str, Any]) -> tuple[float | None, list[dict[str, Any]]]:
    raw = dotted_get(snapshot, "levels.retest_locations")
    if not isinstance(raw, list) or not raw:
        return None, []
    roots: dict[str, float] = {}
    accepted: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        try:
            reliability = max(0.0, min(1.0, float(item.get("reliability"))))
            freshness = max(0.0, min(1.0, float(item.get("freshness"))))
            significance = max(0.0, min(1.0, float(item.get("structural_significance"))))
        except (TypeError, ValueError):
            continue
        root = str(item.get("root_event") or item.get("type") or "unknown")
        value = (reliability * 0.40 + freshness * 0.25 + significance * 0.35) * 100.0
        if root not in roots or value > roots[root]:
            roots[root] = value
        accepted.append(dict(item))
    if not roots:
        return None, accepted
    # Evidence independence matters more than raw count. Multiple derivatives of the same
    # structural event contribute once through the max value for that root event.
    base = sum(roots.values()) / len(roots)
    independence_bonus = min(8.0, max(0, len(roots) - 1) * 2.0)
    return min(100.0, base + independence_bonus), accepted


def detect(snapshot: Mapping[str, Any], config: StrategyConfig) -> PatternDraft:
    direction = direction_from(snapshot)
    draft = PatternDraft("CONTINUATION", direction, "RETEST_REENGAGEMENT", False)
    pullback_count_raw = dotted_get(snapshot, "breakout_alert.pullback_count")
    pullback_count = int(pullback_count_raw) if isinstance(pullback_count_raw, (int, float)) else 0
    major_reset = bool(dotted_get(snapshot, "breakout_alert.major_reset", False))
    if pullback_count > config.continuation_max_minor_pullback_entries and not major_reset:
        draft.missing_critical.append("major_pullback_reset_after_exhausted_minor_sequence")
        draft.flags.append("MINOR_CONTINUATION_SEQUENCE_EXHAUSTED")
    if direction == "NONE":
        draft.missing_critical.append("breakout_alert.direction")
        return draft

    qualified_impulse = score(snapshot, "structure.qualified_impulse_score")
    breakout_quality = average(
        [
            score(snapshot, "breakout_alert.breakout_score"),
            score(snapshot, "structure.displacement_score"),
            score(snapshot, "structure.expansion_score"),
            score(snapshot, "structure.follow_through_score"),
            bool_score(snapshot, "structure.acceptance_outside_range"),
        ]
    )
    if qualified_impulse is None:
        draft.missing_critical.append("structure.qualified_impulse_score")
    if breakout_quality is None:
        draft.missing_critical.append("breakout_quality")

    pullback_scores = [
        inverse_ratio(n01(snapshot, "structure.pullback_depth_ratio"), preferred_max=0.75),
        inverse_ratio(n01(snapshot, "structure.pullback_duration_ratio"), preferred_max=0.85),
        inverse_ratio(n01(snapshot, "structure.pullback_velocity_ratio"), preferred_max=0.75),
        inverse_ratio(n01(snapshot, "orderflow.pullback_volume_ratio"), preferred_max=0.80),
        inverse_ratio(n01(snapshot, "orderflow.pullback_delta_ratio"), preferred_max=0.80),
        inverse_ratio(n01(snapshot, "structure.pullback_displacement_ratio"), preferred_max=0.75),
        inverse_ratio(n01(snapshot, "structure.pullback_overlap"), preferred_max=0.80),
        inverse_ratio(n01(snapshot, "structure.countertrend_structure_damage"), preferred_max=0.45),
    ]
    pullback_quality = average(pullback_scores)
    if pullback_quality is None:
        draft.missing_critical.append("pullback_comparative_metrics")

    location_quality, locations = _location_score(snapshot)
    if location_quality is None:
        draft.missing_critical.append("levels.retest_locations")

    opposing_failure = average(
        [
            score(snapshot, "orderflow.opposing_failure_score"),
            score(snapshot, "orderflow.absorption_score"),
            bool_score(snapshot, "structure.reclaim"),
            score(snapshot, "structure.failed_countertrend_progress_score"),
        ]
    )
    if opposing_failure is None:
        draft.missing_critical.append("opposing_side_failure")

    reengagement = average(
        [
            bool_score(snapshot, "structure.micro_bos"),
            bool_score(snapshot, "structure.micro_choch_main_trend"),
            bool_score(snapshot, "structure.reclaim"),
            bool_score(snapshot, "orderflow.delta_flip"),
            score(snapshot, "orderflow.imbalance_score"),
            score(snapshot, "orderflow.trade_velocity_score"),
            bool_score(snapshot, "structure.directional_displacement_restart"),
            score(snapshot, "volume_profile.value_migration_score"),
            score(snapshot, "volume_profile.poc_migration_score"),
        ]
    )
    if config.continuation_require_reengagement and reengagement is None:
        draft.missing_critical.append("reengagement_confirmation")

    component_scores = {
        "structure_quality": average([qualified_impulse, score(snapshot, "structure.major_structure_quality")]) or 0.0,
        "breakout_quality": breakout_quality or 0.0,
        "location_quality": location_quality or 0.0,
        "pullback_quality": pullback_quality or 0.0,
        "reengagement_quality": reengagement or 0.0,
        "orderflow_quality": average([score(snapshot, "orderflow.directional_delta_score"), score(snapshot, "orderflow.imbalance_score"), opposing_failure]) or 0.0,
        "volume_quality": average([score(snapshot, "breakout_alert.directional_volume_score"), score(snapshot, "orderflow.trade_velocity_score")]) or 0.0,
        "value_quality": average([score(snapshot, "volume_profile.value_migration_score"), score(snapshot, "volume_profile.poc_migration_score")]) or 0.0,
        "liquidity_quality": average([score(snapshot, "levels.liquidity_context_score"), score(snapshot, "derivatives.liquidation_context_score")]) or 0.0,
        "htf_context_quality": score(snapshot, "structure.htf_context_score") or 0.0,
        "target_quality": score(snapshot, "levels.target_room_score") or 50.0,
        "timing_quality": score(snapshot, "structure.timing_score") or 50.0,
        "data_quality_score": 0.0,
    }
    draft.component_scores = component_scores
    draft.evidence = {
        "qualified_impulse": qualified_impulse,
        "breakout_quality": breakout_quality,
        "pullback_quality": pullback_quality,
        "location_quality": location_quality,
        "retest_locations": locations,
        "opposing_side_failure": opposing_failure,
        "reengagement_quality": reengagement,
        "pullback_depth_ratio": dotted_get(snapshot, "structure.pullback_depth_ratio"),
        "pullback_duration_ratio": dotted_get(snapshot, "structure.pullback_duration_ratio"),
        "pullback_velocity_ratio": dotted_get(snapshot, "structure.pullback_velocity_ratio"),
        "pullback_volume_ratio": dotted_get(snapshot, "orderflow.pullback_volume_ratio"),
        "pullback_delta_ratio": dotted_get(snapshot, "orderflow.pullback_delta_ratio"),
        "countertrend_structure_damage": dotted_get(snapshot, "structure.countertrend_structure_damage"),
        "reengagement_triggers": {
            key: dotted_get(snapshot, path)
            for key, path in {
                "micro_bos": "structure.micro_bos",
                "micro_choch": "structure.micro_choch_main_trend",
                "reclaim": "structure.reclaim",
                "delta_flip": "orderflow.delta_flip",
                "directional_displacement_restart": "structure.directional_displacement_restart",
                "value_migration_restart": "volume_profile.value_migration_score",
            }.items()
            if dotted_get(snapshot, path) is not None
        },
    }
    draft.entry_plan = base_entry_plan(
        snapshot,
        entry_type="RETEST_TRIGGER",
        trigger="qualified_retest_plus_directional_reengagement",
    )
    draft.invalidation = base_invalidation(snapshot)
    draft.maturity = min(100.0, average([qualified_impulse, breakout_quality, pullback_quality, reengagement]) or 0.0)
    draft.eligible = (
        not draft.missing_critical
        and (qualified_impulse or 0.0) >= config.continuation_min_breakout_score
        and (breakout_quality or 0.0) >= config.continuation_min_breakout_score
        and (pullback_quality or 0.0) >= config.continuation_min_pullback_score
        and (location_quality or 0.0) >= config.continuation_min_location_score
        and (not config.continuation_require_reengagement or (reengagement or 0.0) >= config.continuation_min_reengagement_score)
    )
    return draft

from __future__ import annotations

from typing import Any, Mapping

from ..config import StrategyConfig
from .common import PatternDraft, average, base_entry_plan, base_invalidation, direction_from, score


def detect(snapshot: Mapping[str, Any], config: StrategyConfig) -> PatternDraft:
    direction = direction_from(snapshot)
    draft = PatternDraft("PRE_BREAKOUT", direction, "ANTICIPATION", False)
    if bool(snapshot.get("breakout_alert", {}).get("breakout_completed", False)):
        draft.missing_critical.append("breakout_already_completed")
    level = score(snapshot, "breakout_alert.level_strength")
    compression = score(snapshot, "breakout_alert.compression_score")
    pressure = score(snapshot, "breakout_alert.directional_pressure")
    progress = score(snapshot, "breakout_alert.progress_per_unit_volume")
    value_location = score(snapshot, "breakout_alert.value_location_score")
    rejection_severity = score(snapshot, "breakout_alert.opposite_rejection_severity")
    if direction == "NONE":
        draft.missing_critical.append("breakout_alert.direction")
    for value, name in ((level, "level_strength"), (compression, "compression_score"), (pressure, "directional_pressure")):
        if value is None:
            draft.missing_critical.append(name)
    chop_signal = average(
        [
            score(snapshot, "volume_profile.range_midpoint_cross_score"),
            score(snapshot, "structure.both_side_liquidity_sweeps"),
            score(snapshot, "volume_profile.poc_oscillation_score"),
            rejection_severity,
        ]
    )
    draft.component_scores = {
        "structure_quality": level or 0.0,
        "breakout_quality": average([compression, pressure, progress]) or 0.0,
        "location_quality": value_location or level or 0.0,
        "pullback_quality": score(snapshot, "breakout_alert.swing_contraction_score") or 0.0,
        "reengagement_quality": pressure or 0.0,
        "orderflow_quality": average([score(snapshot, "orderflow.directional_delta_score"), score(snapshot, "orderflow.trade_velocity_score")]) or 0.0,
        "volume_quality": score(snapshot, "breakout_alert.directional_volume_score") or 0.0,
        "value_quality": average([value_location, score(snapshot, "volume_profile.poc_migration_score")]) or 0.0,
        "liquidity_quality": score(snapshot, "levels.liquidity_context_score") or 0.0,
        "htf_context_quality": score(snapshot, "structure.htf_context_score") or 0.0,
        "target_quality": score(snapshot, "levels.target_room_score") or 50.0,
        "timing_quality": compression or 0.0,
        "data_quality_score": 0.0,
    }
    draft.evidence = {
        "level_strength": level,
        "compression_score": compression,
        "directional_pressure": pressure,
        "progress_per_unit_volume": progress,
        "value_location_score": value_location,
        "chop_signal": chop_signal,
    }
    draft.entry_plan = base_entry_plan(snapshot, entry_type="BREAK_TRIGGER", trigger="pre_breakout_arm_then_confirm_break")
    draft.invalidation = base_invalidation(snapshot)
    draft.maturity = average([level, compression, pressure]) or 0.0
    draft.eligible = (
        not draft.missing_critical
        and (level or 0.0) >= config.pre_breakout_min_level_strength
        and (compression or 0.0) >= config.pre_breakout_min_compression_score
        and (pressure or 0.0) >= config.pre_breakout_min_directional_pressure
        and (chop_signal is None or chop_signal < 65.0)
    )
    if chop_signal is not None and chop_signal >= 65.0:
        draft.flags.append("RANDOM_SIDEWAYS_CHOP")
    return draft

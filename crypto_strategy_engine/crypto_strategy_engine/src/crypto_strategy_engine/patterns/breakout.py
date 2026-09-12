from __future__ import annotations

from typing import Any, Mapping

from ..config import StrategyConfig
from ..models import dotted_get
from .common import PatternDraft, average, base_entry_plan, base_invalidation, bool_score, direction_from, score

BREAKOUT_TYPES = {
    "RANGE_BREAK",
    "MAJOR_STRUCTURE_BREAK",
    "KEY_LEVEL_BREAK",
    "TRENDLINE_BREAK",
    "COMPRESSION_BREAK",
    "LIQUIDITY_DRIVEN_BREAK",
    "VALUE_AREA_ESCAPE",
    "LOW_VOLUME_NODE_ESCAPE",
    "BREAK_AND_ACCEPT",
    "BREAK_RETEST_CONTINUE",
}


def detect(snapshot: Mapping[str, Any], config: StrategyConfig) -> PatternDraft:
    direction = direction_from(snapshot)
    breakout_type = str(dotted_get(snapshot, "breakout_alert.breakout_type", "")).upper()
    pullback_count_raw = dotted_get(snapshot, "breakout_alert.pullback_count")
    pullback_count = int(pullback_count_raw) if isinstance(pullback_count_raw, (int, float)) else 0
    major_reset = bool(dotted_get(snapshot, "breakout_alert.major_reset", False))
    if pullback_count == 0:
        branch = "IMMEDIATE_BREAKOUT"
    elif pullback_count == 1:
        branch = "FIRST_MICRO_PULLBACK"
    elif pullback_count == 2:
        branch = "SECOND_MICRO_PULLBACK"
    else:
        branch = "MAJOR_PULLBACK_REENTRY" if major_reset else "EXHAUSTED_MINOR_PULLBACKS"
    draft = PatternDraft("BREAKOUT", direction, branch, False)
    if direction == "NONE":
        draft.missing_critical.append("breakout_alert.direction")
    if breakout_type not in BREAKOUT_TYPES:
        draft.missing_critical.append("breakout_alert.breakout_type")

    level = score(snapshot, "breakout_alert.level_strength")
    breakout = score(snapshot, "breakout_alert.breakout_score")
    acceptance = score(snapshot, "breakout_alert.acceptance_score")
    follow = score(snapshot, "breakout_alert.follow_through_score")
    compression = score(snapshot, "breakout_alert.compression_score")
    component_scores = {
        "structure_quality": average([level, score(snapshot, "structure.major_structure_quality")]) or 0.0,
        "breakout_quality": average([breakout, acceptance, follow]) or 0.0,
        "location_quality": level or 0.0,
        "pullback_quality": score(snapshot, "breakout_alert.micro_pullback_quality") or (70.0 if pullback_count <= 2 else 20.0),
        "reengagement_quality": average([bool_score(snapshot, "structure.micro_bos"), bool_score(snapshot, "structure.directional_displacement_restart")]) or 0.0,
        "orderflow_quality": average([score(snapshot, "orderflow.directional_delta_score"), score(snapshot, "orderflow.imbalance_score")]) or 0.0,
        "volume_quality": average([score(snapshot, "breakout_alert.directional_volume_score"), score(snapshot, "orderflow.trade_velocity_score")]) or 0.0,
        "value_quality": average([score(snapshot, "volume_profile.value_migration_score"), score(snapshot, "volume_profile.poc_migration_score")]) or 0.0,
        "liquidity_quality": score(snapshot, "levels.liquidity_context_score") or 0.0,
        "htf_context_quality": score(snapshot, "structure.htf_context_score") or 0.0,
        "target_quality": score(snapshot, "levels.target_room_score") or 50.0,
        "timing_quality": compression or 50.0,
        "data_quality_score": 0.0,
    }
    draft.component_scores = component_scores
    draft.evidence = {
        "breakout_type": breakout_type,
        "level_strength": level,
        "breakout_score": breakout,
        "acceptance_score": acceptance,
        "follow_through_score": follow,
        "pullback_count": pullback_count,
        "major_reset": major_reset,
        "branch": branch,
    }
    draft.entry_plan = base_entry_plan(
        snapshot,
        entry_type="BREAK_TRIGGER" if branch == "IMMEDIATE_BREAKOUT" else "RETEST_TRIGGER",
        trigger=f"qualified_{branch.lower()}",
    )
    draft.invalidation = base_invalidation(snapshot)
    branch_allowed = {
        "IMMEDIATE_BREAKOUT": config.breakout_immediate_entry_enabled,
        "FIRST_MICRO_PULLBACK": config.breakout_first_pullback_enabled,
        "SECOND_MICRO_PULLBACK": config.breakout_second_pullback_enabled,
        "MAJOR_PULLBACK_REENTRY": config.breakout_major_pullback_reentry_enabled,
        "EXHAUSTED_MINOR_PULLBACKS": False,
    }[branch]
    draft.maturity = average([level, breakout, acceptance, follow]) or 0.0
    draft.eligible = (
        not draft.missing_critical
        and branch_allowed
        and (breakout or 0.0) >= 60.0
        and (not config.breakout_require_acceptance or (acceptance or 0.0) >= 55.0)
        and (not config.breakout_require_followthrough or (follow or 0.0) >= 50.0)
    )
    if branch == "EXHAUSTED_MINOR_PULLBACKS":
        draft.flags.append("MINOR_CONTINUATION_SEQUENCE_EXHAUSTED")
    return draft

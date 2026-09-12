from __future__ import annotations

from typing import Any, Mapping

from ..config import StrategyConfig
from ..models import dotted_get
from .common import PatternDraft, average, base_entry_plan, base_invalidation, bool_score, direction_from, score


def _opposite(direction: str) -> str:
    return "SHORT" if direction == "LONG" else "LONG" if direction == "SHORT" else "NONE"


def detect(snapshot: Mapping[str, Any], config: StrategyConfig) -> PatternDraft:
    original = direction_from(snapshot)
    direction = str(dotted_get(snapshot, "structure.reversal_direction", _opposite(original))).upper()
    if direction not in {"LONG", "SHORT"}:
        direction = "NONE"
    draft = PatternDraft("REVERSAL", direction, "LIQUIDITY_SWEEP_REVERSAL", False)
    extended = score(snapshot, "structure.extended_impulse_score")
    exhaustion = score(snapshot, "structure.exhaustion_score")
    liquidity = bool_score(snapshot, "levels.liquidity_sweep_reclaim")
    opposite_disp = score(snapshot, "structure.opposite_displacement_score")
    retest = score(snapshot, "structure.reversal_retest_score")
    micro = score(snapshot, "structure.opposite_micro_confirmation_score")
    absorption = score(snapshot, "orderflow.absorption_score")
    divergence = average([score(snapshot, "structure.rsi_divergence_score"), score(snapshot, "structure.macd_divergence_score")])
    if direction == "NONE":
        draft.missing_critical.append("reversal_direction")
    if extended is None or exhaustion is None:
        draft.missing_critical.append("extended_impulse_and_exhaustion")
    if config.reversal_require_liquidity_event and not (liquidity and liquidity >= 50.0):
        draft.missing_critical.append("liquidity_event")
    if config.reversal_require_opposite_displacement and not (opposite_disp and opposite_disp >= 55.0):
        draft.missing_critical.append("opposite_displacement")
    if config.reversal_require_micro_confirmation and not (micro and micro >= 55.0):
        draft.missing_critical.append("opposite_micro_confirmation")
    # Traditional divergence is deliberately secondary; at most a small timing contribution.
    divergence_secondary = min(35.0, divergence or 0.0)
    draft.component_scores = {
        "structure_quality": average([extended, exhaustion, opposite_disp]) or 0.0,
        "breakout_quality": score(snapshot, "breakout_alert.failed_retest_score") or 0.0,
        "location_quality": average([liquidity, retest]) or 0.0,
        "pullback_quality": retest or 0.0,
        "reengagement_quality": micro or 0.0,
        "orderflow_quality": average([absorption, score(snapshot, "orderflow.delta_divergence_score"), opposite_disp]) or 0.0,
        "volume_quality": score(snapshot, "structure.exhaustion_volume_score") or 0.0,
        "value_quality": score(snapshot, "volume_profile.reversal_value_shift_score") or 0.0,
        "liquidity_quality": liquidity or 0.0,
        "htf_context_quality": score(snapshot, "structure.htf_reversal_context_score") or 0.0,
        "target_quality": score(snapshot, "levels.target_room_score") or 50.0,
        "timing_quality": average([micro, divergence_secondary]) or 0.0,
        "data_quality_score": 0.0,
    }
    draft.evidence = {
        "extended_impulse": extended,
        "exhaustion": exhaustion,
        "liquidity_sweep_reclaim": liquidity,
        "opposite_displacement": opposite_disp,
        "retest": retest,
        "micro_confirmation": micro,
        "secondary_indicator_divergence": divergence,
    }
    draft.entry_plan = base_entry_plan(snapshot, entry_type="RETEST_TRIGGER", trigger="liquidity_event_plus_opposite_displacement_plus_micro_confirmation")
    draft.invalidation = base_invalidation(snapshot)
    draft.maturity = average([extended, exhaustion, liquidity, opposite_disp, retest, micro]) or 0.0
    draft.eligible = not draft.missing_critical and draft.maturity >= 60.0
    return draft

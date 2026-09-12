from __future__ import annotations

from typing import Any, Mapping

from ..models import clamp, dotted_get


def _n(snapshot: Mapping[str, Any], path: str) -> float | None:
    raw = dotted_get(snapshot, path)
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError):
        return None


def _b(snapshot: Mapping[str, Any], path: str) -> float | None:
    raw = dotted_get(snapshot, path)
    if raw is None:
        return None
    if isinstance(raw, bool):
        return 1.0 if raw else 0.0
    return _n(snapshot, path)


def _weighted(values: list[tuple[float | None, float]]) -> float | None:
    observed = [(value, weight) for value, weight in values if value is not None]
    if not observed:
        return None
    total_w = sum(weight for _, weight in observed)
    if total_w <= 0:
        return None
    return clamp(sum(float(value) * weight for value, weight in observed) / total_w * 100.0)


def balance_risk_score(snapshot: Mapping[str, Any]) -> float | None:
    regime = dotted_get(snapshot, "regime.type")
    regime_signal = 1.0 if regime in {"BALANCE", "RANGE"} else 0.0 if regime else None
    return _weighted(
        [
            (regime_signal, 1.8),
            (_n(snapshot, "structure.candle_overlap_score"), 1.0),
            (_n(snapshot, "structure.alternating_micro_bos"), 1.3),
            (_n(snapshot, "structure.extension_decay"), 1.1),
            (_n(snapshot, "volume_profile.poc_stagnation_score"), 1.3),
            (_n(snapshot, "volume_profile.poc_oscillation_score"), 1.0),
            (_n(snapshot, "volume_profile.horizontal_value_score"), 1.4),
            (_n(snapshot, "volume_profile.range_midpoint_cross_score"), 1.0),
            (_n(snapshot, "structure.time_without_progress_score"), 1.0),
        ]
    )


def chop_risk_score(snapshot: Mapping[str, Any]) -> float | None:
    both_sweeps = _n(snapshot, "structure.both_side_liquidity_sweeps")
    failed_expansion = _n(snapshot, "structure.repeated_failed_expansion_score")
    directional_efficiency_decay = _n(snapshot, "structure.directional_efficiency_decay")
    vwap_cross = _n(snapshot, "structure.vwap_crossing_score")
    return _weighted(
        [
            (_n(snapshot, "structure.alternating_micro_bos"), 1.4),
            (both_sweeps, 1.2),
            (failed_expansion, 1.2),
            (directional_efficiency_decay, 1.2),
            (vwap_cross, 1.0),
            (_n(snapshot, "volume_profile.horizontal_value_score"), 1.0),
        ]
    )


def failed_breakout_risk_score(snapshot: Mapping[str, Any]) -> float | None:
    no_follow = _n(snapshot, "breakout_alert.follow_through_score")
    if no_follow is not None:
        no_follow = 1.0 - no_follow
    no_value_migration = _n(snapshot, "volume_profile.value_migration_score")
    if no_value_migration is not None:
        no_value_migration = 1.0 - no_value_migration
    return _weighted(
        [
            (no_follow, 1.4),
            (_b(snapshot, "structure.return_inside_prior_range"), 1.5),
            (_b(snapshot, "structure.acceptance_inside_prior_range"), 1.7),
            (no_value_migration, 1.0),
            (_n(snapshot, "volume_profile.poc_stagnation_score"), 1.0),
            (_n(snapshot, "orderflow.aggression_without_progress_score"), 1.2),
            (_n(snapshot, "orderflow.opposite_absorption_score"), 1.2),
            (_n(snapshot, "breakout_alert.liquidation_burst_share"), 0.8),
            (_n(snapshot, "structure.extension_decay"), 0.8),
            (_n(snapshot, "breakout_alert.failed_retest_score"), 1.2),
        ]
    )


def reversal_risk_score(snapshot: Mapping[str, Any], direction: str) -> float | None:
    counter_damage = _n(snapshot, "structure.countertrend_structure_damage")
    pullback_disp = _n(snapshot, "structure.pullback_displacement_ratio")
    pullback_velocity = _n(snapshot, "structure.pullback_velocity_ratio")
    exhaustion = _n(snapshot, "structure.exhaustion_score")
    opposing = _n(snapshot, "orderflow.opposite_absorption_score")
    regime = dotted_get(snapshot, "regime.type")
    regime_signal = 1.0 if regime == "REVERSAL_RISK" else 0.0 if regime else None
    return _weighted(
        [
            (counter_damage, 1.5),
            (pullback_disp, 1.3),
            (pullback_velocity, 1.0),
            (exhaustion, 1.0),
            (opposing, 0.8),
            (regime_signal, 1.5),
        ]
    )


def data_quality_score(snapshot: Mapping[str, Any]) -> float:
    quality = str(snapshot.get("data_quality") or "")
    return {"GOOD": 100.0, "DEGRADED": 60.0, "STALE": 25.0, "INVALID": 0.0}.get(quality, 0.0)

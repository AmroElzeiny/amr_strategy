from __future__ import annotations

from typing import Any, Mapping

from ..config import StrategyConfig
from ..evidence import balance_risk_score, chop_risk_score, failed_breakout_risk_score, reversal_risk_score
from ..models import Penalty, dotted_get

PENALTY_CATALOG_VERSION = "HM_STRATEGY_PENALTIES_V1"
PENALTY_CODES = (
    "BALANCE_RISK",
    "CHOP_RISK",
    "FAILED_BREAKOUT_RISK",
    "REVERSAL_RISK",
    "LATE_ENTRY",
    "OVEREXTENDED_ENTRY",
    "WEAK_BREAKOUT",
    "WEAK_RETEST",
    "COUNTERTREND_PULLBACK_TOO_STRONG",
    "ORDERFLOW_CONTRADICTION",
    "VALUE_NOT_MIGRATING",
    "POC_STAGNATION",
    "HTF_COUNTER_STRUCTURE",
    "TARGET_OBSTRUCTION",
    "INSUFFICIENT_RR",
    "LIQUIDITY_WALL_AHEAD",
    "STALE_SIGNAL",
    "DEGRADED_DATA",
    "MISSING_CRITICAL_EVIDENCE",
    "THESIS_REPEAT",
    "ATTEMPT_EXHAUSTION",
    "DIRECTIONAL_EXHAUSTION",
    "LOW_FOLLOW_THROUGH",
)


def _sev(score: float) -> str:
    if score >= 80:
        return "CRITICAL"
    if score >= 65:
        return "HIGH"
    if score >= 45:
        return "MEDIUM"
    return "LOW"


def _fractional(base: float, score: float, *, activation: float = 45.0) -> float:
    if score < activation:
        return 0.0
    return min(base, base * (score - activation) / max(100.0 - activation, 1.0))


def build_penalties(
    snapshot: Mapping[str, Any],
    *,
    pattern_type: str,
    direction: str,
    risk_reward: float | None,
    missing_critical: list[str],
    attempt_no: int,
    config: StrategyConfig,
) -> tuple[Penalty, ...]:
    penalties: list[Penalty] = []
    balance = balance_risk_score(snapshot)
    chop = chop_risk_score(snapshot)
    failed = failed_breakout_risk_score(snapshot)
    reversal = reversal_risk_score(snapshot, direction)

    def add(code: str, score: float | None, deduction: float, root: str, refs: tuple[str, ...] = ()) -> None:
        if score is None:
            return
        amount = _fractional(deduction, score)
        if amount <= 0:
            return
        penalties.append(Penalty(code, _sev(score), amount, refs, False, root))

    add("BALANCE_RISK", balance, config.penalty_balance_risk, "balance")
    add("CHOP_RISK", chop, config.penalty_chop_risk, "balance")
    add("FAILED_BREAKOUT_RISK", failed, config.penalty_failed_breakout_risk, "failed_breakout")
    if pattern_type != "REVERSAL":
        add("REVERSAL_RISK", reversal, config.penalty_reversal_risk, "countertrend_strength")

    pullback_disp = dotted_get(snapshot, "structure.pullback_displacement_ratio")
    counter_damage = dotted_get(snapshot, "structure.countertrend_structure_damage")
    try:
        counter_score = max(float(pullback_disp or 0), float(counter_damage or 0)) * 100.0
    except (TypeError, ValueError):
        counter_score = 0.0
    if pattern_type != "REVERSAL":
        add(
            "COUNTERTREND_PULLBACK_TOO_STRONG",
            counter_score,
            config.penalty_countertrend_pullback,
            "countertrend_strength",
        )

    orderflow_contra = dotted_get(snapshot, "orderflow.contradiction_score")
    if orderflow_contra is not None:
        add(
            "ORDERFLOW_CONTRADICTION",
            float(orderflow_contra) * 100.0,
            config.penalty_orderflow_contradiction,
            "orderflow_contradiction",
        )

    value = dotted_get(snapshot, "volume_profile.value_migration_score")
    if value is not None:
        add(
            "VALUE_NOT_MIGRATING",
            (1.0 - float(value)) * 100.0,
            config.penalty_value_not_migrating,
            "value_stagnation",
        )
    poc = dotted_get(snapshot, "volume_profile.poc_stagnation_score")
    if poc is not None:
        add(
            "POC_STAGNATION",
            float(poc) * 100.0,
            config.penalty_poc_stagnation,
            "value_stagnation",
        )

    htf = dotted_get(snapshot, "structure.htf_counter_structure_score")
    if htf is not None:
        add(
            "HTF_COUNTER_STRUCTURE",
            float(htf) * 100.0,
            config.penalty_htf_counter_structure,
            "htf_counter_structure",
        )
    wall = dotted_get(snapshot, "orderbook.liquidity_wall_ahead_score")
    if wall is not None:
        add(
            "LIQUIDITY_WALL_AHEAD",
            float(wall) * 100.0,
            config.penalty_liquidity_wall,
            "target_obstruction",
        )
    obstruction = dotted_get(snapshot, "levels.obstacle_score")
    if obstruction is not None:
        add(
            "TARGET_OBSTRUCTION",
            float(obstruction) * 100.0,
            config.penalty_target_obstruction,
            "target_obstruction",
        )

    if risk_reward is not None and risk_reward < config.preferred_min_rr:
        severity_score = min(100.0, max(45.0, (config.preferred_min_rr - risk_reward) / max(config.preferred_min_rr, 0.01) * 100.0 + 45.0))
        add("INSUFFICIENT_RR", severity_score, config.penalty_insufficient_rr, "target_rr")

    quality = str(snapshot.get("data_quality") or "")
    if quality == "DEGRADED":
        penalties.append(Penalty("DEGRADED_DATA", "HIGH", config.penalty_degraded_data, (), False, "data_quality"))
    if quality == "STALE":
        penalties.append(Penalty("STALE_SIGNAL", "CRITICAL", config.penalty_stale_signal, (), False, "data_quality"))
    if missing_critical:
        penalties.append(Penalty("MISSING_CRITICAL_EVIDENCE", "HIGH", config.penalty_missing_critical_evidence, tuple(missing_critical), False, "missing_evidence"))
    if attempt_no > 0:
        penalties.append(Penalty("THESIS_REPEAT", "MEDIUM", config.penalty_thesis_repeat, (), False, "thesis_repeat"))
    if attempt_no >= config.max_strategy_attempts_per_thesis:
        penalties.append(Penalty("ATTEMPT_EXHAUSTION", "CRITICAL", config.penalty_attempt_exhaustion, (), True, "attempt_exhaustion"))

    exhaustion = dotted_get(snapshot, "structure.exhaustion_score")
    if exhaustion is not None and pattern_type != "REVERSAL":
        add("DIRECTIONAL_EXHAUSTION", float(exhaustion) * 100.0, config.penalty_directional_exhaustion, "directional_exhaustion")
    follow = dotted_get(snapshot, "breakout_alert.follow_through_score")
    if follow is not None:
        add("LOW_FOLLOW_THROUGH", (1.0 - float(follow)) * 100.0, config.penalty_low_follow_through, "follow_through")

    # Root-cause deduplication: retain only the strongest penalty within one root cause.
    strongest: dict[str, Penalty] = {}
    for penalty in penalties:
        root = penalty.root_cause or penalty.code
        prior = strongest.get(root)
        if prior is None:
            strongest[root] = penalty
        elif penalty.code == "REVERSAL_RISK" and prior.code == "COUNTERTREND_PULLBACK_TOO_STRONG":
            strongest[root] = penalty
        elif penalty.score_deduction > prior.score_deduction and prior.code != "REVERSAL_RISK":
            strongest[root] = penalty
    return tuple(sorted(strongest.values(), key=lambda p: p.code))

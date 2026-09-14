from __future__ import annotations

from typing import Mapping, Any

from ..config import StrategyConfig
from ..evidence import balance_risk_score, chop_risk_score, failed_breakout_risk_score, reversal_risk_score
from ..models import Blocker, dotted_get

BLOCKER_CODES = (
    "INVALID_DATA",
    "CRITICAL_DATA_STALE",
    "CONTRACT_MISMATCH",
    "UNSUPPORTED_SPOT_SHORT",
    "BALANCE_HARD_BLOCK",
    "FAILED_BREAKOUT_HARD_BLOCK",
    "INVALIDATED_STRUCTURE",
    "NO_TARGET_ROOM",
    "RR_BELOW_HARD_MIN",
    "THESIS_ATTEMPTS_EXHAUSTED",
    "SIGNAL_EXPIRED",
    "CONFLICTING_AUTHORITATIVE_EVIDENCE",
    "MISSING_REQUIRED_SETUP_EVIDENCE",
)


def build_blockers(
    snapshot: Mapping[str, Any],
    *,
    pattern_type: str,
    direction: str,
    missing_critical: list[str],
    risk_reward: float | None,
    attempt_no: int,
    validation_blockers: tuple[str, ...],
    config: StrategyConfig,
) -> tuple[Blocker, ...]:
    blockers: list[Blocker] = [Blocker(code, code.lower()) for code in validation_blockers]
    if snapshot.get("market_mode") == "SPOT" and direction == "SHORT":
        blockers.append(Blocker("UNSUPPORTED_SPOT_SHORT", "spot_opening_short_is_forbidden"))
    if missing_critical:
        blockers.append(Blocker("MISSING_REQUIRED_SETUP_EVIDENCE", "required_setup_evidence_unavailable", tuple(missing_critical)))
    balance = balance_risk_score(snapshot)
    chop = chop_risk_score(snapshot)
    failed = failed_breakout_risk_score(snapshot)
    reversal = reversal_risk_score(snapshot, direction)
    if config.balance_hard_block_enabled and (
        (balance is not None and balance >= config.balance_hard_block_score)
        or (chop is not None and chop >= config.chop_hard_block_score)
    ):
        blockers.append(Blocker("BALANCE_HARD_BLOCK", "balance_or_chop_risk_above_hard_threshold"))
    if (
        config.failed_breakout_hard_block_enabled
        and pattern_type in {"PRE_BREAKOUT", "BREAKOUT", "CONTINUATION"}
        and failed is not None
        and failed >= config.failed_breakout_hard_block_score
    ):
        blockers.append(Blocker("FAILED_BREAKOUT_HARD_BLOCK", "failed_breakout_risk_above_hard_threshold"))
    if pattern_type == "CONTINUATION" and reversal is not None and reversal >= config.reversal_risk_block_score:
        blockers.append(Blocker("INVALIDATED_STRUCTURE", "countertrend_or_reversal_risk_invalidates_continuation"))
    if bool(dotted_get(snapshot, "structure.major_structure_invalidated", False)):
        blockers.append(Blocker("INVALIDATED_STRUCTURE", "major_structure_invalidated"))
    if risk_reward is None:
        blockers.append(Blocker("NO_TARGET_ROOM", "target_or_invalidation_unavailable"))
    elif risk_reward < config.min_acceptable_rr:
        blockers.append(Blocker("RR_BELOW_HARD_MIN", "risk_reward_below_hard_minimum"))
    if attempt_no >= config.max_strategy_attempts_per_thesis:
        blockers.append(Blocker("THESIS_ATTEMPTS_EXHAUSTED", "maximum_attempts_for_thesis_exhausted"))
    if bool(dotted_get(snapshot, "structure.authoritative_conflict", False)):
        blockers.append(Blocker("CONFLICTING_AUTHORITATIVE_EVIDENCE", "authoritative_evidence_conflict"))
    unique: dict[str, Blocker] = {}
    for blocker in blockers:
        unique.setdefault(blocker.code, blocker)
    return tuple(unique.values())

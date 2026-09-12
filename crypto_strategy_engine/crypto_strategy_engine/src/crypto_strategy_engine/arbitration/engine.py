from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..models import Candidate

ARBITRATION_VERSION = "HM_STRATEGY_ARBITRATION_V1"


@dataclass(frozen=True)
class ArbitrationResult:
    selected: Candidate | None
    ambiguous: bool
    conflict: bool
    reason: str
    ranking: tuple[str, ...]


def _rank_score(candidate: Candidate) -> float:
    # Context-sensitive ranking, deliberately not a static pattern weight.
    regime = float(candidate.evidence.get("regime_compatibility", 50.0))
    structural = float(candidate.component_scores.get("structure_quality", 0.0))
    freshness = float(candidate.evidence.get("freshness_score", 100.0))
    independence = float(candidate.evidence.get("evidence_independence_score", min(100.0, len(candidate.evidence) * 8.0)))
    return (
        candidate.deterministic_confidence * 0.60
        + structural * 0.10
        + regime * 0.10
        + freshness * 0.05
        + candidate.target_room * 0.05
        + independence * 0.04
        + candidate.pattern_maturity * 0.06
    )


def _rank_key(candidate: Candidate) -> tuple[float, float, float]:
    return (0.0 if candidate.blockers else 1.0, _rank_score(candidate), candidate.deterministic_confidence)


def arbitrate(candidates: Sequence[Candidate], *, conflict_margin: float = 5.0) -> ArbitrationResult:
    if not candidates:
        return ArbitrationResult(None, False, False, "no_candidates", ())
    ranked = sorted(candidates, key=_rank_key, reverse=True)
    eligible = [c for c in ranked if not c.blockers]
    if not eligible:
        return ArbitrationResult(ranked[0], False, False, "all_candidates_blocked", tuple(c.candidate_id for c in ranked))
    top = eligible[0]
    if len(eligible) > 1:
        second = eligible[1]
        opposite = top.direction != second.direction and "NONE" not in {top.direction, second.direction}
        near = abs(_rank_score(top) - _rank_score(second)) <= conflict_margin
        if opposite and near:
            return ArbitrationResult(None, True, True, "unresolved_directional_conflict", tuple(c.candidate_id for c in ranked))
        ambiguous = near
    else:
        ambiguous = False
    return ArbitrationResult(top, ambiguous, False, "highest_contextual_quality", tuple(c.candidate_id for c in ranked))

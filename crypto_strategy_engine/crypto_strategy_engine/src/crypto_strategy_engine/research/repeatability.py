from __future__ import annotations

from collections import Counter
from statistics import pstdev
from typing import Any, Callable, Mapping, Sequence

REPEATABILITY_VERSION = "HM_AI_REPEATABILITY_V1"


def _mode_fraction(values: Sequence[Any]) -> float | None:
    if not values:
        return None
    counts = Counter(str(value) for value in values)
    return max(counts.values()) / len(values)


def measure_repeatability(responses: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Measure non-trading repeated AI-review stability.

    The result is diagnostic only; no metric produced here can grant live trading
    authority or replace deterministic market evidence.
    """

    rows = list(responses)
    verdicts = [row.get("verdict") for row in rows]
    vetoes = [bool(row.get("veto")) for row in rows]
    candidate_rankings = [tuple(row.get("candidate_ranking") or ()) for row in rows]
    scores = [float(row["qualitative_score"]) for row in rows if row.get("qualitative_score") is not None]
    reason_sets = [tuple(sorted(str(code) for code in row.get("veto_codes") or row.get("reason_codes") or ())) for row in rows]
    return {
        "repeatability_version": REPEATABILITY_VERSION,
        "research_only": True,
        "run_count": len(rows),
        "decision_agreement": _mode_fraction(verdicts),
        "veto_agreement": _mode_fraction(vetoes),
        "candidate_ranking_agreement": _mode_fraction(candidate_rankings),
        "confidence_variation": pstdev(scores) if len(scores) >= 2 else 0.0 if scores else None,
        "reason_code_stability": _mode_fraction(reason_sets),
    }


def run_repeatability_research(
    call: Callable[[], Mapping[str, Any]],
    *,
    runs: int,
) -> dict[str, Any]:
    if runs < 2:
        raise ValueError("repeatability_runs_must_be_at_least_2")
    responses = [dict(call()) for _ in range(runs)]
    return {"responses": responses, "metrics": measure_repeatability(responses)}

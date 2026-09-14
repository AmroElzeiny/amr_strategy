from __future__ import annotations

from typing import Any, Callable, Mapping

from ..models import canonical_hash

RESEARCH_HYPOTHESIS_VERSION = "HM_RESEARCH_HYPOTHESIS_V1"


def _hypothesis(question: str, basis: Mapping[str, Any]) -> dict[str, Any]:
    payload = {"question": question, "quantitative_basis": dict(basis)}
    return {
        "hypothesis_id": "hyp_" + canonical_hash(payload)[:20],
        "question": question,
        "quantitative_basis": dict(basis),
        "status": "REQUIRES_QUANTITATIVE_CONFIRMATION",
        "authority": "RESEARCH_HYPOTHESIS_ONLY",
    }


def build_quantitative_hypotheses(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Create bounded research questions from measured OOS artifacts, never facts."""

    hypotheses: list[dict[str, Any]] = []
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), Mapping) else {}
    false_breakout = metrics.get("false_breakout_loss_rate")
    balance = metrics.get("balance_trap_loss_rate")
    reversal = metrics.get("reversal_failure_rate")
    if false_breakout is not None:
        hypotheses.append(
            _hypothesis(
                "Do stricter acceptance/value-migration requirements reduce false-breakout losses OOS?",
                {"false_breakout_loss_rate": false_breakout},
            )
        )
    if balance is not None:
        hypotheses.append(
            _hypothesis(
                "Does a higher balance/chop rejection threshold improve continuation expectancy without excessive signal loss?",
                {"balance_trap_loss_rate": balance},
            )
        )
    if reversal is not None:
        hypotheses.append(
            _hypothesis(
                "Which reversal contexts need stronger liquidity-event or opposite-displacement confirmation?",
                {"reversal_failure_rate": reversal},
            )
        )
    for row in summary.get("feature_ablation") or ():
        if not isinstance(row, Mapping):
            continue
        impact = row.get("oos_impact_r")
        if impact is None:
            continue
        hypotheses.append(
            _hypothesis(
                f"Is feature/filter '{row.get('feature')}' stable enough to retain at its current authority?",
                {
                    "sample_size": row.get("sample_size"),
                    "oos_impact_r": impact,
                    "stability": row.get("stability"),
                },
            )
        )
    return hypotheses


def build_ai_research_artifact(
    summary: Mapping[str, Any],
    *,
    ai_interpreter: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Optionally add an AI interpretation to quantitative research questions.

    ``ai_interpreter`` is dependency-injected so unit tests and normal walk-forward
    runs never need network access. Returned AI material is deliberately marked as
    non-authoritative and cannot mutate champion/challenger configuration.
    """

    hypotheses = build_quantitative_hypotheses(summary)
    artifact: dict[str, Any] = {
        "version": RESEARCH_HYPOTHESIS_VERSION,
        "authority": "RESEARCH_ONLY",
        "auto_config_mutation_allowed": False,
        "quantitative_hypotheses": hypotheses,
        "ai_called": False,
        "ai_interpretation": None,
    }
    if ai_interpreter is None:
        return artifact
    safe_input = {
        "metrics": summary.get("metrics"),
        "pattern_metrics": summary.get("pattern_metrics"),
        "regime_metrics": summary.get("regime_metrics"),
        "feature_ablation": summary.get("feature_ablation"),
        "challenger_promotion_criteria": summary.get("challenger_promotion_criteria"),
        "instruction": "Return research hypotheses only; do not modify or promote live configuration.",
    }
    response = ai_interpreter(safe_input)
    if not isinstance(response, Mapping):
        raise ValueError("ai_research_response_not_object")
    artifact["ai_called"] = True
    artifact["ai_interpretation"] = dict(response)
    return artifact

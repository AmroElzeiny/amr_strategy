from __future__ import annotations

from ..config import StrategyConfig
from ..models import Penalty, clamp


def weighted_raw_score(component_scores: dict[str, float], config: StrategyConfig) -> float:
    weights = config.component_weights
    numerator = 0.0
    denominator = 0.0
    for name, weight in weights.items():
        if name not in component_scores:
            continue
        numerator += clamp(component_scores[name]) * weight
        denominator += weight
    return 0.0 if denominator <= 0 else clamp(numerator / denominator)


def penalty_total(penalties: tuple[Penalty, ...]) -> float:
    return sum(max(0.0, penalty.score_deduction) for penalty in penalties)


def deterministic_confidence(raw_score: float, penalties: tuple[Penalty, ...]) -> float:
    return clamp(raw_score - penalty_total(penalties))


def decision_from_confidence(confidence: float, config: StrategyConfig, *, hard_blocked: bool) -> str:
    if hard_blocked:
        return "NO_TRADE"
    if confidence >= config.enter_min_confidence:
        return "ENTER"
    if confidence >= config.armed_min_confidence:
        return "ARMED"
    if confidence >= config.watch_min_confidence:
        return "WATCH"
    return "NO_TRADE"

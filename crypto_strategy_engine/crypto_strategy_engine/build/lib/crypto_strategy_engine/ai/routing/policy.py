from __future__ import annotations

from dataclasses import dataclass

from ...config import StrategyConfig

ROUTING_POLICY_VERSION = "HM_AI_ROUTING_V1"


@dataclass(frozen=True)
class RouteStep:
    role: str
    provider: str
    model: str
    importance: str


def plan_route(
    deterministic_confidence: float,
    tentative_decision: str,
    config: StrategyConfig,
    *,
    ambiguous: bool = False,
) -> tuple[RouteStep, ...]:
    if not config.ai_enabled or deterministic_confidence < config.ai_call_min_deterministic_confidence:
        return ()
    muse = config.opencode_muse_model
    qwen = config.opencode_qwen_model
    if tentative_decision == "WATCH":
        return (RouteStep("ANALYST", "opencode", muse, "normal"),)
    if tentative_decision == "ARMED":
        if config.opencode_dual_review_enabled and ambiguous:
            return (
                RouteStep("ANALYST", "opencode", muse, "important"),
                RouteStep("CRITIC", "opencode", qwen, "important"),
            )
        return (RouteStep("ANALYST", "opencode", qwen, "important"),)
    if tentative_decision == "ENTER":
        if config.opencode_dual_review_enabled:
            return (
                RouteStep("ANALYST", "opencode", qwen, "critical"),
                RouteStep("CRITIC", "opencode", muse, "critical"),
            )
        return (RouteStep("ANALYST", "opencode", qwen, "critical"),)
    return ()

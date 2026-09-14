from __future__ import annotations

from ..models import HealthState


def aggregate_health(
    package_states: dict[str, str], *, reconciled: bool, emergency: bool = False
) -> HealthState:
    if emergency:
        return HealthState.EMERGENCY
    if not reconciled or package_states.get("risk") in {"BLOCKED", "UNHEALTHY"}:
        return HealthState.BLOCK_NEW_ENTRIES
    if any(value != "HEALTHY" for value in package_states.values()):
        return HealthState.DEGRADED
    return HealthState.HEALTHY


__all__ = ["aggregate_health"]

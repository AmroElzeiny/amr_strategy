"""Runtime coordination only; trading authority remains in the three owned packages."""

from .config import OrchestratorConfig
from .models import Event, EventType, HealthState, RuntimeState, SymbolState
from .runtime import TradingOrchestrator

ORCHESTRATOR_VERSION = "HM_ORCHESTRATOR_V1"
CONTRACT_VERSION = "HM_CRYPTO_V1"

__all__ = [
    "CONTRACT_VERSION",
    "ORCHESTRATOR_VERSION",
    "Event",
    "EventType",
    "HealthState",
    "OrchestratorConfig",
    "RuntimeState",
    "SymbolState",
    "TradingOrchestrator",
]

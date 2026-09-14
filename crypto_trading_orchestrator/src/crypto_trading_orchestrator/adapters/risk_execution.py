from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ..canonical import canonical_hash, primitive_dict


class RiskExecutionAdapter:
    """Only Package 3 may assess capital, size, reserve, execute, or manage positions."""

    def __init__(self, module: Any, *, settings: Any = None, adapter: Any = None, store: Any = None) -> None:
        for method in ("validate_trade_intent", "risk_assess", "execute_trade_intent", "reconcile_account"):
            if not callable(getattr(module, method, None)):
                raise ValueError(f"RISK_METHOD_MISSING:{method}")
        self.module = module
        self.settings = settings
        self.exchange_adapter = adapter
        self.store = store

    def validate(self, intent: Mapping[str, Any]) -> tuple[bool, tuple[str, ...]]:
        valid, reasons = self.module.validate_trade_intent(deepcopy(dict(intent)))
        return bool(valid), tuple(str(value) for value in reasons)

    def assess(self, intent: Mapping[str, Any]) -> Any:
        return self.module.risk_assess(
            deepcopy(dict(intent)), settings=self.settings, adapter=self.exchange_adapter, store=self.store
        )

    def execute(self, intent: Mapping[str, Any]) -> dict[str, Any]:
        before = canonical_hash(intent)
        result = self.module.execute_trade_intent(
            deepcopy(dict(intent)), settings=self.settings, adapter=self.exchange_adapter, store=self.store
        )
        if canonical_hash(intent) != before:
            raise RuntimeError("TRADE_INTENT_MUTATION_DETECTED")
        if hasattr(result, "to_dict") and callable(result.to_dict):
            result = result.to_dict()
        return primitive_dict(result)

    def reconcile(self) -> dict[str, Any]:
        return primitive_dict(
            self.module.reconcile_account(
                settings=self.settings, adapter=self.exchange_adapter, store=self.store
            )
        )

    def manage(self) -> dict[str, Any]:
        method = getattr(self.module, "manage_open_positions", None)
        if not callable(method):
            raise ValueError("RISK_METHOD_MISSING:manage_open_positions")
        return primitive_dict(method(settings=self.settings, adapter=self.exchange_adapter, store=self.store))

    def emergency(self, reason: str) -> dict[str, Any]:
        method = getattr(self.module, "emergency_flatten", None)
        if not callable(method):
            raise ValueError("RISK_METHOD_MISSING:emergency_flatten")
        return primitive_dict(
            method(reason=reason, settings=self.settings, adapter=self.exchange_adapter, store=self.store)
        )

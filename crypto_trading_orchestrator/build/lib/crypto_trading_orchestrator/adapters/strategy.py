from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime
from typing import Any

from ..canonical import canonical_hash, primitive_dict


class StrategyAdapter:
    """Invokes Package 2 and proves caller-owned inputs remain unchanged."""

    def __init__(self, module: Any) -> None:
        for method in (
            "validate_market_snapshot",
            "evaluate_snapshot",
            "ingest_execution_report",
            "run_walkforward",
        ):
            if not callable(getattr(module, method, None)):
                raise ValueError(f"STRATEGY_METHOD_MISSING:{method}")
        self.module = module

    def validate(self, snapshot: Mapping[str, Any], *, now_utc: datetime | None = None) -> Any:
        return self.module.validate_market_snapshot(snapshot, now_utc=now_utc)

    def evaluate(
        self,
        snapshot: Mapping[str, Any],
        *,
        persist: bool = True,
        now_utc: datetime | None = None,
    ) -> dict[str, Any]:
        before = canonical_hash(snapshot)
        frozen_input = deepcopy(dict(snapshot))
        result = primitive_dict(self.module.evaluate_snapshot(frozen_input, persist=persist, now_utc=now_utc))
        if canonical_hash(snapshot) != before:
            raise RuntimeError("SNAPSHOT_MUTATION_DETECTED")
        return result

    def ingest_execution_report(self, report: Mapping[str, Any]) -> dict[str, Any]:
        return primitive_dict(self.module.ingest_execution_report(deepcopy(dict(report))))

    def walkforward(
        self, records: Sequence[Mapping[str, Any]], output_dir: str | None = None
    ) -> dict[str, Any]:
        return primitive_dict(self.module.run_walkforward(records, output_dir=output_dir))

    def champion(self) -> dict[str, Any]:
        method = getattr(self.module, "get_champion_config", None)
        return primitive_dict(method()) if callable(method) else {}

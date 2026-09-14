from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..canonical import integrity_valid


def learning_eligible(report: Mapping[str, Any], *, reconciled: bool) -> bool:
    return (
        reconciled
        and bool(report.get("execution_id"))
        and bool(report.get("signal_id"))
        and integrity_valid(report)
    )


__all__ = ["learning_eligible"]

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def metrics_document(metrics: Mapping[str, Any], package_health: Mapping[str, str]) -> dict[str, Any]:
    return {"metrics": dict(metrics), "package_health": dict(package_health)}


__all__ = ["metrics_document"]

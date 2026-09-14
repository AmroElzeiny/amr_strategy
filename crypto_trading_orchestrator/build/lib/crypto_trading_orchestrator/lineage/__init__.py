from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def same_instrument(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return all(
        str(left.get(field, "")) == str(right.get(field, ""))
        for field in ("exchange", "environment", "market_mode", "symbol")
    )


__all__ = ["same_instrument"]

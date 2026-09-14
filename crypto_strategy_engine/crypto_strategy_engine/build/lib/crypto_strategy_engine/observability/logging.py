from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Mapping

from ..persistence import atomic_write_json

_SECRET_FRAGMENTS = ("api_key", "authorization", "secret", "token")


def _sanitize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: ("<redacted>" if any(s in str(k).lower() for s in _SECRET_FRAGMENTS) else _sanitize(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    return value


def write_decision_log(directory: str | Path, signal_id: str, payload: Mapping[str, Any]) -> Path:
    path = Path(directory) / f"{signal_id}.json"
    atomic_write_json(path, _sanitize(dict(payload)))
    return path

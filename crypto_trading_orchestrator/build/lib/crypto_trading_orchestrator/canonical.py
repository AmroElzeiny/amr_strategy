from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


def primitive(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return primitive(dataclasses.asdict(value))
    if hasattr(value, "model_dump"):
        return primitive(value.model_dump(mode="json"))
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return primitive(value.to_dict())
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("naive_datetime_forbidden")
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return primitive(value.value)
    if isinstance(value, Mapping):
        return {str(key): primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [primitive(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"unsupported_transport_type:{type(value).__name__}")


def primitive_dict(value: Any) -> dict[str, Any]:
    result = primitive(value)
    if not isinstance(result, dict):
        raise TypeError("transport_object_required")
    return result


def canonical_json(value: Any) -> str:
    return json.dumps(
        primitive(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def payload_integrity_hash(payload: Mapping[str, Any]) -> str:
    return canonical_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def integrity_valid(payload: Mapping[str, Any]) -> bool:
    return bool(payload.get("integrity_hash")) and str(payload["integrity_hash"]) == payload_integrity_hash(
        payload
    )


def parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("utc_z_required")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError("utc_required")
    return parsed


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_text(value: datetime | None = None) -> str:
    return (value or utc_now()).astimezone(UTC).isoformat().replace("+00:00", "Z")

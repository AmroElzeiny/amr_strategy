from __future__ import annotations
from decimal import Decimal
from datetime import datetime, timezone
import hashlib, json
from typing import Any

def utc_now() -> datetime: return datetime.now(timezone.utc)
def utc_iso() -> str: return utc_now().isoformat().replace('+00:00','Z')
def D(value: Any) -> Decimal:
    if isinstance(value, Decimal): return value
    if value is None: raise ValueError('missing_decimal')
    d=Decimal(str(value))
    if not d.is_finite(): raise ValueError('non_finite_decimal')
    return d

def _default(v: Any):
    if isinstance(v, Decimal): return format(v,'f')
    if isinstance(v, datetime):
        if v.tzinfo is None: raise ValueError('naive_datetime')
        return v.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
    raise TypeError(type(v).__name__)
def canonical_json(v: Any) -> str:
    return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False,default=_default)
def sha256_json(v: Any) -> str: return hashlib.sha256(canonical_json(v).encode()).hexdigest()

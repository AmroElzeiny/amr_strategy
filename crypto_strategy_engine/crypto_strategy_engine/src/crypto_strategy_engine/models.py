from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any, Mapping

CONTRACT_VERSION = "HM_CRYPTO_V1"
STRATEGY_VERSION = "HM_STRATEGY_V1"
CONFIG_VERSION = "HM_STRATEGY_CONFIG_V1"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def canonical_hash(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def decimal_from(value: Any, *, name: str = "value") -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{name}:decimal_required")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{name}:invalid_decimal") from exc
    if not number.is_finite():
        raise ValueError(f"{name}:non_finite_decimal")
    return number


def decimal_text(value: Decimal | str | int | float) -> str:
    number = decimal_from(value)
    text = format(number.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def dotted_get(data: Mapping[str, Any], path: str, default: Any = None) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return default
        current = current[part]
    return current


@dataclass(frozen=True)
class Penalty:
    code: str
    severity: str
    score_deduction: float
    evidence_refs: tuple[str, ...] = ()
    hard_block: bool = False
    root_cause: str = ""

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["evidence_refs"] = list(self.evidence_refs)
        return row


@dataclass(frozen=True)
class Blocker:
    code: str
    reason: str
    evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["evidence_refs"] = list(self.evidence_refs)
        return row


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    candidate_hash: str
    pattern_type: str
    direction: str
    branch: str
    thesis_id: str
    attempt_no: int
    component_scores: dict[str, float]
    raw_score: float
    penalties: tuple[Penalty, ...]
    blockers: tuple[Blocker, ...]
    deterministic_confidence: float
    evidence: dict[str, Any]
    entry_plan: dict[str, Any]
    invalidation: dict[str, Any]
    targets: tuple[dict[str, Any], ...]
    projected_extension_target: str | None
    risk_reward: float | None
    pattern_maturity: float
    target_room: float
    strategic_risk_hint: str

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["penalties"] = [p.to_dict() for p in self.penalties]
        row["blockers"] = [b.to_dict() for b in self.blockers]
        row["targets"] = list(self.targets)
        return row


@dataclass(frozen=True)
class AIResult:
    valid: bool
    request_id: str
    request_identity_hash: str
    candidate_id: str
    candidate_hash: str
    role: str
    verdict: str
    thesis_supported: bool
    qualitative_score: float | None
    confidence_band: str
    veto: bool
    veto_codes: tuple[str, ...]
    material_contradictions: tuple[str, ...]
    missing_confirmations: tuple[str, ...]
    major_risks: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    summary: str
    provider_id: str
    model_id: str
    provider_request_id: str
    latency_ms: int
    failure_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        for key in (
            "veto_codes",
            "material_contradictions",
            "missing_confirmations",
            "major_risks",
            "evidence_refs",
        ):
            row[key] = list(row[key])
        return row


@dataclass(frozen=True)
class EvaluationResult:
    trade_intent: dict[str, Any]
    candidates: tuple[Candidate, ...] = field(default_factory=tuple)
    latency_ms: dict[str, float] = field(default_factory=dict)

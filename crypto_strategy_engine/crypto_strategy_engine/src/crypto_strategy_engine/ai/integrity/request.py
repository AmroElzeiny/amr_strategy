from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

from ...models import canonical_hash, canonical_json

AI_REQUEST_IDENTITY_VERSION = "HM_AI_REQUEST_IDENTITY_V1"


@dataclass(frozen=True)
class FrozenAIRequest:
    request_id: str
    request_identity_hash: str
    candidate_id: str
    candidate_hash: str
    snapshot_id: str
    config_version: str
    strategy_version: str
    schema_hash: str
    provider_identity: str
    role: str
    frozen_payload: dict[str, Any]


def freeze_ai_request(
    *,
    candidate: Mapping[str, Any],
    snapshot_id: str,
    config_version: str,
    strategy_version: str,
    schema_hash: str,
    provider_identity: str,
    role: str,
    evidence_catalog: list[dict[str, Any]],
) -> FrozenAIRequest:
    payload = {
        "identity_version": AI_REQUEST_IDENTITY_VERSION,
        "candidate": dict(candidate),
        "snapshot_id": snapshot_id,
        "config_version": config_version,
        "strategy_version": strategy_version,
        "schema_hash": schema_hash,
        "provider_identity": provider_identity,
        "role": role,
        "evidence_catalog": evidence_catalog,
    }
    frozen = json.loads(canonical_json(payload))
    identity_hash = canonical_hash(frozen)
    request_id = "aireq_" + identity_hash[:24]
    return FrozenAIRequest(
        request_id=request_id,
        request_identity_hash=identity_hash,
        candidate_id=str(candidate["candidate_id"]),
        candidate_hash=str(candidate["candidate_hash"]),
        snapshot_id=snapshot_id,
        config_version=config_version,
        strategy_version=strategy_version,
        schema_hash=schema_hash,
        provider_identity=provider_identity,
        role=role,
        frozen_payload=frozen,
    )


def frozen_request_unchanged(request: FrozenAIRequest) -> bool:
    return canonical_hash(request.frozen_payload) == request.request_identity_hash

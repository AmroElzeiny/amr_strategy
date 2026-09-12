from __future__ import annotations

from typing import Any, Mapping

AI_ASSESSMENT_SCHEMA_VERSION = "HM_AI_ASSESSMENT_V1"
VERDICTS = {"SUPPORT", "DOWNGRADE", "VETO", "ABSTAIN"}
CONFIDENCE_BANDS = {"LOW", "MEDIUM", "HIGH"}
ROLES = {"ANALYST", "CRITIC", "ADJUDICATOR"}

AI_ASSESSMENT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "request_id",
        "request_identity_hash",
        "candidate_id",
        "candidate_hash",
        "role",
        "verdict",
        "thesis_supported",
        "qualitative_score",
        "confidence_band",
        "veto",
        "veto_codes",
        "material_contradictions",
        "missing_confirmations",
        "major_risks",
        "evidence_refs",
        "summary",
        "provider_id",
        "model_id",
        "provider_request_id",
        "latency_ms",
    ],
    "properties": {
        "request_id": {"type": "string"},
        "request_identity_hash": {"type": "string"},
        "candidate_id": {"type": "string"},
        "candidate_hash": {"type": "string"},
        "role": {"enum": sorted(ROLES)},
        "verdict": {"enum": sorted(VERDICTS)},
        "thesis_supported": {"type": "boolean"},
        "qualitative_score": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
        "confidence_band": {"enum": sorted(CONFIDENCE_BANDS)},
        "veto": {"type": "boolean"},
        "veto_codes": {"type": "array", "items": {"type": "string"}},
        "material_contradictions": {"type": "array", "items": {"type": "string"}},
        "missing_confirmations": {"type": "array", "items": {"type": "string"}},
        "major_risks": {"type": "array", "items": {"type": "string"}},
        "evidence_refs": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "summary": {"type": "string", "maxLength": 900},
        "provider_id": {"type": "string"},
        "model_id": {"type": "string"},
        "provider_request_id": {"type": "string"},
        "latency_ms": {"type": "integer", "minimum": 0},
    },
}


def validate_shape(value: Mapping[str, Any]) -> tuple[bool, str]:
    required = AI_ASSESSMENT_JSON_SCHEMA["required"]
    missing = [name for name in required if name not in value]
    if missing:
        return False, "missing_fields:" + ",".join(missing)
    if set(value) - set(AI_ASSESSMENT_JSON_SCHEMA["properties"]):
        return False, "unexpected_fields"
    if value.get("role") not in ROLES:
        return False, "role_enum"
    if value.get("verdict") not in VERDICTS:
        return False, "verdict_enum"
    if value.get("confidence_band") not in CONFIDENCE_BANDS:
        return False, "confidence_band_enum"
    if not isinstance(value.get("thesis_supported"), bool) or not isinstance(value.get("veto"), bool):
        return False, "boolean_fields"
    quality = value.get("qualitative_score")
    if quality is not None and (not isinstance(quality, (int, float)) or isinstance(quality, bool) or not 0 <= float(quality) <= 100):
        return False, "qualitative_score_range"
    for name in ("veto_codes", "material_contradictions", "missing_confirmations", "major_risks", "evidence_refs"):
        if not isinstance(value.get(name), list) or not all(isinstance(item, str) for item in value[name]):
            return False, f"{name}_type"
    if not value["evidence_refs"]:
        return False, "evidence_refs_empty"
    if not isinstance(value.get("latency_ms"), int) or value["latency_ms"] < 0:
        return False, "latency_type"
    return True, "ok"

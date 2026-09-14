from __future__ import annotations

import json
import os
from typing import Any, Callable, Mapping

from ...config import StrategyConfig
from ..integrity import FrozenAIRequest
from ..schemas import AI_ASSESSMENT_JSON_SCHEMA
from .http import ProviderTransportError, get_json, post_json

Transport = Callable[[str, Mapping[str, Any], Mapping[str, str], float], dict[str, Any]]


def _extract_responses_text(response: Mapping[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return str(response["output_text"])
    output = response.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, Mapping):
                continue
            content = item.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, Mapping) and part.get("type") in {"output_text", "text"} and isinstance(part.get("text"), str):
                        return str(part["text"])
    raise ProviderTransportError("INVALID_PROVIDER_RESPONSE", "responses_text_missing")


def _extract_messages_text(response: Mapping[str, Any]) -> str:
    content = response.get("content")
    if isinstance(content, list):
        for part in content:
            if isinstance(part, Mapping) and part.get("type") == "text" and isinstance(part.get("text"), str):
                return str(part["text"])
    raise ProviderTransportError("INVALID_PROVIDER_RESPONSE", "messages_text_missing")


class OpenCodeGoProvider:
    """Protocol-aware OpenCode Go transport.

    Current official mapping verified 2026-09-12:
      - qwen3.8-flash -> /v1/messages (Anthropic-compatible)
      - muse-spark-1.3-contributor -> /v1/responses (OpenAI Responses-compatible)
    """

    def __init__(self, config: StrategyConfig, *, transport: Transport = post_json) -> None:
        self.config = config
        self.transport = transport
        self.api_key = os.getenv("OPENCODE_GO_API_KEY", "").strip()

    def headers(self, request_id: str) -> dict[str, str]:
        if not self.api_key:
            raise ProviderTransportError("CONFIGURATION_ERROR", "OPENCODE_GO_API_KEY_missing")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "x-opencode-session": request_id,
        }

    def endpoint_for_model(self, model_id: str) -> str:
        base = self.config.opencode_go_base_url.rstrip("/")
        if model_id == self.config.opencode_qwen_model:
            return base + "/v1/messages"
        if model_id == self.config.opencode_muse_model:
            return base + "/v1/responses"
        raise ProviderTransportError("UNSUPPORTED_MODEL_PROTOCOL", model_id)

    def model_available(self, model_id: str) -> bool:
        base = self.config.opencode_go_base_url.rstrip("/")
        headers = self.headers("model-discovery")
        payload = get_json(base + "/v1/models", headers, self.config.ai_provider_timeout_ms / 1000.0)
        rows = payload.get("data") or payload.get("models") or []
        if not isinstance(rows, list):
            return False
        ids = {
            str(row.get("id"))
            for row in rows
            if isinstance(row, Mapping) and row.get("id") is not None
        }
        return model_id in ids

    def generate(self, request: FrozenAIRequest, *, model_id: str, role: str) -> tuple[dict[str, Any], str]:
        endpoint = self.endpoint_for_model(model_id)
        headers = self.headers(request.request_id)
        timeout = self.config.ai_provider_timeout_ms / 1000.0
        system = (
            "You are an evidence-bound trading setup reviewer. Never invent market facts or prices. "
            "Use only evidence_catalog entries in the frozen request. Hard blockers cannot be removed. "
            "Return exactly one JSON object matching the supplied schema."
        )
        user_payload = {
            "request_id": request.request_id,
            "request_identity_hash": request.request_identity_hash,
            "candidate_id": request.candidate_id,
            "candidate_hash": request.candidate_hash,
            "role": role,
            "frozen_request": request.frozen_payload,
            "required_json_schema": AI_ASSESSMENT_JSON_SCHEMA,
        }
        if endpoint.endswith("/responses"):
            body = {
                "model": model_id,
                "input": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(user_payload, separators=(",", ":"), ensure_ascii=False)},
                ],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "hm_ai_assessment",
                        "schema": AI_ASSESSMENT_JSON_SCHEMA,
                        "strict": True,
                    }
                },
                "max_output_tokens": self.config.openai_max_output_tokens,
            }
            response = self.transport(endpoint, body, headers, timeout)
            return json.loads(_extract_responses_text(response)), str(response.get("id") or "")
        body = {
            "model": model_id,
            "max_tokens": self.config.openai_max_output_tokens,
            "system": system + " Schema: " + json.dumps(AI_ASSESSMENT_JSON_SCHEMA, separators=(",", ":")),
            "messages": [
                {"role": "user", "content": json.dumps(user_payload, separators=(",", ":"), ensure_ascii=False)}
            ],
        }
        response = self.transport(endpoint, body, headers, timeout)
        return json.loads(_extract_messages_text(response)), str(response.get("id") or "")

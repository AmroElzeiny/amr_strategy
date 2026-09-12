from __future__ import annotations

import json
import os
from typing import Any, Callable, Mapping

from ...config import StrategyConfig
from ..integrity import FrozenAIRequest
from ..schemas import AI_ASSESSMENT_JSON_SCHEMA
from .http import ProviderTransportError, post_json

Transport = Callable[[str, Mapping[str, Any], Mapping[str, str], float], dict[str, Any]]


def _extract_text(response: Mapping[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return str(response["output_text"])
    output = response.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, Mapping):
                continue
            for part in item.get("content", []) if isinstance(item.get("content"), list) else []:
                if isinstance(part, Mapping) and isinstance(part.get("text"), str):
                    return str(part["text"])
    raise ProviderTransportError("INVALID_PROVIDER_RESPONSE", "output_text_missing")


class OpenAIFallbackProvider:
    def __init__(self, config: StrategyConfig, *, transport: Transport = post_json) -> None:
        self.config = config
        self.transport = transport
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()

    def generate(self, request: FrozenAIRequest, *, role: str) -> tuple[dict[str, Any], str]:
        if not self.api_key:
            raise ProviderTransportError("CONFIGURATION_ERROR", "OPENAI_API_KEY_missing")
        url = self.config.openai_base_url.rstrip("/") + "/v1/responses"
        body = {
            "model": self.config.openai_fallback_model,
            "reasoning": {"effort": self.config.openai_reasoning_effort},
            "service_tier": self.config.openai_service_tier,
            "input": [
                {
                    "role": "system",
                    "content": "Evidence-bound trading setup reviewer. Do not invent facts. Return only schema-valid JSON.",
                },
                {
                    "role": "user",
                    "content": json.dumps(request.frozen_payload, separators=(",", ":"), ensure_ascii=False),
                },
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
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = self.transport(url, body, headers, self.config.openai_timeout_sec)
        return json.loads(_extract_text(response)), str(response.get("id") or "")

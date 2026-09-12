from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Mapping


class ProviderTransportError(RuntimeError):
    def __init__(self, failure_type: str, message: str) -> None:
        self.failure_type = failure_type
        super().__init__(f"{failure_type}:{message}")


def post_json(
    url: str,
    payload: Mapping[str, Any],
    headers: Mapping[str, str],
    timeout_sec: float,
) -> dict[str, Any]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("User-Agent", "hm-crypto-strategy-engine/1.0")
    for key, value in headers.items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            raw = response.read().decode("utf-8")
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ProviderTransportError("INVALID_PROVIDER_RESPONSE", "response_root_not_object")
            return value
    except urllib.error.HTTPError as exc:
        category = "AUTHENTICATION_FAILED" if exc.code == 401 else "PERMISSION_DENIED" if exc.code == 403 else "HTTP_ERROR"
        raise ProviderTransportError(category, f"http_{exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ProviderTransportError("NETWORK_ERROR", type(exc.reason).__name__) from exc
    except TimeoutError as exc:
        raise ProviderTransportError("TIMEOUT", "provider_timeout") from exc
    except json.JSONDecodeError as exc:
        raise ProviderTransportError("INVALID_PROVIDER_RESPONSE", "non_json_response") from exc


def get_json(url: str, headers: Mapping[str, str], timeout_sec: float) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET")
    request.add_header("User-Agent", "hm-crypto-strategy-engine/1.0")
    for key, value in headers.items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            value = json.loads(response.read().decode("utf-8"))
            if not isinstance(value, dict):
                raise ProviderTransportError("INVALID_PROVIDER_RESPONSE", "models_root_not_object")
            return value
    except Exception as exc:
        if isinstance(exc, ProviderTransportError):
            raise
        raise ProviderTransportError("MODEL_DISCOVERY_FAILED", type(exc).__name__) from exc

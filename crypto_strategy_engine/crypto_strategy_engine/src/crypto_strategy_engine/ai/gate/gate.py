from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Mapping

from ...config import StrategyConfig
from ...evidence import EvidenceCatalog, validate_evidence_refs
from ...models import AIResult, Candidate, clamp
from ..integrity import freeze_ai_request, frozen_request_unchanged
from ..providers import OpenAIFallbackProvider, OpenCodeGoProvider, ProviderTransportError
from ..routing import RouteStep, plan_route
from ..schemas import validate_shape


@dataclass(frozen=True)
class AIGateOutcome:
    results: tuple[AIResult, ...]
    ai_confidence: float | None
    adjustment: float
    veto: bool
    failure_log: tuple[dict[str, Any], ...]
    route: tuple[dict[str, str], ...]
    required_failed: bool


def _semantic_validate(
    raw: Mapping[str, Any],
    *,
    request_id: str,
    request_identity_hash: str,
    candidate: Candidate,
    role: str,
    catalog: EvidenceCatalog,
) -> tuple[bool, str]:
    valid, reason = validate_shape(raw)
    if not valid:
        return False, reason
    if raw.get("request_id") != request_id:
        return False, "request_id_mismatch"
    if raw.get("request_identity_hash") != request_identity_hash:
        return False, "request_identity_hash_mismatch"
    if raw.get("candidate_id") != candidate.candidate_id:
        return False, "candidate_id_mismatch"
    if raw.get("candidate_hash") != candidate.candidate_hash:
        return False, "candidate_hash_mismatch"
    if raw.get("role") != role:
        return False, "role_mismatch"
    refs = raw.get("evidence_refs")
    if not isinstance(refs, list) or not validate_evidence_refs(catalog, refs):
        return False, "invented_or_duplicate_evidence_ref"
    return True, "ok"


def _to_result(
    raw: Mapping[str, Any],
    *,
    provider_id: str,
    model_id: str,
    provider_request_id: str,
    latency_ms: int,
) -> AIResult:
    return AIResult(
        valid=True,
        request_id=str(raw["request_id"]),
        request_identity_hash=str(raw["request_identity_hash"]),
        candidate_id=str(raw["candidate_id"]),
        candidate_hash=str(raw["candidate_hash"]),
        role=str(raw["role"]),
        verdict=str(raw["verdict"]),
        thesis_supported=bool(raw["thesis_supported"]),
        qualitative_score=float(raw["qualitative_score"]) if raw["qualitative_score"] is not None else None,
        confidence_band=str(raw["confidence_band"]),
        veto=bool(raw["veto"]),
        veto_codes=tuple(str(v) for v in raw["veto_codes"]),
        material_contradictions=tuple(str(v) for v in raw["material_contradictions"]),
        missing_confirmations=tuple(str(v) for v in raw["missing_confirmations"]),
        major_risks=tuple(str(v) for v in raw["major_risks"]),
        evidence_refs=tuple(str(v) for v in raw["evidence_refs"]),
        summary=str(raw["summary"]),
        provider_id=provider_id,
        model_id=model_id,
        provider_request_id=provider_request_id,
        latency_ms=latency_ms,
    )


class AIGate:
    def __init__(
        self,
        config: StrategyConfig,
        *,
        opencode: OpenCodeGoProvider | None = None,
        openai: OpenAIFallbackProvider | None = None,
    ) -> None:
        self.config = config
        self.opencode = opencode or OpenCodeGoProvider(config)
        self.openai = openai or OpenAIFallbackProvider(config)

    def _call_step(
        self,
        step: RouteStep,
        *,
        candidate: Candidate,
        snapshot_id: str,
        schema_hash: str,
        catalog: EvidenceCatalog,
        started: float,
    ) -> tuple[AIResult | None, list[dict[str, Any]]]:
        failures: list[dict[str, Any]] = []
        provider_order = [("opencode", step.model)]
        other = (
            self.config.opencode_muse_model
            if step.model == self.config.opencode_qwen_model
            else self.config.opencode_qwen_model
        )
        if other != step.model:
            provider_order.append(("opencode", other))
        if self.config.openai_fallback_enabled:
            provider_order.append(("openai", self.config.openai_fallback_model))

        for provider_index, (provider_name, model_id) in enumerate(provider_order):
            elapsed_ms = int((time.monotonic() - started) * 1000)
            if elapsed_ms >= self.config.ai_total_deadline_ms:
                failures.append({"provider": provider_name, "model": model_id, "failure_type": "TOTAL_DEADLINE_EXCEEDED", "fallback_used": provider_name != step.provider or model_id != step.model})
                break
            request = freeze_ai_request(
                candidate=candidate.to_dict(),
                snapshot_id=snapshot_id,
                config_version=self.config.config_version,
                strategy_version=self.config.strategy_version,
                schema_hash=schema_hash,
                provider_identity=f"{provider_name}:{model_id}",
                role=step.role,
                evidence_catalog=catalog.provider_view(),
            )
            if not frozen_request_unchanged(request):
                failures.append({"provider": provider_name, "model": model_id, "failure_type": "FROZEN_REQUEST_MUTATION", "fallback_used": provider_name != step.provider or model_id != step.model})
                continue
            call_started = time.monotonic()
            try:
                if provider_name == "opencode":
                    raw, provider_request_id = self.opencode.generate(request, model_id=model_id, role=step.role)
                else:
                    raw, provider_request_id = self.openai.generate(request, role=step.role)
                latency_ms = int((time.monotonic() - call_started) * 1000)
                if int((time.monotonic() - started) * 1000) >= self.config.ai_total_deadline_ms:
                    failures.append({"provider": provider_name, "model": model_id, "failure_type": "LATE_RESPONSE", "fallback_used": provider_name != step.provider or model_id != step.model})
                    continue
                # Provider-owned fields are deterministic transport metadata, never trusted from model text.
                raw = dict(raw)
                raw["provider_id"] = provider_name
                raw["model_id"] = model_id
                raw["provider_request_id"] = provider_request_id
                raw["latency_ms"] = latency_ms
                valid, reason = _semantic_validate(
                    raw,
                    request_id=request.request_id,
                    request_identity_hash=request.request_identity_hash,
                    candidate=candidate,
                    role=step.role,
                    catalog=catalog,
                )
                if not valid:
                    failures.append({"provider": provider_name, "model": model_id, "failure_type": "STRUCTURED_RESPONSE_INVALID:" + reason, "fallback_used": provider_name != step.provider or model_id != step.model})
                    continue
                return _to_result(raw, provider_id=provider_name, model_id=model_id, provider_request_id=provider_request_id, latency_ms=latency_ms), failures
            except (ProviderTransportError, ValueError, TypeError, KeyError) as exc:
                failure_type = exc.failure_type if isinstance(exc, ProviderTransportError) else type(exc).__name__
                failures.append({"provider": provider_name, "model": model_id, "failure_type": failure_type, "fallback_used": provider_index < len(provider_order) - 1})
        return None, failures

    def assess(
        self,
        candidate: Candidate,
        *,
        tentative_decision: str,
        snapshot_id: str,
        schema_hash: str,
        catalog: EvidenceCatalog,
        ttl_ms: int,
        ambiguous: bool = False,
    ) -> AIGateOutcome:
        route = plan_route(candidate.deterministic_confidence, tentative_decision, self.config, ambiguous=ambiguous)
        if not route:
            required_failed = tentative_decision == "ENTER" and self.config.ai_required_for_enter
            return AIGateOutcome((), None, 0.0, False, (), (), required_failed)
        started = time.monotonic()
        results: list[AIResult] = []
        failures: list[dict[str, Any]] = []
        executed_route = list(route)
        for step in route:
            if int((time.monotonic() - started) * 1000) >= min(ttl_ms, self.config.ai_total_deadline_ms):
                failures.append({"provider": step.provider, "model": step.model, "failure_type": "SIGNAL_TTL_EXPIRED", "fallback_used": False})
                break
            result, step_failures = self._call_step(
                step,
                candidate=candidate,
                snapshot_id=snapshot_id,
                schema_hash=schema_hash,
                catalog=catalog,
                started=started,
            )
            failures.extend(step_failures)
            if result is not None:
                results.append(result)

        # A third role is called only when two independent reviews materially disagree
        # or the deterministic candidate sits very close to the ENTER threshold.
        materially_disagree = (
            len(results) >= 2
            and (results[0].veto != results[1].veto
                 or results[0].verdict != results[1].verdict
                 or (results[0].qualitative_score is not None and results[1].qualitative_score is not None
                     and abs(results[0].qualitative_score - results[1].qualitative_score) >= 15.0))
        )
        threshold_critical = abs(candidate.deterministic_confidence - self.config.enter_min_confidence) <= 2.0
        if self.config.ai_adjudicator_enabled and len(results) >= 2 and (materially_disagree or threshold_critical):
            adjudicator = RouteStep("ADJUDICATOR", "opencode", self.config.ai_adjudicator_model, "critical")
            executed_route.append(adjudicator)
            result, step_failures = self._call_step(
                adjudicator, candidate=candidate, snapshot_id=snapshot_id, schema_hash=schema_hash,
                catalog=catalog, started=started,
            )
            failures.extend(step_failures)
            if result is not None:
                results.append(result)

        veto = any(result.veto or result.verdict == "VETO" for result in results)
        scores = [result.qualitative_score for result in results if result.qualitative_score is not None]
        ai_confidence = sum(scores) / len(scores) if scores else None
        if veto:
            adjustment = -self.config.ai_max_negative_adjustment
        elif ai_confidence is None:
            adjustment = 0.0
        else:
            delta = ai_confidence - candidate.deterministic_confidence
            if delta >= 0:
                adjustment = min(self.config.ai_max_positive_adjustment, delta * 0.10)
            else:
                adjustment = max(-self.config.ai_max_negative_adjustment, delta * 0.25)
        required_failed = tentative_decision == "ENTER" and self.config.ai_required_for_enter and not results
        return AIGateOutcome(
            tuple(results),
            ai_confidence,
            clamp(adjustment, -self.config.ai_max_negative_adjustment, self.config.ai_max_positive_adjustment),
            veto,
            tuple(failures),
            tuple({"role": step.role, "provider": step.provider, "model": step.model, "importance": step.importance} for step in executed_route),
            required_failed,
        )

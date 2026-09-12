from __future__ import annotations

from dataclasses import replace
import time

from crypto_strategy_engine.ai.gate import AIGate
from crypto_strategy_engine.ai.providers import ProviderTransportError
from crypto_strategy_engine.ai.routing import plan_route
from crypto_strategy_engine.evidence import build_evidence_catalog
from crypto_strategy_engine import evaluate_candidates, evaluate_snapshot
from crypto_strategy_engine.validation import schema_sha256
from conftest import event_time, load_fixture


def _response(req, role, ref, *, score=90.0, veto=False, bad_ref=False, bad_hash=False):
    return {
        "request_id": req.request_id,
        "request_identity_hash": req.request_identity_hash,
        "candidate_id": req.candidate_id,
        "candidate_hash": "bad" if bad_hash else req.candidate_hash,
        "role": role,
        "verdict": "VETO" if veto else "SUPPORT",
        "thesis_supported": not veto,
        "qualitative_score": score,
        "confidence_band": "HIGH" if score >= 75 else "MEDIUM",
        "veto": veto,
        "veto_codes": ["MATERIAL_CONTRADICTION"] if veto else [],
        "material_contradictions": ["contradiction"] if veto else [],
        "missing_confirmations": [],
        "major_risks": [],
        "evidence_refs": ["E999" if bad_ref else ref],
        "summary": "Evidence-bound mock assessment.",
        "provider_id": "ignored",
        "model_id": "ignored",
        "provider_request_id": "ignored",
        "latency_ms": 0,
    }


class FakeOpenCode:
    def __init__(self, *, failures=None, veto=False, score=90.0, bad_ref=False, bad_hash=False, sleep=0.0):
        self.calls=[]; self.failures=set(failures or []); self.veto=veto; self.score=score; self.bad_ref=bad_ref; self.bad_hash=bad_hash; self.sleep=sleep
    def generate(self, req, *, model_id, role):
        self.calls.append((model_id, role))
        if model_id in self.failures:
            raise ProviderTransportError("MODEL_UNAVAILABLE", model_id)
        if self.sleep: time.sleep(self.sleep)
        ref=req.frozen_payload["evidence_catalog"][0]["evidence_id"]
        return _response(req, role, ref, score=self.score, veto=self.veto, bad_ref=self.bad_ref, bad_hash=self.bad_hash), "mock-opencode"


class FakeOpenAI:
    def __init__(self, *, fail=False, score=88.0): self.calls=[]; self.fail=fail; self.score=score
    def generate(self, req, *, role):
        self.calls.append(role)
        if self.fail: raise ProviderTransportError("FALLBACK_FAILED", "x")
        ref=req.frozen_payload["evidence_catalog"][0]["evidence_id"]
        return _response(req, role, ref, score=self.score), "mock-openai"


def _candidate(cfg):
    s=load_fixture("healthy_continuation_long")
    c=next(x for x in evaluate_candidates(s, cfg, now_utc=event_time(s)) if x.pattern_type=="CONTINUATION")
    return s,c,build_evidence_catalog(s)


def test_low_quality_candidate_zero_ai_calls(deterministic_config):
    cfg=replace(deterministic_config, ai_enabled=True, ai_required_for_enter=True, ai_call_min_deterministic_confidence=45)
    assert plan_route(30,"NO_TRADE",cfg)==()


def test_routing_is_deterministic(deterministic_config):
    cfg=replace(deterministic_config, ai_enabled=True, opencode_dual_review_enabled=True)
    assert plan_route(50,"WATCH",cfg)==plan_route(50,"WATCH",cfg)
    assert plan_route(70,"ARMED",cfg)[0].model==cfg.opencode_qwen_model
    route=plan_route(90,"ENTER",cfg); assert [r.role for r in route]==["ANALYST","CRITIC"]


def test_qwen_and_muse_paths_and_bounded_positive_uplift(deterministic_config):
    cfg=replace(deterministic_config, ai_enabled=True, ai_required_for_enter=True, opencode_dual_review_enabled=True)
    s,c,cat=_candidate(cfg); oc=FakeOpenCode(score=100); oa=FakeOpenAI()
    out=AIGate(cfg,opencode=oc,openai=oa).assess(c,tentative_decision="ENTER",snapshot_id=s["snapshot_id"],schema_hash=schema_sha256(),catalog=cat,ttl_ms=45000)
    assert cfg.opencode_qwen_model in [x[0] for x in oc.calls]
    assert cfg.opencode_muse_model in [x[0] for x in oc.calls]
    assert out.adjustment <= cfg.ai_max_positive_adjustment
    assert not out.required_failed


def test_open_code_failure_falls_back_other_model(deterministic_config):
    cfg=replace(deterministic_config, ai_enabled=True, opencode_dual_review_enabled=False)
    s,c,cat=_candidate(cfg); oc=FakeOpenCode(failures={cfg.opencode_qwen_model}); oa=FakeOpenAI()
    out=AIGate(cfg,opencode=oc,openai=oa).assess(c,tentative_decision="ENTER",snapshot_id=s["snapshot_id"],schema_hash=schema_sha256(),catalog=cat,ttl_ms=45000)
    assert any(x["fallback_used"] for x in out.failure_log)
    assert out.results


def test_openai_luna_final_fallback(deterministic_config):
    cfg=replace(deterministic_config, ai_enabled=True, opencode_dual_review_enabled=False)
    s,c,cat=_candidate(cfg); oc=FakeOpenCode(failures={cfg.opencode_qwen_model,cfg.opencode_muse_model}); oa=FakeOpenAI()
    out=AIGate(cfg,opencode=oc,openai=oa).assess(c,tentative_decision="ENTER",snapshot_id=s["snapshot_id"],schema_hash=schema_sha256(),catalog=cat,ttl_ms=45000)
    assert oa.calls and out.results[0].model_id==cfg.openai_fallback_model


def test_invalid_evidence_ref_and_hash_are_rejected(deterministic_config):
    cfg=replace(deterministic_config, ai_enabled=True, opencode_dual_review_enabled=False, openai_fallback_enabled=False)
    s,c,cat=_candidate(cfg)
    for kwargs,reason in (({"bad_ref":True},"invented_or_duplicate_evidence_ref"),({"bad_hash":True},"candidate_hash_mismatch")):
        out=AIGate(cfg,opencode=FakeOpenCode(**kwargs),openai=FakeOpenAI(fail=True)).assess(c,tentative_decision="ENTER",snapshot_id=s["snapshot_id"],schema_hash=schema_sha256(),catalog=cat,ttl_ms=45000)
        assert not out.results
        assert any(reason in x["failure_type"] for x in out.failure_log)


def test_veto_downgrades_and_cannot_be_positive(deterministic_config):
    cfg=replace(deterministic_config, ai_enabled=True, opencode_dual_review_enabled=False)
    s,c,cat=_candidate(cfg); out=AIGate(cfg,opencode=FakeOpenCode(veto=True),openai=FakeOpenAI()).assess(c,tentative_decision="ENTER",snapshot_id=s["snapshot_id"],schema_hash=schema_sha256(),catalog=cat,ttl_ms=45000)
    assert out.veto and out.adjustment < 0


def test_late_ai_response_rejected(deterministic_config):
    cfg=replace(deterministic_config, ai_enabled=True, ai_required_for_enter=True, ai_total_deadline_ms=1, opencode_dual_review_enabled=False, openai_fallback_enabled=False)
    s,c,cat=_candidate(cfg); out=AIGate(cfg,opencode=FakeOpenCode(sleep=0.01),openai=FakeOpenAI()).assess(c,tentative_decision="ENTER",snapshot_id=s["snapshot_id"],schema_hash=schema_sha256(),catalog=cat,ttl_ms=1)
    assert not out.results
    assert out.required_failed
    assert any(x["failure_type"] in {"LATE_RESPONSE","SIGNAL_TTL_EXPIRED","TOTAL_DEADLINE_EXCEEDED"} for x in out.failure_log)


def test_ai_required_failure_prevents_enter(deterministic_config):
    cfg=replace(deterministic_config, ai_enabled=True, ai_required_for_enter=True, opencode_dual_review_enabled=False, openai_fallback_enabled=False)
    s=load_fixture("healthy_continuation_long")
    gate=AIGate(cfg,opencode=FakeOpenCode(failures={cfg.opencode_qwen_model,cfg.opencode_muse_model}),openai=FakeOpenAI(fail=True))
    i=evaluate_snapshot(s,cfg,ai_gate=gate,persist=False,now_utc=event_time(s))
    assert i["decision"] != "ENTER"


def test_ai_not_called_on_hard_blocker(deterministic_config):
    cfg=replace(deterministic_config, ai_enabled=True, ai_required_for_enter=True)
    s=load_fixture("balance_trap"); oc=FakeOpenCode(); gate=AIGate(cfg,opencode=oc,openai=FakeOpenAI())
    i=evaluate_snapshot(s,cfg,ai_gate=gate,persist=False,now_utc=event_time(s))
    assert i["decision"]=="NO_TRADE" and not oc.calls

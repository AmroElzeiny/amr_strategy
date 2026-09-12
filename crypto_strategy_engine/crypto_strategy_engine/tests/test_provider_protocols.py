from __future__ import annotations

from dataclasses import replace
import os

from crypto_strategy_engine.ai.providers import OpenAIFallbackProvider, OpenCodeGoProvider
from crypto_strategy_engine.ai.integrity import freeze_ai_request
from crypto_strategy_engine.ai.schemas import AI_ASSESSMENT_JSON_SCHEMA
from crypto_strategy_engine import evaluate_candidates
from crypto_strategy_engine.evidence import build_evidence_catalog
from crypto_strategy_engine.validation import schema_sha256
from conftest import event_time, load_fixture


def _req(cfg):
    s=load_fixture("healthy_continuation_long")
    c=evaluate_candidates(s,cfg,now_utc=event_time(s))[0]
    cat=build_evidence_catalog(s)
    return freeze_ai_request(candidate=c.to_dict(),snapshot_id=s["snapshot_id"],config_version=cfg.config_version,strategy_version=cfg.strategy_version,schema_hash=schema_sha256(),provider_identity="test",role="ANALYST",evidence_catalog=cat.provider_view())


def _raw(req, role="ANALYST"):
    ref=req.frozen_payload["evidence_catalog"][0]["evidence_id"]
    import json
    return json.dumps({"request_id":req.request_id,"request_identity_hash":req.request_identity_hash,"candidate_id":req.candidate_id,"candidate_hash":req.candidate_hash,"role":role,"verdict":"SUPPORT","thesis_supported":True,"qualitative_score":90,"confidence_band":"HIGH","veto":False,"veto_codes":[],"material_contradictions":[],"missing_confirmations":[],"major_risks":[],"evidence_refs":[ref],"summary":"ok","provider_id":"x","model_id":"x","provider_request_id":"x","latency_ms":0})


def test_qwen_messages_and_muse_responses_protocol(monkeypatch, deterministic_config):
    cfg=replace(deterministic_config,ai_enabled=True)
    monkeypatch.setenv("OPENCODE_GO_API_KEY","secret")
    calls=[]
    req=_req(cfg)
    def transport(url,body,headers,timeout):
        calls.append((url,body,headers))
        if url.endswith('/responses'):
            return {"id":"r1","output_text":_raw(req)}
        return {"id":"m1","content":[{"type":"text","text":_raw(req)}]}
    p=OpenCodeGoProvider(cfg,transport=transport)
    p.generate(req,model_id=cfg.opencode_qwen_model,role="ANALYST")
    p.generate(req,model_id=cfg.opencode_muse_model,role="ANALYST")
    assert calls[0][0].endswith('/v1/messages')
    assert calls[1][0].endswith('/v1/responses')
    assert calls[0][2]["Authorization"]=="Bearer secret"
    assert calls[0][2]["x-opencode-session"]==req.request_id
    assert calls[1][1]["text"]["format"]["type"]=="json_schema"


def test_openai_luna_low_reasoning_flex_body(monkeypatch, deterministic_config):
    cfg=replace(deterministic_config,ai_enabled=True,openai_fallback_model="gpt-5.6-luna",openai_reasoning_effort="low",openai_service_tier="flex")
    monkeypatch.setenv("OPENAI_API_KEY","secret")
    req=_req(cfg); captured={}
    def transport(url,body,headers,timeout):
        captured.update({"url":url,"body":body,"headers":headers}); return {"id":"resp","output_text":_raw(req)}
    p=OpenAIFallbackProvider(cfg,transport=transport)
    p.generate(req,role="ANALYST")
    assert captured["url"].endswith('/v1/responses')
    assert captured["body"]["model"]=="gpt-5.6-luna"
    assert captured["body"]["reasoning"]["effort"]=="low"
    assert captured["body"]["service_tier"]=="flex"
    assert captured["body"]["text"]["format"]["strict"] is True

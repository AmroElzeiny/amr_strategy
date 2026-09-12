from __future__ import annotations

from pathlib import Path
import json

from jsonschema import Draft202012Validator

from crypto_strategy_engine import evaluate_snapshot
from crypto_strategy_engine.memory import execution_report_integrity_hash
from crypto_strategy_engine.research import build_ai_research_artifact, measure_repeatability
from conftest import event_time, load_fixture


ROOT = Path(__file__).parents[1]
SCHEMA = json.loads((ROOT / "src" / "crypto_strategy_engine" / "contracts" / "schema.json").read_text())


def _validate_def(name: str, value: dict) -> None:
    schema = {"$schema": SCHEMA["$schema"], "$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{name}"}
    Draft202012Validator(schema).validate(value)


def test_market_snapshot_fixture_matches_frozen_schema():
    _validate_def("marketSnapshot", load_fixture("healthy_continuation_long"))


def test_trade_intent_matches_frozen_schema(deterministic_config):
    snapshot = load_fixture("healthy_continuation_long")
    intent = evaluate_snapshot(snapshot, deterministic_config, persist=False, now_utc=event_time(snapshot))
    _validate_def("tradeIntent", intent)


def test_execution_report_local_contract_schema():
    report = {
        "contract_version": "HM_CRYPTO_V1",
        "execution_id": "exec_schema",
        "signal_id": "sig_schema",
        "created_at_utc": "2026-09-12T15:05:00Z",
        "exchange": "BYBIT",
        "environment": "DEMO",
        "market_mode": "DERIVATIVES",
        "symbol": "BTCUSDT",
        "approved": True,
        "reason_codes": [],
        "final_qty": "0.01",
        "final_notional": "650",
        "leverage": 2.0,
        "margin_mode": "ISOLATED",
        "order_ids": ["o1"],
        "order_link_ids": ["l1"],
        "order_state": "FILLED",
        "fill_state": "FILLED",
        "avg_fill_price": "65000",
        "fees": "0.3",
        "realized_pnl": "12.5",
        "stop_state": "CANCELLED",
        "take_profit_state": "HIT",
        "risk_snapshot_before": {},
        "risk_snapshot_after": {},
        "daily_loss_lock": False,
        "max_loss_lock": False,
        "reconciled": True,
    }
    report["integrity_hash"] = execution_report_integrity_hash(report)
    _validate_def("executionReport", report)


def test_repeatability_metrics_are_research_only():
    rows = [
        {"verdict": "SUPPORT", "veto": False, "candidate_ranking": ["a", "b"], "qualitative_score": 80, "veto_codes": []},
        {"verdict": "SUPPORT", "veto": False, "candidate_ranking": ["a", "b"], "qualitative_score": 82, "veto_codes": []},
        {"verdict": "SUPPORT", "veto": False, "candidate_ranking": ["a", "b"], "qualitative_score": 79, "veto_codes": []},
    ]
    metrics = measure_repeatability(rows)
    assert metrics["research_only"] is True
    assert metrics["decision_agreement"] == 1.0
    assert metrics["veto_agreement"] == 1.0
    assert metrics["candidate_ranking_agreement"] == 1.0


def test_ai_research_artifact_cannot_mutate_live_config():
    summary = {
        "metrics": {"false_breakout_loss_rate": 0.2, "balance_trap_loss_rate": 0.1, "reversal_failure_rate": 0.05},
        "feature_ablation": [{"feature": "balance_detector", "sample_size": 40, "oos_impact_r": 0.15, "stability": "MEASURED"}],
        "pattern_metrics": {},
        "regime_metrics": {},
        "challenger_promotion_criteria": {},
    }
    artifact = build_ai_research_artifact(summary, ai_interpreter=lambda payload: {"hypotheses": ["test quantitatively"]})
    assert artifact["authority"] == "RESEARCH_ONLY"
    assert artifact["auto_config_mutation_allowed"] is False
    assert artifact["ai_called"] is True
    assert artifact["quantitative_hypotheses"]

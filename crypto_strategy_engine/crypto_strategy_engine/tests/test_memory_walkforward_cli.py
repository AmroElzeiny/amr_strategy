from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import json
from pathlib import Path
import subprocess
import sys

import pytest

from crypto_strategy_engine import evaluate_snapshot
from crypto_strategy_engine.memory import TradeMemoryStore, execution_report_integrity_hash
from crypto_strategy_engine.walkforward import no_lookahead_audit, run_walkforward, time_ordered_windows
from conftest import event_time, load_fixture


def _report(intent, *, reconciled=True, execution_id="exec_1"):
    report = {
        "contract_version":"HM_CRYPTO_V1","execution_id":execution_id,"signal_id":intent["signal_id"],"created_at_utc":"2026-09-12T15:05:00Z",
        "exchange":"BYBIT","environment":"DEMO","market_mode":"DERIVATIVES","symbol":"BTCUSDT","approved":True,"reason_codes":[],
        "final_qty":"0.01","final_notional":"650","leverage":2.0,"margin_mode":"ISOLATED","order_ids":["o1"],"order_link_ids":["l1"],
        "order_state":"FILLED","fill_state":"FILLED","avg_fill_price":"65000","fees":"0.3","realized_pnl":"12.5",
        "stop_state":"CANCELLED","take_profit_state":"HIT","risk_snapshot_before":{},"risk_snapshot_after":{},
        "daily_loss_lock":False,"max_loss_lock":False,"reconciled":reconciled,"realized_r":1.25,
    }
    report["integrity_hash"] = execution_report_integrity_hash(report)
    return report


def test_pending_decision_and_clean_outcome_map(tmp_path, deterministic_config):
    cfg=replace(deterministic_config, trade_memory_enabled=True, trade_memory_db=str(tmp_path/'memory.db'))
    s=load_fixture("healthy_continuation_long")
    intent=evaluate_snapshot(s,cfg,persist=True,now_utc=event_time(s))
    result=TradeMemoryStore(cfg.trade_memory_db).ingest_execution_report(_report(intent))
    assert result["learning_eligible"] is True


def test_dirty_outcome_quarantined(tmp_path, deterministic_config):
    cfg=replace(deterministic_config, trade_memory_enabled=True, trade_memory_db=str(tmp_path/'memory.db'))
    s=load_fixture("healthy_continuation_long")
    intent=evaluate_snapshot(s,cfg,persist=True,now_utc=event_time(s))
    result=TradeMemoryStore(cfg.trade_memory_db).ingest_execution_report(_report(intent,reconciled=False))
    assert result["learning_eligible"] is False
    assert result["learning_rejection_reason"]=="execution_not_reconciled"



def test_bad_execution_integrity_hash_quarantined(tmp_path, deterministic_config):
    cfg=replace(deterministic_config, trade_memory_enabled=True, trade_memory_db=str(tmp_path/'memory.db'))
    s=load_fixture("healthy_continuation_long")
    intent=evaluate_snapshot(s,cfg,persist=True,now_utc=event_time(s))
    report=_report(intent)
    report["integrity_hash"]="0"*64
    result=TradeMemoryStore(cfg.trade_memory_db).ingest_execution_report(report)
    assert result["learning_eligible"] is False
    assert result["learning_rejection_reason"]=="integrity_hash_mismatch"

def test_mismatched_execution_report_rejected(tmp_path, deterministic_config):
    store=TradeMemoryStore(tmp_path/'memory.db')
    result=store.ingest_execution_report({**_report({"signal_id":"unknown"}),"signal_id":"unknown"})
    assert result["learning_eligible"] is False
    assert result["learning_rejection_reason"]=="signal_identity_unknown"


def test_historical_analogue_no_future_leakage(tmp_path, deterministic_config):
    cfg=replace(deterministic_config, trade_memory_enabled=True, trade_memory_db=str(tmp_path/'memory.db'))
    s=load_fixture("healthy_continuation_long")
    intent=evaluate_snapshot(s,cfg,persist=True,now_utc=event_time(s))
    store=TradeMemoryStore(cfg.trade_memory_db); store.ingest_execution_report(_report(intent))
    before=store.historical_analogues(candidate_time_utc="2026-09-12T14:00:00Z",pattern=intent["pattern_type"],direction=intent["direction"],market_mode=intent["market_mode"],regime=s["regime"]["type"],min_sample=1,max_results=10)
    after=store.historical_analogues(candidate_time_utc="2026-09-13T14:00:00Z",pattern=intent["pattern_type"],direction=intent["direction"],market_mode=intent["market_mode"],regime=s["regime"]["type"],min_sample=1,max_results=10)
    assert before["state"]=="INSUFFICIENT_SAMPLE" and before["sample_count"]==0
    assert after["state"]=="AVAILABLE" and after["sample_count"]==1


def test_walkforward_ordered_no_leakage_and_artifacts(tmp_path, deterministic_config):
    records=json.loads((Path(__file__).parents[1]/'examples'/'historical_walkforward_records.json').read_text())
    cfg=replace(deterministic_config,walkforward_train_days=20,walkforward_validation_days=5,walkforward_test_days=5,walkforward_step_days=5,walkforward_min_trades=10,calibration_min_sample=20)
    windows=time_ordered_windows(records,cfg)
    assert len(windows)>=2
    assert no_lookahead_audit(records,windows)["passed"]
    out=tmp_path/'research'
    summary=run_walkforward(records,config=cfg,output_dir=out)
    assert summary["window_count"]>=2
    assert summary["auto_promoted"] is False
    assert summary["metrics"]["trade_count"]>0
    for name in ["walkforward_summary.json","walkforward_metrics.csv","pattern_metrics.csv","regime_metrics.csv","confidence_calibration.json","feature_ablation.csv","failure_mode_analysis.csv","champion_config.json","challenger_config.json","ai_research_hypotheses.json"]:
        assert (out/name).exists(), name


def test_walkforward_rejects_future_source(deterministic_config):
    records=json.loads((Path(__file__).parents[1]/'examples'/'historical_walkforward_records.json').read_text())[:50]
    event=datetime.fromisoformat(records[0]["event_time_utc"].replace("Z","+00:00"))
    records[0]["snapshot"]["source_timestamps"]["ticker"]=(event+timedelta(seconds=1)).isoformat().replace('+00:00','Z')
    windows=time_ordered_windows(records,replace(deterministic_config,walkforward_train_days=20,walkforward_validation_days=5,walkforward_test_days=5))
    assert not no_lookahead_audit(records,windows)["passed"]


def test_calibration_insufficient_sample_reported(tmp_path, deterministic_config):
    records=json.loads((Path(__file__).parents[1]/'examples'/'historical_walkforward_records.json').read_text())
    cfg=replace(deterministic_config,walkforward_train_days=20,walkforward_validation_days=5,walkforward_test_days=5,walkforward_step_days=10,calibration_min_sample=10_000)
    summary=run_walkforward(records,config=cfg,output_dir=tmp_path/'r')
    assert summary["calibration"]["calibration_available"] is False


def test_metrics_include_expectancy_and_drawdown(tmp_path, deterministic_config):
    records=json.loads((Path(__file__).parents[1]/'examples'/'historical_walkforward_records.json').read_text())
    cfg=replace(deterministic_config,walkforward_train_days=20,walkforward_validation_days=5,walkforward_test_days=5,walkforward_step_days=10)
    m=run_walkforward(records,config=cfg,output_dir=tmp_path/'r')["metrics"]
    for key in ("win_rate","expectancy_r","profit_factor","max_drawdown_r","mfe","mae","false_breakout_loss_rate","balance_trap_loss_rate"):
        assert key in m


def test_cli_validate_and_evaluate_no_ai(tmp_path):
    root=Path(__file__).parents[1]
    env={"PYTHONPATH":str(root/'src'),"MAX_SNAPSHOT_AGE_MS":"1000000000","AI_ENABLED":"false","AI_REQUIRED_FOR_ENTER":"false","TRADE_MEMORY_ENABLED":"false"}
    import os
    e={**os.environ,**env}
    fixture=root/'tests'/'fixtures'/'healthy_continuation_long.json'
    v=subprocess.run([sys.executable,"-m","crypto_strategy_engine","validate",str(fixture)],cwd=root,env=e,capture_output=True,text=True)
    assert v.returncode==0, v.stderr
    r=subprocess.run([sys.executable,"-m","crypto_strategy_engine","evaluate",str(fixture),"--no-ai","--no-persist"],cwd=root,env=e,capture_output=True,text=True)
    assert r.returncode==0, r.stderr
    assert json.loads(r.stdout)["decision"]=="ENTER"

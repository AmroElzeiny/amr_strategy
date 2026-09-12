from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from crypto_strategy_engine import evaluate_candidates, evaluate_snapshot
from crypto_strategy_engine.config import StrategyConfig
from crypto_strategy_engine.penalties import build_penalties
from crypto_strategy_engine.thesis import ThesisStore, build_thesis_id
from conftest import event_time, load_fixture


def test_same_structure_same_thesis_and_touch_not_new():
    s = load_fixture("healthy_continuation_long")
    a = build_thesis_id(s, "CONTINUATION", "LONG")
    s["levels"]["entry_reference"] = "65010"  # repeated touch/entry refinement is not thesis identity
    b = build_thesis_id(s, "CONTINUATION", "LONG")
    assert a == b


def test_major_structural_reset_changes_thesis():
    s = load_fixture("healthy_continuation_long")
    a = build_thesis_id(s, "CONTINUATION", "LONG")
    s["levels"]["breakout_event_id"] = "new_major_breakout"
    b = build_thesis_id(s, "CONTINUATION", "LONG")
    assert a != b


def test_attempt_counter_persists_restart(tmp_path: Path):
    db = tmp_path / "thesis.db"
    s = load_fixture("healthy_continuation_long")
    tid = build_thesis_id(s, "CONTINUATION", "LONG")
    store = ThesisStore(db); store.record_seen(tid, "struct"); assert store.record_attempt(tid) == 1
    restarted = ThesisStore(db)
    assert restarted.peek(tid, max_attempts=2).attempt_no == 1
    assert restarted.record_attempt(tid) == 2
    assert restarted.peek(tid, max_attempts=2).exhausted


def test_attempts_exhausted_block_enter(tmp_path, deterministic_config):
    s = load_fixture("healthy_continuation_long")
    cfg = replace(deterministic_config, trade_memory_enabled=True, trade_memory_db=str(tmp_path / "m.db"))
    # First two strategic ENTER forwards consume the thesis attempts.
    a = evaluate_snapshot(s, cfg, persist=True, now_utc=event_time(s)); assert a["decision"] == "ENTER"
    b = evaluate_snapshot(s, cfg, persist=True, now_utc=event_time(s)); assert b["decision"] == "ENTER"
    c = evaluate_snapshot(s, cfg, persist=True, now_utc=event_time(s))
    assert c["decision"] == "NO_TRADE"
    assert "THESIS_ATTEMPTS_EXHAUSTED" in {x["code"] for x in c["blockers"]}


def test_penalty_root_cause_not_double_counted(deterministic_config):
    s = load_fixture("balance_trap")
    p = build_penalties(s, pattern_type="CONTINUATION", direction="LONG", risk_reward=2.0, missing_critical=[], attempt_no=0, config=deterministic_config)
    roots = [x.root_cause for x in p]
    assert len(roots) == len(set(roots))


def test_major_penalties_independent(deterministic_config):
    fixtures_expected = {
        "fake_breakout_long": "FAILED_BREAKOUT_RISK",
        "balance_trap": "BALANCE_RISK",
        "strong_counter_pullback": "REVERSAL_RISK",
        "value_not_migrating": "VALUE_NOT_MIGRATING",
        "conflicting_orderflow": "ORDERFLOW_CONTRADICTION",
    }
    for name, code in fixtures_expected.items():
        s = load_fixture(name)
        c = next(x for x in evaluate_candidates(s, deterministic_config, now_utc=event_time(s)) if x.pattern_type == "CONTINUATION")
        assert code in {p.code for p in c.penalties}


def test_hard_blocker_overrides_high_score(deterministic_config):
    s = load_fixture("balance_trap")
    i = evaluate_snapshot(s, deterministic_config, persist=False, now_utc=event_time(s))
    assert i["decision"] == "NO_TRADE"
    assert i["deterministic_confidence"] >= 0


def test_property_invariants(deterministic_config):
    names = [p.stem for p in (Path(__file__).parent / "fixtures").glob("*.json")]
    for name in names:
        s = load_fixture(name)
        try:
            i = evaluate_snapshot(s, deterministic_config, persist=False, now_utc=event_time(s))
        except ValueError:
            continue
        blocker_codes = {b["code"] for b in i["blockers"]}
        if blocker_codes:
            assert i["decision"] != "ENTER"
        if s["market_mode"] == "SPOT" and i["direction"] == "SHORT":
            assert i["decision"] != "ENTER"
        if s["data_quality"] == "INVALID":
            assert i["decision"] != "ENTER"
        if i["final_confidence"] < deterministic_config.enter_min_confidence:
            assert i["decision"] != "ENTER"


def test_config_env_controls_weights_and_target_filters():
    cfg = StrategyConfig.from_env({
        "WEIGHT_STRUCTURE_QUALITY": "0.2",
        "PENALTY_BALANCE_RISK": "30",
        "TARGET_OBSTACLE_FILTER_ENABLED": "false",
        "LIQUIDITY_WALL_TARGET_FILTER_ENABLED": "false",
        "CONTINUATION_FIB_LEVELS": "0.5,0.618,0.786",
        "CONTINUATION_FVG_LEVELS": "0,0.25,0.5,0.75,1",
    })
    assert cfg.weight_structure_quality == 0.2
    assert cfg.penalty_balance_risk == 30.0
    assert cfg.target_obstacle_filter_enabled is False
    assert cfg.liquidity_wall_target_filter_enabled is False
    assert cfg.continuation_fib_levels == (0.5, 0.618, 0.786)
    assert cfg.continuation_fvg_levels == (0.0, 0.25, 0.5, 0.75, 1.0)


def test_thesis_cooldown_persists(tmp_path):
    db = tmp_path / "thesis.db"
    store = ThesisStore(db)
    tid = "thesis_cooldown_case"
    store.record_seen(tid, "struct")
    assert store.record_attempt(tid, cooldown_sec=120) == 1
    status = ThesisStore(db).peek(tid, max_attempts=2)
    assert status.cooldown_until.endswith("Z")
    assert status.cooldown_until > status.last_seen

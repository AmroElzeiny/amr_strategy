from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from crypto_strategy_engine import evaluate_candidates, evaluate_snapshot
from crypto_strategy_engine.patterns import pre_breakout, reversal
from crypto_strategy_engine.targets import projected_extension_target
from conftest import event_time, load_fixture


def cand(snapshot, cfg, pattern):
    return next(c for c in evaluate_candidates(snapshot, cfg, now_utc=event_time(snapshot)) if c.pattern_type == pattern)


def test_healthy_continuation_long_enters(deterministic_config):
    s = load_fixture("healthy_continuation_long")
    i = evaluate_snapshot(s, deterministic_config, persist=False, now_utc=event_time(s))
    assert i["pattern_type"] == "CONTINUATION"
    assert i["decision"] == "ENTER"
    assert not i["blockers"]


def test_healthy_continuation_short_supported(deterministic_config):
    s = load_fixture("healthy_continuation_short")
    c = cand(s, deterministic_config, "CONTINUATION")
    assert c.direction == "SHORT" and not c.blockers


def test_fake_breakout_is_hard_rejected(deterministic_config):
    s = load_fixture("fake_breakout_long")
    i = evaluate_snapshot(s, deterministic_config, persist=False, now_utc=event_time(s))
    assert i["decision"] == "NO_TRADE"
    assert "FAILED_BREAKOUT_HARD_BLOCK" in {b["code"] for b in i["blockers"]}


def test_balance_trap_rejected_even_with_fvg(deterministic_config):
    s = load_fixture("balance_trap")
    assert any(x["type"].startswith("FVG") for x in s["levels"]["retest_locations"])
    i = evaluate_snapshot(s, deterministic_config, persist=False, now_utc=event_time(s))
    assert i["decision"] == "NO_TRADE"
    assert "BALANCE_HARD_BLOCK" in {b["code"] for b in i["blockers"]}


def test_strong_counter_pullback_blocks_continuation(deterministic_config):
    s = load_fixture("strong_counter_pullback")
    c = cand(s, deterministic_config, "CONTINUATION")
    assert c.deterministic_confidence < 78 or c.blockers
    assert "REVERSAL_RISK" in {p.code for p in c.penalties} or "INVALIDATED_STRUCTURE" in {b.code for b in c.blockers}


def test_first_and_second_pullbacks_supported(deterministic_config):
    for name, branch in (("first_pullback_breakout", "FIRST_MICRO_PULLBACK"), ("second_pullback_breakout", "SECOND_MICRO_PULLBACK")):
        s = load_fixture(name)
        b = cand(s, deterministic_config, "BREAKOUT")
        assert b.branch == branch
        assert not b.blockers


def test_third_minor_pullback_requires_major_reset(deterministic_config):
    s = load_fixture("exhausted_minor_pullbacks")
    b = cand(s, deterministic_config, "BREAKOUT")
    c = cand(s, deterministic_config, "CONTINUATION")
    assert "MISSING_REQUIRED_SETUP_EVIDENCE" in {x.code for x in b.blockers}
    assert "MISSING_REQUIRED_SETUP_EVIDENCE" in {x.code for x in c.blockers}
    i = evaluate_snapshot(s, deterministic_config, persist=False, now_utc=event_time(s))
    assert i["decision"] == "NO_TRADE"


def test_prebreakout_compression_vs_chop(deterministic_config):
    clean = load_fixture("prebreakout_compression")
    chop = load_fixture("prebreakout_chop")
    assert pre_breakout.detect(clean, deterministic_config).eligible
    assert not pre_breakout.detect(chop, deterministic_config).eligible
    assert evaluate_snapshot(chop, deterministic_config, persist=False, now_utc=event_time(chop))["decision"] == "NO_TRADE"


def test_reversal_requires_real_confirmation_not_divergence_alone(deterministic_config):
    good = load_fixture("reversal_liquidity_sweep")
    false = load_fixture("reversal_false_signal")
    assert reversal.detect(good, deterministic_config).eligible
    assert not reversal.detect(false, deterministic_config).eligible
    good_intent = evaluate_snapshot(good, deterministic_config, persist=False, now_utc=event_time(good))
    assert good_intent["pattern_type"] == "REVERSAL"
    assert good_intent["decision"] == "ENTER"


def test_spot_opening_short_impossible(deterministic_config):
    s = load_fixture("spot_short")
    i = evaluate_snapshot(s, deterministic_config, persist=False, now_utc=event_time(s))
    assert not (i["direction"] == "SHORT" and i["order_intent"] == "OPEN" and i["decision"] == "ENTER")
    assert "UNSUPPORTED_SPOT_SHORT" in {b["code"] for b in i["blockers"]}


def test_derivatives_long_and_short_strategically_valid(deterministic_config):
    for name, direction in (("healthy_continuation_long", "LONG"), ("healthy_continuation_short", "SHORT")):
        s = load_fixture(name)
        c = cand(s, deterministic_config, "CONTINUATION")
        assert c.direction == direction
        assert not c.blockers


def test_projected_1_6_target_exact(deterministic_config):
    s = load_fixture("healthy_continuation_long")
    assert projected_extension_target(s, "LONG", deterministic_config) == Decimal("69800.0")
    i = evaluate_snapshot(s, deterministic_config, persist=False, now_utc=event_time(s))
    assert i["projected_extension_target"] == "69800"


def test_obstacle_stops_practical_target_before_projection(deterministic_config):
    s = load_fixture("healthy_continuation_long")
    i = evaluate_snapshot(s, deterministic_config, persist=False, now_utc=event_time(s))
    assert Decimal(i["targets"][0]["price"]) < Decimal(i["projected_extension_target"])


def test_rr_below_minimum_rejects(deterministic_config):
    s = load_fixture("target_blocked")
    i = evaluate_snapshot(s, deterministic_config, persist=False, now_utc=event_time(s))
    assert i["decision"] == "NO_TRADE"
    assert "RR_BELOW_HARD_MIN" in {b["code"] for b in i["blockers"]}

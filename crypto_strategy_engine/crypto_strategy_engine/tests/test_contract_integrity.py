from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from crypto_strategy_engine import evaluate_candidates, evaluate_snapshot, validate_market_snapshot
from crypto_strategy_engine.ai.integrity import freeze_ai_request, frozen_request_unchanged
from crypto_strategy_engine.evidence import build_evidence_catalog
from crypto_strategy_engine.models import canonical_hash
from crypto_strategy_engine.validation import schema_sha256
from conftest import event_time, load_fixture


def test_valid_snapshot_accepted(deterministic_config):
    s = load_fixture("healthy_continuation_long")
    v = validate_market_snapshot(s, deterministic_config, now_utc=event_time(s))
    assert v.valid
    assert not v.blockers


def test_wrong_contract_rejected(deterministic_config):
    s = load_fixture("healthy_continuation_long")
    s["contract_version"] = "WRONG"
    with pytest.raises(ValueError, match="CONTRACT_MISMATCH"):
        validate_market_snapshot(s, deterministic_config, now_utc=event_time(s))


def test_missing_required_rejected(deterministic_config):
    s = load_fixture("healthy_continuation_long")
    del s["orderflow"]
    with pytest.raises(ValueError, match="missing_required"):
        validate_market_snapshot(s, deterministic_config, now_utc=event_time(s))


def test_malformed_decimal_rejected(deterministic_config):
    s = load_fixture("healthy_continuation_long")
    s["ticker"]["last_price"] = "NaN"
    with pytest.raises(ValueError, match="invalid_decimal|non_finite"):
        validate_market_snapshot(s, deterministic_config, now_utc=event_time(s))


def test_decimal_number_not_string_rejected(deterministic_config):
    s = load_fixture("healthy_continuation_long")
    s["ticker"]["last_price"] = 65000.0
    with pytest.raises(ValueError, match="decimal_must_be_string"):
        validate_market_snapshot(s, deterministic_config, now_utc=event_time(s))


def test_enum_mismatch_rejected(deterministic_config):
    s = load_fixture("healthy_continuation_long")
    s["market_mode"] = "MARGIN_SPOT"
    with pytest.raises(ValueError, match="market_mode_enum"):
        validate_market_snapshot(s, deterministic_config, now_utc=event_time(s))


def test_schema_hash_is_raw_file_sha256():
    path = Path(__file__).parents[1] / "src" / "crypto_strategy_engine" / "contracts" / "schema.json"
    assert schema_sha256() == sha256(path.read_bytes()).hexdigest()


def test_deterministic_output_repeatable(deterministic_config):
    s = load_fixture("healthy_continuation_long")
    now = event_time(s)
    a = evaluate_snapshot(s, deterministic_config, persist=False, now_utc=now)
    b = evaluate_snapshot(s, deterministic_config, persist=False, now_utc=now)
    assert a == b


def test_candidate_ids_and_scores_repeatable(deterministic_config):
    s = load_fixture("healthy_continuation_long")
    now = event_time(s)
    a = evaluate_candidates(s, deterministic_config, now_utc=now)
    b = evaluate_candidates(s, deterministic_config, now_utc=now)
    assert [(c.candidate_id, c.candidate_hash, c.deterministic_confidence) for c in a] == [
        (c.candidate_id, c.candidate_hash, c.deterministic_confidence) for c in b
    ]


def test_frozen_ai_request_mutation_detected(deterministic_config):
    s = load_fixture("healthy_continuation_long")
    candidate = evaluate_candidates(s, deterministic_config, now_utc=event_time(s))[0]
    cat = build_evidence_catalog(s)
    req = freeze_ai_request(
        candidate=candidate.to_dict(), snapshot_id=s["snapshot_id"], config_version=deterministic_config.config_version,
        strategy_version=deterministic_config.strategy_version, schema_hash=schema_sha256(), provider_identity="mock:model",
        role="ANALYST", evidence_catalog=cat.provider_view(),
    )
    assert frozen_request_unchanged(req)
    req.frozen_payload["candidate"]["direction"] = "SHORT"
    assert not frozen_request_unchanged(req)


def test_integrity_hash_matches_payload(deterministic_config):
    s = load_fixture("healthy_continuation_long")
    intent = evaluate_snapshot(s, deterministic_config, persist=False, now_utc=event_time(s))
    expected = canonical_hash({k: v for k, v in intent.items() if k != "integrity_hash"})
    assert intent["integrity_hash"] == expected


def test_invalid_stale_and_degraded_never_enter(deterministic_config):
    for name in ("invalid_snapshot", "stale_snapshot", "degraded_snapshot"):
        s = load_fixture(name)
        intent = evaluate_snapshot(s, deterministic_config, persist=False, now_utc=event_time(s))
        assert intent["decision"] != "ENTER"


def test_source_boundary_has_no_peer_package_or_exchange_execution_dependencies():
    root = Path(__file__).resolve().parents[1] / "src" / "crypto_strategy_engine"
    text = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    forbidden = (
        "import crypto_market_intel",
        "import crypto_risk_execution",
        "from crypto_market_intel",
        "from crypto_risk_execution",
        "import pybit",
        "from pybit",
        "MetaTrader5",
        "mt5.order_send",
        "place_order(",
        "wallet_balance",
    )
    for token in forbidden:
        assert token not in text

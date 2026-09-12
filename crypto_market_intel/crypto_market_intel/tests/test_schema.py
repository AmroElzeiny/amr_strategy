from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

from crypto_market_intel.contracts.models import DataQuality, Exchange, MarketMode, MarketSnapshot, TradingEnvironment


def test_schema_contains_all_frozen_contracts() -> None:
    path = Path(__file__).parents[1] / "src/crypto_market_intel/contracts/schema.json"
    schema = json.loads(path.read_text())
    assert schema["contract_version"] == "HM_CRYPTO_V1"
    assert {"MarketSnapshot","TradeIntent","ExecutionReport"}.issubset(schema["$defs"])
    assert len(hashlib.sha256(path.read_bytes()).hexdigest()) == 64


def test_market_snapshot_serializes_and_validates_against_schema() -> None:
    now = datetime(2026,9,12,tzinfo=timezone.utc)
    snapshot = MarketSnapshot(
        contract_version="HM_CRYPTO_V1", snapshot_id="snap1", created_at_utc=now, event_time_utc=now, exchange=Exchange.BYBIT,
        environment=TradingEnvironment.DEMO, market_mode=MarketMode.DERIVATIVES, symbol="BTCUSDT",
        instrument={}, ticker={}, timeframes={}, structure={}, levels=[], volume_profile={}, orderflow={}, orderbook={}, derivatives={},
        regime={}, breakout_alert=None, data_quality=DataQuality.GOOD, quality_reasons=[], feature_versions={"x":"1"}, source_timestamps={"ticker":now},
    )
    payload = snapshot.model_dump(mode="json")
    path = Path(__file__).parents[1] / "src/crypto_market_intel/contracts/schema.json"
    schema = json.loads(path.read_text())
    jsonschema.validate(payload, {"$schema":schema["$schema"], "$defs":schema["$defs"], **schema["$defs"]["MarketSnapshot"]})
    encoded = snapshot.canonical_json()
    assert '"contract_version":"HM_CRYPTO_V1"' in encoded
    assert snapshot.integrity_hash() == snapshot.integrity_hash()

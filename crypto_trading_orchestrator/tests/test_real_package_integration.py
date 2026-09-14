from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import crypto_risk_execution
import crypto_strategy_engine
import pytest
from conftest import FakeMarket
from crypto_market_intel.contracts.models import (
    DataQuality,
    Exchange,
    MarketMode,
    MarketSnapshot,
    TradingEnvironment,
)
from crypto_risk_execution.config import Settings as RiskSettings
from crypto_risk_execution.models import AccountState, InstrumentRules
from crypto_risk_execution.persistence.state import StateStore
from crypto_risk_execution.validation import validate_trade_intent
from crypto_strategy_engine import evaluate_snapshot, validate_market_snapshot
from crypto_strategy_engine.config import StrategyConfig

from crypto_trading_orchestrator.adapters import RiskExecutionAdapter, StrategyAdapter
from crypto_trading_orchestrator.config import OrchestratorConfig
from crypto_trading_orchestrator.runtime import TradingOrchestrator


class OfflineExchange:
    def get_open_orders(self):
        return []

    def get_positions(self):
        return []

    def get_account_state(self):
        return AccountState(Decimal("10000"), Decimal("10000"), Decimal("9000"))

    def get_instrument_rules(self, symbol):
        return InstrumentRules(
            symbol,
            Decimal("0.1"),
            Decimal("0.001"),
            Decimal("0.001"),
            max_qty=Decimal("100"),
            min_notional=Decimal("5"),
            max_leverage=Decimal("3"),
            base_asset="BTC",
            quote_asset="USDT",
        )

    def get_fee_schedule(self, symbol):
        return {"taker": "0.0006", "maker": "0.0001", "source": "offline-test"}

    def place_order(self, order):
        raise AssertionError("dry-run must never call place_order")


def _fresh_strategy_fixture() -> tuple[dict, datetime]:
    return _fresh_named_fixture("healthy_continuation_long")


def _fresh_named_fixture(name: str) -> tuple[dict, datetime]:
    path = Path(__file__).parent / "fixtures" / f"{name}.json"
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    now = datetime.now(UTC)
    stamp = now.isoformat().replace("+00:00", "Z")
    snapshot["created_at_utc"] = stamp
    snapshot["event_time_utc"] = stamp
    snapshot["source_timestamps"] = {
        key: stamp if value is not None else None for key, value in snapshot["source_timestamps"].items()
    }
    return snapshot, now


@pytest.mark.parametrize(
    ("fixture_name", "pattern", "decision"),
    [
        ("prebreakout_compression", "PRE_BREAKOUT", "ENTER"),
        ("exhausted_minor_pullbacks", "BREAKOUT", "NO_TRADE"),
        ("healthy_continuation_long", "CONTINUATION", "ENTER"),
        ("reversal_liquidity_sweep", "REVERSAL", "ENTER"),
    ],
)
def test_all_four_real_strategy_patterns(fixture_name, pattern, decision) -> None:
    snapshot, now = _fresh_named_fixture(fixture_name)
    config = replace(
        StrategyConfig(),
        ai_enabled=False,
        ai_required_for_enter=False,
        trade_memory_enabled=False,
        max_snapshot_age_ms=10**9,
    )
    intent = evaluate_snapshot(snapshot, config, persist=False, now_utc=now)
    assert (intent["pattern_type"], intent["decision"]) == (pattern, decision)


def test_real_package1_snapshot_is_accepted_by_real_strategy() -> None:
    now = datetime.now(UTC)
    snapshot = MarketSnapshot(
        contract_version="HM_CRYPTO_V1",
        snapshot_id="snapshot_cross_package_0001",
        created_at_utc=now,
        event_time_utc=now,
        exchange=Exchange.BYBIT,
        environment=TradingEnvironment.DEMO,
        market_mode=MarketMode.DERIVATIVES,
        symbol="BTCUSDT",
        instrument={},
        ticker={"last_price": "100", "bid": "99", "ask": "101"},
        timeframes={"5m": []},
        structure={},
        levels=[],
        volume_profile={},
        orderflow={},
        orderbook={},
        derivatives=None,
        regime={"type": "UNKNOWN"},
        breakout_alert=None,
        data_quality=DataQuality.GOOD,
        quality_reasons=[],
        feature_versions={"market": "test"},
        source_timestamps={"ticker": now},
    ).model_dump(mode="json")
    validation = validate_market_snapshot(snapshot, now_utc=now)
    assert validation.valid
    assert isinstance(validation.frozen["levels"], dict)
    assert evaluate_snapshot(snapshot, persist=False, now_utc=now)["decision"] == "NO_TRADE"


def test_real_strategy_enter_is_valid_for_real_risk_package() -> None:
    snapshot, now = _fresh_strategy_fixture()
    config = replace(
        StrategyConfig(),
        ai_enabled=False,
        ai_required_for_enter=False,
        trade_memory_enabled=False,
        max_snapshot_age_ms=10**9,
    )
    intent = evaluate_snapshot(snapshot, config, persist=False, now_utc=now)
    assert intent["decision"] == "ENTER"
    assert intent["attempt_no"] == 0
    assert validate_trade_intent(intent, now=now) == (True, ())


def test_real_risk_package_rejects_spot_short() -> None:
    snapshot, now = _fresh_strategy_fixture()
    config = replace(
        StrategyConfig(), ai_enabled=False, ai_required_for_enter=False, trade_memory_enabled=False
    )
    intent = evaluate_snapshot(snapshot, config, persist=False, now_utc=now)
    intent["market_mode"] = "SPOT"
    intent["direction"] = "SHORT"
    from crypto_risk_execution.validation import intent_hash

    intent["integrity_hash"] = intent_hash(intent)
    valid, reasons = validate_trade_intent(intent, now=now)
    assert not valid
    assert "UNSUPPORTED_SPOT_SHORT" in reasons


def test_real_strategy_to_real_risk_dry_run_end_to_end(tmp_path, monkeypatch) -> None:
    snapshot, now = _fresh_strategy_fixture()
    monkeypatch.setenv("AI_ENABLED", "false")
    monkeypatch.setenv("AI_REQUIRED_FOR_ENTER", "false")
    monkeypatch.setenv("TRADE_MEMORY_ENABLED", "false")
    monkeypatch.setenv("MAX_SNAPSHOT_AGE_MS", "1000000000")
    package_store = StateStore(str(tmp_path / "risk.db"))
    risk_settings = replace(
        RiskSettings(),
        state_db=str(tmp_path / "risk.db"),
        execution_enabled=True,
        dry_run=True,
        risk_pct=Decimal("1"),
        max_risk_pct=Decimal("1"),
    )
    risk = RiskExecutionAdapter(
        crypto_risk_execution,
        settings=risk_settings,
        adapter=OfflineExchange(),
        store=package_store,
    )
    config = replace(
        OrchestratorConfig(),
        execution_enabled=True,
        state_db=str(tmp_path / "orchestrator.db"),
        data_dir=str(tmp_path / "data"),
        audit_dir=str(tmp_path / "audit"),
        quarantine_dir=str(tmp_path / "quarantine"),
    )
    runtime = TradingOrchestrator(config, FakeMarket(), StrategyAdapter(crypto_strategy_engine), risk)

    async def scenario() -> None:
        status = await runtime.startup()
        assert status["state"] == "RUNNING"
        result = await runtime.process_snapshot(snapshot, persist_strategy=False, now_utc=now)
        assert result["status"] == "APPROVED", result
        assert result["execution_report"]["order_state"] == "SIMULATED_NOT_SUBMITTED"
        assert result["execution_report"]["order_ids"] == []
        assert runtime.get_metrics().get("orders_submitted", 0) == 0
        await runtime.shutdown()

    asyncio.run(scenario())


def test_scanner_breakout_continuation_to_execution_pipeline(tmp_path, monkeypatch) -> None:
    snapshot, _ = _fresh_strategy_fixture()
    monkeypatch.setenv("AI_ENABLED", "false")
    monkeypatch.setenv("AI_REQUIRED_FOR_ENTER", "false")
    monkeypatch.setenv("TRADE_MEMORY_ENABLED", "false")
    monkeypatch.setenv("MAX_SNAPSHOT_AGE_MS", "1000000000")

    class PipelineMarket(FakeMarket):
        def build_snapshot(self, symbol, alert=None):
            assert symbol == "BTCUSDT"
            assert alert["alert_id"] == "alert-1"
            return snapshot

    package_store = StateStore(str(tmp_path / "risk.db"))
    settings = replace(
        RiskSettings(),
        state_db=str(tmp_path / "risk.db"),
        execution_enabled=True,
        dry_run=True,
        risk_pct=Decimal("1"),
        max_risk_pct=Decimal("1"),
    )
    risk = RiskExecutionAdapter(
        crypto_risk_execution,
        settings=settings,
        adapter=OfflineExchange(),
        store=package_store,
    )
    config = replace(
        OrchestratorConfig(),
        execution_enabled=True,
        state_db=str(tmp_path / "orchestrator.db"),
        data_dir=str(tmp_path / "data"),
        audit_dir=str(tmp_path / "audit"),
        quarantine_dir=str(tmp_path / "quarantine"),
    )
    runtime = TradingOrchestrator(config, PipelineMarket(), StrategyAdapter(crypto_strategy_engine), risk)

    async def scenario() -> None:
        assert (await runtime.startup())["state"] == "RUNNING"
        cycle = await runtime.scan_once()
        alert = cycle["alerts"][0]
        result = await runtime.build_and_process("BTCUSDT", alert, persist_strategy=False)
        assert result["intent"]["pattern_type"] == "CONTINUATION"
        assert result["intent"]["decision"] == "ENTER"
        assert result["status"] == "APPROVED"
        assert result["execution_report"]["order_state"] == "SIMULATED_NOT_SUBMITTED"
        assert runtime.get_metrics()["snapshots_generated"] == 1
        await runtime.shutdown()

    asyncio.run(scenario())

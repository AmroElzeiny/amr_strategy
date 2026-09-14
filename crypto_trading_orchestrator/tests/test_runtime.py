from __future__ import annotations

import asyncio
import time
from dataclasses import replace
from datetime import timedelta

from conftest import FakeMarket, FakeRisk, FakeStrategy, make_intent, make_report

from crypto_trading_orchestrator.canonical import payload_integrity_hash, utc_text
from crypto_trading_orchestrator.config import OrchestratorConfig
from crypto_trading_orchestrator.models import (
    Event,
    EventType,
    HealthState,
    Priority,
    RuntimeState,
    SymbolState,
)
from crypto_trading_orchestrator.runtime import TradingOrchestrator


def _runtime(tmp_path, strategy, risk, **changes):
    config = replace(
        OrchestratorConfig(),
        state_db=str(tmp_path / "orchestrator.db"),
        data_dir=str(tmp_path / "data"),
        audit_dir=str(tmp_path / "audit"),
        quarantine_dir=str(tmp_path / "quarantine"),
        **changes,
    )
    return TradingOrchestrator(config, FakeMarket(), strategy, risk)


def test_startup_requires_reconciliation(tmp_path, snapshot) -> None:
    intent = make_intent(snapshot)
    runtime = _runtime(tmp_path, FakeStrategy(intent), FakeRisk(make_report(intent), reconciled=False))

    async def scenario() -> None:
        status = await runtime.startup()
        assert runtime.state == RuntimeState.BLOCKED
        assert status["accepting_new_entries"] is False
        assert "ACCOUNT_RECONCILIATION_REQUIRED" in status["error"]
        await runtime.shutdown()

    asyncio.run(scenario())


def test_execution_disabled_means_zero_execution_calls(tmp_path, snapshot, now) -> None:
    intent = make_intent(snapshot)
    risk = FakeRisk(make_report(intent))
    runtime = _runtime(tmp_path, FakeStrategy(intent), risk)

    async def scenario() -> None:
        await runtime.startup()
        result = await runtime.process_snapshot(snapshot, now_utc=now)
        assert result["status"] == "BLOCKED"
        assert result["reason"] == "ORCHESTRATOR_EXECUTION_DISABLED"
        assert risk.execute_calls == 0
        await runtime.shutdown()

    asyncio.run(scenario())


def test_enter_routes_once_when_dry_run_enabled(tmp_path, snapshot, now) -> None:
    intent = make_intent(snapshot)
    risk = FakeRisk(make_report(intent))
    runtime = _runtime(tmp_path, FakeStrategy(intent), risk, execution_enabled=True)

    async def scenario() -> None:
        await runtime.startup()
        first = await runtime.process_snapshot(snapshot, now_utc=now)
        second = await runtime.process_snapshot(snapshot, now_utc=now)
        assert first["status"] == "APPROVED"
        assert first["execution_report"]["order_state"] == "SIMULATED_NOT_SUBMITTED"
        assert second["status"] == "DUPLICATE"
        assert risk.execute_calls == 1
        assert runtime.get_metrics().get("orders_submitted", 0) == 0
        await runtime.shutdown()

    asyncio.run(scenario())


def test_expired_snapshot_never_reaches_strategy_or_risk(tmp_path, snapshot, now) -> None:
    intent = make_intent(snapshot)
    risk = FakeRisk(make_report(intent))
    runtime = _runtime(tmp_path, FakeStrategy(intent), risk, execution_enabled=True)

    async def scenario() -> None:
        await runtime.startup()
        result = await runtime.process_snapshot(snapshot, now_utc=now + timedelta(seconds=6))
        assert result["status"] == "EXPIRED"
        assert risk.execute_calls == 0
        await runtime.shutdown()

    asyncio.run(scenario())


def test_tampered_intent_quarantined(tmp_path, snapshot, now) -> None:
    intent = make_intent(snapshot)
    intent["final_confidence"] = 1
    risk = FakeRisk(make_report(make_intent(snapshot)))
    runtime = _runtime(tmp_path, FakeStrategy(intent), risk, execution_enabled=True)

    async def scenario() -> None:
        await runtime.startup()
        result = await runtime.process_snapshot(snapshot, now_utc=now)
        assert result["status"] == "QUARANTINED"
        assert risk.execute_calls == 0
        assert runtime.store.counts()["quarantine"] == 1
        await runtime.shutdown()

    asyncio.run(scenario())


def test_loss_lock_blocks_following_entries(tmp_path, snapshot, now) -> None:
    intent = make_intent(snapshot)
    risk = FakeRisk(make_report(intent))
    runtime = _runtime(tmp_path, FakeStrategy(intent), risk, execution_enabled=True)

    async def scenario() -> None:
        await runtime.startup()
        lock = Event(
            EventType.DAILY_LOSS_LOCK,
            Priority.RISK_RECONCILIATION,
            runtime.runtime_session_id,
            "risk",
            symbol="BTCUSDT",
        )
        await runtime.ingest_execution_event(lock)
        result = await runtime.process_snapshot(snapshot, now_utc=now)
        assert result["status"] == "BLOCKED"
        assert runtime.health == HealthState.BLOCK_NEW_ENTRIES
        assert risk.execute_calls == 0
        await runtime.shutdown()

    asyncio.run(scenario())


def test_closed_position_feedback_is_once_only(tmp_path, snapshot) -> None:
    intent = make_intent(snapshot)
    strategy = FakeStrategy(intent)
    report = make_report(intent)
    report.update(
        {"fill_state": "FILLED", "realized_r": "1", "stop_state": "NONE", "take_profit_state": "HIT"}
    )
    report["integrity_hash"] = payload_integrity_hash(report)
    risk = FakeRisk(make_report(intent))
    runtime = _runtime(tmp_path, strategy, risk)

    async def scenario() -> None:
        await runtime.startup()
        runtime.store.upsert_lineage(intent["signal_id"], intent)
        event = Event(
            EventType.POSITION_CLOSED,
            Priority.EXECUTION_PROTECTION,
            runtime.runtime_session_id,
            "risk",
            symbol="BTCUSDT",
            signal_id=intent["signal_id"],
            execution_id=report["execution_id"],
            payload=report,
        )
        first = await runtime.ingest_execution_event(event)
        second = await runtime.ingest_execution_event(event)
        assert first["status"] == "FEEDBACK_INGESTED"
        assert second["status"] == "DUPLICATE"
        assert len(strategy.feedback) == 1
        await runtime.shutdown()

    asyncio.run(scenario())


def test_scan_promotion_is_bounded(tmp_path, snapshot) -> None:
    intent = make_intent(snapshot, "WATCH")
    runtime = _runtime(
        tmp_path,
        FakeStrategy(intent),
        FakeRisk(make_report(intent)),
        max_active_symbols=1,
        max_deep_watch_symbols=1,
    )

    async def scenario() -> None:
        await runtime.startup()
        result = await runtime.scan_once()
        assert result["promoted"] == ["BTCUSDT"]
        assert runtime.get_watchlist()[0]["state"] == "DEEP_WATCH"
        await runtime.shutdown()

    asyncio.run(scenario())


def test_no_trade_watch_and_armed_never_call_risk(tmp_path, snapshot, now) -> None:
    async def scenario() -> None:
        for decision in ("NO_TRADE", "WATCH", "ARMED"):
            intent = make_intent(snapshot, decision)
            intent["signal_id"] += decision
            intent["integrity_hash"] = payload_integrity_hash(intent)
            risk = FakeRisk(make_report(intent))
            runtime = _runtime(tmp_path / decision, FakeStrategy(intent), risk, execution_enabled=True)
            await runtime.startup()
            result = await runtime.process_snapshot(snapshot, now_utc=now)
            assert result["status"] == decision
            assert risk.execute_calls == 0
            await runtime.shutdown()

    asyncio.run(scenario())


def test_risk_rejection_is_final(tmp_path, snapshot, now) -> None:
    intent = make_intent(snapshot)

    class RejectingRisk(FakeRisk):
        def validate(self, intent):
            return False, ("MAX_LOSS_LOCK",)

    risk = RejectingRisk(make_report(intent, approved=False))
    runtime = _runtime(tmp_path, FakeStrategy(intent), risk, execution_enabled=True)

    async def scenario() -> None:
        await runtime.startup()
        result = await runtime.process_snapshot(snapshot, now_utc=now)
        assert result["status"] == "RISK_REJECTED"
        assert result["reason_codes"] == ["MAX_LOSS_LOCK"]
        assert risk.execute_calls == 0
        await runtime.shutdown()

    asyncio.run(scenario())


def test_contract_mismatch_is_quarantined_before_strategy(tmp_path, snapshot, now) -> None:
    bad = dict(snapshot)
    bad["contract_version"] = "HM_WRONG"
    intent = make_intent(snapshot)
    risk = FakeRisk(make_report(intent))
    runtime = _runtime(tmp_path, FakeStrategy(intent), risk, execution_enabled=True)

    async def scenario() -> None:
        await runtime.startup()
        result = await runtime.process_snapshot(bad, now_utc=now)
        assert result["reason"] == "CONTRACT_MISMATCH"
        assert risk.execute_calls == 0
        await runtime.shutdown()

    asyncio.run(scenario())


def test_market_failure_blocks_new_entries_but_shutdown_management_runs(tmp_path, snapshot) -> None:
    intent = make_intent(snapshot)
    risk = FakeRisk(make_report(intent))

    class BrokenMarket(FakeMarket):
        def scan_once(self):
            raise RuntimeError("market unavailable")

    runtime = _runtime(tmp_path, FakeStrategy(intent), risk)
    runtime.market = BrokenMarket()

    async def scenario() -> None:
        await runtime.startup()
        try:
            await runtime.scan_once()
        except RuntimeError:
            pass
        assert runtime.health == HealthState.BLOCK_NEW_ENTRIES
        assert runtime.get_package_health()["market"] == "UNHEALTHY"
        shutdown = await runtime.shutdown()
        assert shutdown["management"]["managed"] is True

    asyncio.run(scenario())


def test_restart_preserves_duplicate_guard(tmp_path, snapshot, now) -> None:
    intent = make_intent(snapshot)

    async def scenario() -> None:
        first_risk = FakeRisk(make_report(intent))
        first = _runtime(tmp_path, FakeStrategy(intent), first_risk, execution_enabled=True)
        await first.startup()
        assert (await first.process_snapshot(snapshot, now_utc=now))["status"] == "APPROVED"
        await first.shutdown()
        second_risk = FakeRisk(make_report(intent))
        second = _runtime(tmp_path, FakeStrategy(intent), second_risk, execution_enabled=True)
        await second.startup()
        assert (await second.process_snapshot(snapshot, now_utc=now))["status"] == "DUPLICATE"
        assert second_risk.execute_calls == 0
        await second.shutdown()

    asyncio.run(scenario())


def test_global_execution_calls_are_serialized(tmp_path, snapshot, now) -> None:
    active = 0
    maximum = 0

    class DynamicStrategy(FakeStrategy):
        def evaluate(self, current, **kwargs):
            result = make_intent(current)
            result["signal_id"] = "sig_" + current["symbol"]
            result["integrity_hash"] = payload_integrity_hash(result)
            return result

    class SlowRisk(FakeRisk):
        def execute(self, intent):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            time.sleep(0.03)
            active -= 1
            report = make_report(intent)
            report["execution_id"] = "EX-" + intent["symbol"]
            report["integrity_hash"] = payload_integrity_hash(report)
            return report

    risk = SlowRisk(make_report(make_intent(snapshot)))
    runtime = _runtime(tmp_path, DynamicStrategy(make_intent(snapshot)), risk, execution_enabled=True)
    second = dict(snapshot)
    second["symbol"] = "ETHUSDT"
    second["snapshot_id"] = "snap_runtime_00000002"

    async def scenario() -> None:
        await runtime.startup()
        results = await asyncio.gather(
            runtime.process_snapshot(snapshot, now_utc=now),
            runtime.process_snapshot(second, now_utc=now),
        )
        assert [row["status"] for row in results] == ["APPROVED", "APPROVED"]
        assert maximum == 1
        await runtime.shutdown()

    asyncio.run(scenario())


def test_watch_expiry_demotes_symbol(tmp_path, snapshot, now) -> None:
    intent = make_intent(snapshot, "WATCH")
    runtime = _runtime(tmp_path, FakeStrategy(intent), FakeRisk(make_report(intent)))

    async def scenario() -> None:
        await runtime.startup()
        runtime._watch(
            "BTCUSDT",
            SymbolState.DEEP_WATCH,
            0.5,
            expires=utc_text(now - timedelta(seconds=1)),
        )
        assert await runtime.expire_watches(now) == ["BTCUSDT"]
        assert runtime.get_active_watches()[0]["state"] == "DEMOTED"
        await runtime.shutdown()

    asyncio.run(scenario())


def test_walkforward_is_delegated(tmp_path, snapshot) -> None:
    intent = make_intent(snapshot)
    runtime = _runtime(tmp_path, FakeStrategy(intent), FakeRisk(make_report(intent)))

    async def scenario() -> None:
        assert await runtime.walkforward([{"one": 1}], "out") == {"records": 1, "output_dir": "out"}
        runtime.store.close()

    asyncio.run(scenario())


def test_emergency_health_is_preserved(tmp_path, snapshot) -> None:
    intent = make_intent(snapshot)
    runtime = _runtime(tmp_path, FakeStrategy(intent), FakeRisk(make_report(intent)))

    async def scenario() -> None:
        await runtime.startup()
        result = await runtime.emergency_stop("operator-test")
        assert result["accepted"] is True
        assert runtime.health == HealthState.EMERGENCY
        assert runtime.get_system_status()["health"] == "EMERGENCY"
        await runtime.shutdown()

    asyncio.run(scenario())

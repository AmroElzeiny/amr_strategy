from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from crypto_trading_orchestrator.canonical import payload_integrity_hash, utc_text


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 9, 14, 18, 0, tzinfo=UTC)


@pytest.fixture
def snapshot(now: datetime) -> dict[str, Any]:
    stamp = utc_text(now)
    return {
        "contract_version": "HM_CRYPTO_V1",
        "snapshot_id": "snap_runtime_00000001",
        "created_at_utc": stamp,
        "event_time_utc": stamp,
        "exchange": "BYBIT",
        "environment": "DEMO",
        "market_mode": "DERIVATIVES",
        "symbol": "BTCUSDT",
    }


def make_intent(snapshot: dict[str, Any], decision: str = "ENTER") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contract_version": "HM_CRYPTO_V1",
        "signal_id": "sig_runtime_00000001",
        "snapshot_id": snapshot["snapshot_id"],
        "created_at_utc": snapshot["created_at_utc"],
        "exchange": "BYBIT",
        "environment": "DEMO",
        "market_mode": "DERIVATIVES",
        "symbol": snapshot["symbol"],
        "pattern_type": "BREAKOUT",
        "direction": "LONG",
        "order_intent": "OPEN" if decision == "ENTER" else "NONE",
        "decision": decision,
        "thesis_id": "thesis_runtime_0001",
        "attempt_no": 0,
        "deterministic_confidence": 90.0,
        "ai_confidence": None,
        "final_confidence": 90.0,
        "entry_plan": {"entry_reference": "100", "order_type": "MARKET"},
        "invalidation": {"stop_price": "99"},
        "targets": [{"price": "102"}],
        "risk_reward": 2.0,
        "ttl_ms": 45000,
        "config_version": "test",
        "strategy_version": "test",
    }
    payload["integrity_hash"] = payload_integrity_hash(payload)
    return payload


def make_report(intent: dict[str, Any], approved: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contract_version": "HM_CRYPTO_V1",
        "execution_id": "EX-runtime-0001" if approved else "",
        "signal_id": intent["signal_id"],
        "created_at_utc": intent["created_at_utc"],
        "exchange": intent["exchange"],
        "environment": intent["environment"],
        "market_mode": intent["market_mode"],
        "symbol": intent["symbol"],
        "approved": approved,
        "reason_codes": ["APPROVED"] if approved else ["RISK_LIMIT"],
        "order_state": "SIMULATED_NOT_SUBMITTED" if approved else "REJECTED",
        "reconciled": True,
    }
    payload["integrity_hash"] = payload_integrity_hash(payload)
    return payload


class FakeMarket:
    def scan_once(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return (
            {"eligible_symbols": ["BTCUSDT"], "promoted": ["BTCUSDT"]},
            [{"symbol": "BTCUSDT", "alert_id": "alert-1", "preliminary_score": 0.9}],
        )

    def deep_watch_symbols(self) -> tuple[str, ...]:
        return ("BTCUSDT",)

    def build_snapshot(self, symbol: str, alert: Any = None) -> dict[str, Any]:
        raise AssertionError("inject snapshots explicitly in unit tests")


class FakeStrategy:
    def __init__(self, intent: dict[str, Any]) -> None:
        self.intent = intent
        self.feedback: list[dict[str, Any]] = []

    def evaluate(self, snapshot: dict[str, Any], **_: Any) -> dict[str, Any]:
        return dict(self.intent)

    def ingest_execution_report(self, report: dict[str, Any]) -> dict[str, Any]:
        self.feedback.append(report)
        return {"learning_eligible": True, "execution_id": report["execution_id"]}

    def walkforward(self, records: list[dict[str, Any]], output_dir: str | None = None) -> dict[str, Any]:
        return {"records": len(records), "output_dir": output_dir}

    def champion(self) -> dict[str, Any]:
        return {"config_version": "test"}


class FakeRisk:
    def __init__(self, report: dict[str, Any], *, reconciled: bool = True) -> None:
        self.report = report
        self.reconciled = reconciled
        self.execute_calls = 0

    def reconcile(self) -> dict[str, Any]:
        return {"reconciled": self.reconciled, "foreign_orders": 0, "ambiguous_positions": 0}

    def validate(self, intent: dict[str, Any]) -> tuple[bool, tuple[str, ...]]:
        return True, ()

    def execute(self, intent: dict[str, Any]) -> dict[str, Any]:
        self.execute_calls += 1
        return dict(self.report)

    def manage(self) -> dict[str, Any]:
        return {"managed": True}

    def emergency(self, reason: str) -> dict[str, Any]:
        return {"accepted": True, "reason": reason}

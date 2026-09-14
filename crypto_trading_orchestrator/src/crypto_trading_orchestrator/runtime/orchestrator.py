from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..canonical import (
    canonical_hash,
    integrity_valid,
    parse_utc,
    primitive,
    primitive_dict,
    utc_now,
    utc_text,
)
from ..compatibility import CompatibilityResult, validate_compatibility
from ..config import OrchestratorConfig
from ..events import PriorityEventBus
from ..models import (
    Event,
    EventType,
    HealthState,
    PackageIdentity,
    Priority,
    RuntimeState,
    SymbolState,
    WatchRecord,
)
from ..persistence import OrchestratorStore


class TradingOrchestrator:
    """Coordinates package APIs while keeping all trading authority in Packages 1-3."""

    def __init__(
        self,
        config: OrchestratorConfig,
        market: Any,
        strategy: Any,
        risk: Any,
        *,
        identities: Mapping[str, PackageIdentity] | None = None,
        store: OrchestratorStore | None = None,
    ) -> None:
        self.config = config
        self.market = market
        self.strategy = strategy
        self.risk = risk
        self.identities = dict(identities or {})
        self.store = store or OrchestratorStore(config.state_db)
        self.bus = PriorityEventBus(config.market_queue_max, coalesce_market=config.coalesce_snapshots)
        self.runtime_session_id = "run_" + uuid.uuid4().hex
        self.state = RuntimeState.BOOT
        self.health = HealthState.HEALTHY
        self.reconciled = False
        self.accepting_new_entries = False
        self.watches: dict[str, WatchRecord] = {}
        self.package_health: dict[str, str] = {
            "market": "UNKNOWN",
            "strategy": "UNKNOWN",
            "risk": "UNKNOWN",
            "ai": "PACKAGE_2_OWNED",
            "private_ws": "PACKAGE_3_OWNED",
            "database": "HEALTHY",
            "contract": "UNKNOWN",
        }
        self.state_history: list[dict[str, str]] = []
        self.metrics: Counter[str] = Counter()
        self._symbol_locks: dict[str, asyncio.Lock] = {}
        self._strategy_slots = asyncio.Semaphore(config.max_strategy_evaluations)
        self._execution_lock = asyncio.Lock()
        self._stop = asyncio.Event()
        self._closed = False
        self.compatibility: CompatibilityResult | None = None

    def _transition(self, state: RuntimeState) -> None:
        self.state = state
        self.state_history.append({"state": str(state), "at_utc": utc_text()})
        if state in {RuntimeState.RUNNING, RuntimeState.READY}:
            self.health = HealthState.HEALTHY
        elif state == RuntimeState.DEGRADED:
            self.health = HealthState.DEGRADED
        elif state == RuntimeState.BLOCKED:
            self.health = HealthState.BLOCK_NEW_ENTRIES
        if not self._closed:
            self.store.set("runtime", self.get_runtime_status())

    async def _emit(
        self,
        event_type: EventType,
        priority: Priority,
        *,
        package: str,
        symbol: str = "",
        snapshot_id: str = "",
        signal_id: str = "",
        thesis_id: str = "",
        execution_id: str = "",
        payload: Mapping[str, Any] | None = None,
    ) -> Event:
        event = Event(
            event_type=event_type,
            priority=priority,
            runtime_session_id=self.runtime_session_id,
            package=package,
            symbol=symbol,
            snapshot_id=snapshot_id,
            signal_id=signal_id,
            thesis_id=thesis_id,
            execution_id=execution_id,
            payload=dict(payload or {}),
        )
        self.store.record_event(event)
        await self.bus.publish(event)
        return event

    async def startup(self) -> dict[str, Any]:
        try:
            self._transition(RuntimeState.CONFIG_VALIDATE)
            self.config.validate()
            self.config.ensure_directories()
            self.store.register_session(self.runtime_session_id, str(self.state), self.config.config_hash)
            self._transition(RuntimeState.PACKAGE_DISCOVERY)
            if self.identities:
                self._transition(RuntimeState.CONTRACT_VALIDATE)
                self.compatibility = validate_compatibility(self.config, self.identities)
                if not self.compatibility.compatible:
                    raise RuntimeError(";".join(self.compatibility.reasons))
                self.package_health["contract"] = "HEALTHY"
            self._transition(RuntimeState.EXCHANGE_MODE_VALIDATE)
            self.config.validate()
            self._validate_adapter_environment()
            self._transition(RuntimeState.RISK_EXECUTION_RECONCILE)
            reconciliation = primitive_dict(await asyncio.to_thread(self.risk.reconcile))
            self.reconciled = bool(reconciliation.get("reconciled"))
            self.package_health["risk"] = "HEALTHY" if self.reconciled else "BLOCKED"
            if not self.reconciled and self.config.require_reconciliation:
                await self._emit(
                    EventType.RECONCILIATION_REQUIRED,
                    Priority.RISK_RECONCILIATION,
                    package="risk",
                    payload=reconciliation,
                )
                raise RuntimeError("ACCOUNT_RECONCILIATION_REQUIRED")
            await self._emit(
                EventType.RECONCILIATION_COMPLETE,
                Priority.RISK_RECONCILIATION,
                package="risk",
                payload=reconciliation,
            )
            self._transition(RuntimeState.MARKET_DATA_START)
            self.package_health["market"] = "HEALTHY"
            self.package_health["strategy"] = "HEALTHY"
            if self.config.recover_active_watches:
                self.watches = self.store.load_watches()
            self._transition(RuntimeState.SCANNER_START)
            self._transition(RuntimeState.READY)
            self.accepting_new_entries = self.reconciled and self.health == HealthState.HEALTHY
            self._transition(RuntimeState.RUNNING)
            return self.get_runtime_status()
        except Exception as exc:
            self.accepting_new_entries = False
            self.metrics["startup_failures"] += 1
            self.store.set("last_error", {"stage": str(self.state), "error": str(exc), "at_utc": utc_text()})
            self._transition(RuntimeState.BLOCKED)
            return {**self.get_runtime_status(), "error": str(exc)}

    def _validate_adapter_environment(self) -> None:
        expected = {
            "exchange": self.config.exchange,
            "environment": self.config.trading_env,
            "market_mode": self.config.market_mode,
        }
        candidates = {
            "market": getattr(getattr(self.market, "engine", None), "settings", None),
            "risk": getattr(self.risk, "settings", None),
        }
        for role, settings in candidates.items():
            if settings is None:
                continue
            for field, wanted in expected.items():
                actual = getattr(settings, field, None)
                if actual is not None and str(actual).upper() != wanted:
                    raise RuntimeError(f"PACKAGE_ENVIRONMENT_MISMATCH:{role}:{field}:{actual}:{wanted}")

    def _watch(
        self,
        symbol: str,
        state: SymbolState,
        priority: float,
        *,
        alert_id: str = "",
        expires: str | None = None,
    ) -> WatchRecord:
        watch = WatchRecord(symbol, state, priority, expires, alert_id)
        self.watches[symbol] = watch
        self.store.save_watch(watch)
        return watch

    async def scan_once(self) -> dict[str, Any]:
        if self.state not in {RuntimeState.READY, RuntimeState.RUNNING, RuntimeState.DEGRADED}:
            raise RuntimeError("RUNTIME_NOT_READY")
        started = time.perf_counter()
        try:
            scan, alerts = await asyncio.to_thread(self.market.scan_once)
            self.package_health["market"] = "HEALTHY"
        except Exception:
            self.package_health["market"] = "UNHEALTHY"
            if self.config.block_on_market_unhealthy:
                self.health = HealthState.BLOCK_NEW_ENTRIES
                self.accepting_new_entries = False
            self.metrics["market_errors"] += 1
            raise
        promoted = [str(value) for value in scan.get("promoted", [])]
        ranked_alerts = sorted(
            alerts,
            key=lambda row: (
                -float(row.get("preliminary_score", 0.0)),
                str(row.get("symbol", "")),
                str(row.get("alert_id", "")),
            ),
        )
        if self.config.breakout_promotion_enabled:
            for alert in ranked_alerts:
                if float(alert.get("preliminary_score", 0.0)) < self.config.promotion_min_score:
                    continue
                symbol = str(alert.get("symbol", ""))
                if symbol and symbol not in promoted:
                    promoted.append(symbol)
        promoted = promoted[: self.config.max_active_symbols]
        deep = set(str(value) for value in await asyncio.to_thread(self.market.deep_watch_symbols))
        deep_order = [symbol for symbol in promoted if symbol in deep][: self.config.max_deep_watch_symbols]
        alert_by_symbol = {str(row.get("symbol", "")): row for row in ranked_alerts}
        for rank, symbol in enumerate(promoted):
            alert = alert_by_symbol.get(symbol, {})
            state = SymbolState.DEEP_WATCH if symbol in deep_order else SymbolState.PROMOTED
            priority = float(alert.get("preliminary_score", max(0.0, 1.0 - rank / max(1, len(promoted)))))
            self._watch(
                symbol,
                state,
                priority,
                alert_id=str(alert.get("alert_id", "")),
                expires=str(alert.get("watch_until_utc")) if alert.get("watch_until_utc") else None,
            )
            await self._emit(
                EventType.SYMBOL_PROMOTED,
                Priority.MARKET_DEEP_WATCH,
                package="market",
                symbol=symbol,
                snapshot_id=str(alert.get("snapshot_id", "")),
                payload={"state": str(state), "rank": rank, "alert": alert},
            )
        self.metrics["scan_cycles"] += 1
        self.metrics["symbols_scanned"] += len(scan.get("eligible_symbols", []))
        self.metrics["alerts"] += len(alerts)
        self.metrics["promoted"] += len(promoted)
        self.metrics["scan_latency_ms_total"] += int((time.perf_counter() - started) * 1000)
        return {"scan": scan, "alerts": alerts, "promoted": promoted, "deep_watch": deep_order}

    async def demote_symbol(self, symbol: str, reason: str) -> dict[str, Any]:
        watch = self._watch(symbol, SymbolState.DEMOTED, 0.0)
        await self._emit(
            EventType.SYMBOL_DEMOTED,
            Priority.MARKET_DEEP_WATCH,
            package="market",
            symbol=symbol,
            payload={"reason": reason},
        )
        return primitive_dict(watch)

    async def expire_watches(self, now_utc: datetime | None = None) -> list[str]:
        now = now_utc or utc_now()
        expired: list[str] = []
        for symbol, watch in list(self.watches.items()):
            if watch.expires_at_utc and parse_utc(watch.expires_at_utc) <= now:
                await self.demote_symbol(symbol, "WATCH_TTL_EXPIRED")
                expired.append(symbol)
        return expired

    async def build_and_process(
        self, symbol: str, alert: Any = None, *, persist_strategy: bool = True
    ) -> dict[str, Any]:
        snapshot = await asyncio.to_thread(self.market.build_snapshot, symbol, alert)
        self.metrics["snapshots_generated"] += 1
        await self._emit(
            EventType.MARKET_SNAPSHOT_READY,
            Priority.MARKET_DEEP_WATCH,
            package="market",
            symbol=symbol,
            snapshot_id=str(snapshot.get("snapshot_id", "")),
            payload={"snapshot_hash": canonical_hash(snapshot)},
        )
        return await self.process_snapshot(snapshot, persist_strategy=persist_strategy)

    def _symbol_lock(self, symbol: str) -> asyncio.Lock:
        if symbol not in self._symbol_locks:
            self._symbol_locks[symbol] = asyncio.Lock()
        return self._symbol_locks[symbol]

    @staticmethod
    def _age_ms(value: str, now: datetime) -> int:
        return max(0, int((now - parse_utc(value)).total_seconds() * 1000))

    async def process_snapshot(
        self,
        snapshot: Mapping[str, Any],
        *,
        persist_strategy: bool = True,
        now_utc: datetime | None = None,
    ) -> dict[str, Any]:
        now = now_utc or utc_now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        symbol = str(snapshot.get("symbol", ""))
        snapshot_id = str(snapshot.get("snapshot_id", ""))
        if snapshot.get("contract_version") != self.config.contract_version:
            self.store.quarantine("snapshot", "contract_mismatch", snapshot_id or "unknown", snapshot)
            return {"status": "QUARANTINED", "reason": "CONTRACT_MISMATCH", "snapshot_id": snapshot_id}
        if not symbol or not snapshot_id:
            self.store.quarantine("snapshot", "missing_identity", snapshot_id or "unknown", snapshot)
            return {"status": "QUARANTINED", "reason": "SNAPSHOT_IDENTITY_MISSING"}
        try:
            if (
                self._age_ms(str(snapshot.get("event_time_utc", "")), now)
                > self.config.max_snapshot_to_strategy_ms
            ):
                self.metrics["expired_snapshots"] += 1
                return {"status": "EXPIRED", "reason": "SNAPSHOT_TTL_EXCEEDED", "snapshot_id": snapshot_id}
        except ValueError as exc:
            self.store.quarantine("snapshot", str(exc), snapshot_id, snapshot)
            return {"status": "QUARANTINED", "reason": str(exc), "snapshot_id": snapshot_id}
        async with self._symbol_lock(symbol), self._strategy_slots:
            started = time.perf_counter()
            try:
                intent = primitive_dict(
                    await asyncio.to_thread(
                        self.strategy.evaluate, snapshot, persist=persist_strategy, now_utc=now
                    )
                )
                self.package_health["strategy"] = "HEALTHY"
            except Exception as exc:
                self.package_health["strategy"] = "UNHEALTHY"
                if self.config.block_on_strategy_unhealthy:
                    self.health = HealthState.BLOCK_NEW_ENTRIES
                    self.accepting_new_entries = False
                self.metrics["strategy_errors"] += 1
                self.store.quarantine("snapshot", f"strategy:{exc}", snapshot_id, snapshot)
                return {"status": "ERROR", "reason": f"STRATEGY_ERROR:{exc}", "snapshot_id": snapshot_id}
            latency_ms = int((time.perf_counter() - started) * 1000)
            self.metrics["strategy_evaluations"] += 1
            self.metrics["strategy_latency_ms_total"] += latency_ms
            if str(intent.get("snapshot_id", "")) != snapshot_id or str(intent.get("symbol", "")) != symbol:
                self.store.quarantine("intent", "lineage_mismatch", str(intent.get("signal_id", "")), intent)
                return {"status": "QUARANTINED", "reason": "INTENT_LINEAGE_MISMATCH", "intent": intent}
            if intent.get("contract_version") != self.config.contract_version or any(
                str(intent.get(field, "")).upper() != expected
                for field, expected in (
                    ("exchange", self.config.exchange),
                    ("environment", self.config.trading_env),
                    ("market_mode", self.config.market_mode),
                )
            ):
                self.store.quarantine(
                    "intent", "contract_or_environment_mismatch", str(intent.get("signal_id", "")), intent
                )
                return {"status": "QUARANTINED", "reason": "INTENT_CONTRACT_MISMATCH", "intent": intent}
            if not integrity_valid(intent):
                self.store.quarantine(
                    "intent", "integrity_hash_mismatch", str(intent.get("signal_id", "")), intent
                )
                return {"status": "QUARANTINED", "reason": "INTENT_INTEGRITY_INVALID", "intent": intent}
            decision = str(intent.get("decision", "NO_TRADE"))
            self.metrics[f"decision_{decision.lower()}"] += 1
            event_type = {
                "ENTER": EventType.STRATEGY_ENTER,
                "ARMED": EventType.STRATEGY_ARMED,
                "WATCH": EventType.STRATEGY_WATCH,
            }.get(decision, EventType.STRATEGY_NO_TRADE)
            signal_id = str(intent.get("signal_id", ""))
            thesis_id = str(intent.get("thesis_id", ""))
            await self._emit(
                event_type,
                Priority.STRATEGY_ENTER if decision == "ENTER" else Priority.MARKET_DEEP_WATCH,
                package="strategy",
                symbol=symbol,
                snapshot_id=snapshot_id,
                signal_id=signal_id,
                thesis_id=thesis_id,
                payload={
                    "decision": decision,
                    "confidence": intent.get("final_confidence"),
                    "latency_ms": latency_ms,
                },
            )
            self.store.upsert_lineage(signal_id, intent)
            if decision != "ENTER":
                watch_state = SymbolState.ARMED if decision == "ARMED" else SymbolState.DEEP_WATCH
                self._watch(symbol, watch_state, float(intent.get("final_confidence", 0.0)))
                return {"status": decision, "intent": intent, "execution_report": None}
            return await self._route_enter(intent, now)

    async def _route_enter(self, intent: Mapping[str, Any], now: datetime) -> dict[str, Any]:
        signal_id = str(intent.get("signal_id", ""))
        symbol = str(intent.get("symbol", ""))
        if (
            not self.reconciled
            or not self.accepting_new_entries
            or self.health
            in {
                HealthState.BLOCK_NEW_ENTRIES,
                HealthState.EMERGENCY,
            }
        ):
            self.metrics["entries_blocked"] += 1
            return {"status": "BLOCKED", "reason": "RUNTIME_ENTRY_GATE", "intent": dict(intent)}
        try:
            if self._age_ms(str(intent.get("created_at_utc", "")), now) > int(intent.get("ttl_ms", 0)):
                self.metrics["expired_intents"] += 1
                return {"status": "EXPIRED", "reason": "TRADE_INTENT_TTL_EXCEEDED", "intent": dict(intent)}
        except (TypeError, ValueError):
            return {"status": "QUARANTINED", "reason": "TRADE_INTENT_TIME_INVALID", "intent": dict(intent)}
        if not self.config.execution_permitted:
            self.metrics["entries_disabled"] += 1
            return {"status": "BLOCKED", "reason": "ORCHESTRATOR_EXECUTION_DISABLED", "intent": dict(intent)}
        if not self.store.claim_once("signal_execution", signal_id):
            self.metrics["duplicate_signals"] += 1
            return {"status": "DUPLICATE", "reason": "SIGNAL_ALREADY_ROUTED", "intent": dict(intent)}
        async with self._execution_lock:
            valid, reasons = await asyncio.to_thread(self.risk.validate, intent)
            if not valid:
                self.metrics["risk_rejections"] += 1
                lock_type: EventType | None = None
                if "DAILY_LOSS_LOCK" in reasons:
                    lock_type = EventType.DAILY_LOSS_LOCK
                    self.metrics["daily_locks"] += 1
                elif "MAX_LOSS_LOCK" in reasons:
                    lock_type = EventType.MAX_LOSS_LOCK
                    self.metrics["max_locks"] += 1
                if lock_type is not None:
                    self.health = HealthState.BLOCK_NEW_ENTRIES
                    self.accepting_new_entries = False
                    await self._emit(
                        lock_type,
                        Priority.RISK_RECONCILIATION,
                        package="risk",
                        symbol=symbol,
                        signal_id=signal_id,
                        payload={"reason_codes": list(reasons)},
                    )
                await self._emit(
                    EventType.RISK_REJECTED,
                    Priority.RISK_RECONCILIATION,
                    package="risk",
                    symbol=symbol,
                    signal_id=signal_id,
                    payload={"reason_codes": list(reasons)},
                )
                return {"status": "RISK_REJECTED", "reason_codes": list(reasons), "intent": dict(intent)}
            started = time.perf_counter()
            try:
                report = primitive_dict(await asyncio.to_thread(self.risk.execute, intent))
                self.package_health["risk"] = "HEALTHY"
            except Exception as exc:
                self.package_health["risk"] = "UNHEALTHY"
                if self.config.block_on_risk_unhealthy:
                    self.health = HealthState.BLOCK_NEW_ENTRIES
                    self.accepting_new_entries = False
                self.metrics["execution_errors"] += 1
                await self._emit(
                    EventType.EXECUTION_ERROR,
                    Priority.EXECUTION_PROTECTION,
                    package="risk",
                    symbol=symbol,
                    signal_id=signal_id,
                    payload={"error": str(exc)},
                )
                return {"status": "ERROR", "reason": f"RISK_EXECUTION_ERROR:{exc}", "intent": dict(intent)}
            latency_ms = int((time.perf_counter() - started) * 1000)
            self.metrics["risk_latency_ms_total"] += latency_ms
            if latency_ms > self.config.max_strategy_to_risk_ms:
                self.metrics["risk_latency_breaches"] += 1
            return await self.handle_execution_report(report, intent=intent)

    async def handle_execution_report(
        self, report: Mapping[str, Any], *, intent: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        payload = primitive_dict(report)
        execution_id = str(payload.get("execution_id", ""))
        signal_id = str(payload.get("signal_id", ""))
        symbol = str(payload.get("symbol", ""))
        if (
            payload.get("contract_version") != self.config.contract_version
            or payload.get("reconciled") is not True
        ):
            self.store.quarantine(
                "execution_report", "contract_or_reconciliation_mismatch", execution_id or signal_id, payload
            )
            return {"status": "QUARANTINED", "reason": "EXECUTION_REPORT_CONTRACT_INVALID", "report": payload}
        if not integrity_valid(payload):
            self.store.quarantine(
                "execution_report", "integrity_hash_mismatch", execution_id or signal_id, payload
            )
            return {
                "status": "QUARANTINED",
                "reason": "EXECUTION_REPORT_INTEGRITY_INVALID",
                "report": payload,
            }
        lineage = self.store.get_lineage(signal_id)
        if lineage is None or (intent is not None and canonical_hash(lineage) != canonical_hash(intent)):
            self.store.quarantine(
                "execution_report", "unknown_or_changed_lineage", execution_id or signal_id, payload
            )
            return {"status": "QUARANTINED", "reason": "EXECUTION_LINEAGE_INVALID", "report": payload}
        if any(
            str(payload.get(field, "")) != str(lineage.get(field, ""))
            for field in ("exchange", "environment", "market_mode", "symbol")
        ):
            self.store.quarantine(
                "execution_report", "instrument_lineage_mismatch", execution_id or signal_id, payload
            )
            return {"status": "QUARANTINED", "reason": "EXECUTION_INSTRUMENT_MISMATCH", "report": payload}
        lineage["execution_id"] = execution_id
        lineage["execution_report_hash"] = str(payload.get("integrity_hash", ""))
        self.store.upsert_lineage(signal_id, lineage)
        approved = bool(payload.get("approved"))
        if payload.get("daily_loss_lock") is True or payload.get("max_loss_lock") is True:
            self.health = HealthState.BLOCK_NEW_ENTRIES
            self.accepting_new_entries = False
        event_type = EventType.RISK_APPROVED if approved else EventType.RISK_REJECTED
        await self._emit(
            event_type,
            Priority.RISK_RECONCILIATION,
            package="risk",
            symbol=symbol,
            signal_id=signal_id,
            execution_id=execution_id,
            payload={
                "reason_codes": payload.get("reason_codes", []),
                "order_state": payload.get("order_state"),
            },
        )
        if approved:
            self.metrics["risk_approvals"] += 1
            order_state = str(payload.get("order_state", ""))
            if order_state not in {"SIMULATED_NOT_SUBMITTED", "REJECTED", "NONE"}:
                self.metrics["orders_submitted"] += 1
                await self._emit(
                    EventType.ORDER_SUBMITTED,
                    Priority.EXECUTION_PROTECTION,
                    package="risk",
                    symbol=symbol,
                    signal_id=signal_id,
                    execution_id=execution_id,
                    payload={"order_state": order_state},
                )
            self._watch(symbol, SymbolState.IN_TRADE, float(lineage.get("final_confidence", 0.0)))
            return {"status": "APPROVED", "intent": intent or lineage, "execution_report": payload}
        self.metrics["risk_rejections"] += 1
        return {"status": "RISK_REJECTED", "intent": intent or lineage, "execution_report": payload}

    async def ingest_execution_event(self, event: Event) -> dict[str, Any]:
        if event.event_type not in {
            EventType.ORDER_PARTIAL_FILL,
            EventType.ORDER_FILLED,
            EventType.POSITION_PROTECTED,
            EventType.POSITION_REDUCED,
            EventType.POSITION_CLOSED,
            EventType.DAILY_LOSS_LOCK,
            EventType.MAX_LOSS_LOCK,
            EventType.EXECUTION_HEALTH_LOCK,
            EventType.EXECUTION_ERROR,
        }:
            raise ValueError("NOT_AN_EXECUTION_EVENT")
        if not self.store.record_event(event):
            return {"status": "DUPLICATE", "event_id": event.event_id}
        await self.bus.publish(event)
        if event.event_type == EventType.ORDER_PARTIAL_FILL:
            self.metrics["partial_fills"] += 1
        elif event.event_type == EventType.ORDER_FILLED:
            self.metrics["fills"] += 1
        if event.event_type in {
            EventType.DAILY_LOSS_LOCK,
            EventType.MAX_LOSS_LOCK,
            EventType.EXECUTION_HEALTH_LOCK,
            EventType.EXECUTION_ERROR,
        }:
            self.health = HealthState.BLOCK_NEW_ENTRIES
            self.accepting_new_entries = False
        if event.event_type == EventType.POSITION_CLOSED:
            report = dict(event.payload)
            if not self.reconciled or not integrity_valid(report):
                self.store.quarantine("feedback", "unreconciled_or_invalid", event.execution_id, report)
                return {"status": "QUARANTINED", "event_id": event.event_id}
            if not self.store.claim_once("strategy_feedback", event.execution_id):
                return {"status": "DUPLICATE", "event_id": event.event_id}
            outcome = primitive_dict(await asyncio.to_thread(self.strategy.ingest_execution_report, report))
            self.metrics["feedback_outcomes_ingested"] += 1
            await self._emit(
                EventType.LEARNING_OUTCOME_READY,
                Priority.RESEARCH,
                package="strategy",
                symbol=event.symbol,
                signal_id=event.signal_id,
                execution_id=event.execution_id,
                payload=outcome,
            )
            self._watch(event.symbol, SymbolState.COOLDOWN, 0.0)
            return {"status": "FEEDBACK_INGESTED", "outcome": outcome}
        return {"status": "ACCEPTED", "event_id": event.event_id}

    async def reconcile(self) -> dict[str, Any]:
        result = primitive_dict(await asyncio.to_thread(self.risk.reconcile))
        self.reconciled = bool(result.get("reconciled"))
        self.accepting_new_entries = self.reconciled and self.health == HealthState.HEALTHY
        if not self.reconciled:
            self.health = HealthState.BLOCK_NEW_ENTRIES
        await self._emit(
            EventType.RECONCILIATION_COMPLETE if self.reconciled else EventType.RECONCILIATION_REQUIRED,
            Priority.RISK_RECONCILIATION,
            package="risk",
            payload=result,
        )
        return result

    async def walkforward(
        self, records: Sequence[Mapping[str, Any]], output_dir: str | None = None
    ) -> dict[str, Any]:
        if not self.config.walkforward_enabled:
            raise RuntimeError("WALKFORWARD_DISABLED")
        return primitive_dict(await asyncio.to_thread(self.strategy.walkforward, records, output_dir))

    async def emergency_stop(self, reason: str) -> dict[str, Any]:
        self.accepting_new_entries = False
        self._transition(RuntimeState.BLOCKED)
        self.health = HealthState.EMERGENCY
        self.store.set("runtime", self.get_runtime_status())
        result = primitive_dict(await asyncio.to_thread(self.risk.emergency, reason))
        self.store.set("emergency", {"reason": reason, "result": result, "at_utc": utc_text()})
        return result

    async def run(self, *, scan_interval_sec: float = 30.0, once: bool = False) -> None:
        if self.state == RuntimeState.BOOT:
            await self.startup()
        if self.state != RuntimeState.RUNNING:
            return
        while not self._stop.is_set():
            if bool(self.store.get("shutdown_requested", {}).get("requested")):
                self.request_stop()
                break
            if self.config.scanner_enabled:
                cycle = await self.scan_once()
                alert_by_symbol = {str(row.get("symbol", "")): row for row in cycle["alerts"]}
                for symbol in cycle["deep_watch"]:
                    if self._stop.is_set():
                        break
                    await self.build_and_process(symbol, alert_by_symbol.get(symbol))
            if once:
                return
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=scan_interval_sec)
            except TimeoutError:
                pass

    def request_stop(self) -> None:
        self._stop.set()

    async def shutdown(self) -> dict[str, Any]:
        if self._closed:
            return {"state": str(RuntimeState.STOPPED), "already_closed": True}
        self.accepting_new_entries = False
        self._transition(RuntimeState.STOPPING)
        self._stop.set()
        management: dict[str, Any] = {}
        if self.reconciled:
            try:
                management = primitive_dict(
                    await asyncio.wait_for(
                        asyncio.to_thread(self.risk.manage), timeout=self.config.shutdown_settle_timeout_sec
                    )
                )
            except Exception as exc:
                management = {"managed": False, "error": str(exc)}
        self._transition(RuntimeState.STOPPED)
        self.store.update_session(self.runtime_session_id, str(self.state), stopped=True)
        result = {"state": str(self.state), "management": management}
        self._write_session_audit(result)
        self._closed = True
        self.store.close()
        return result

    def _write_session_audit(self, shutdown: Mapping[str, Any]) -> None:
        document = {
            "runtime_session_id": self.runtime_session_id,
            "state_history": self.state_history,
            "config_hashes": self.get_config_hashes(),
            "metrics": dict(self.metrics),
            "package_health": dict(self.package_health),
            "reconciled": self.reconciled,
            "shutdown": dict(shutdown),
            "event_counts": self.store.counts(),
            "generated_at_utc": utc_text(),
        }
        target = Path(self.config.audit_dir) / f"{self.runtime_session_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document, sort_keys=True, indent=2), encoding="utf-8")

    def get_runtime_status(self) -> dict[str, Any]:
        return {
            "runtime_session_id": self.runtime_session_id,
            "state": str(self.state),
            "health": str(self.health),
            "reconciled": self.reconciled,
            "accepting_new_entries": self.accepting_new_entries,
            "execution_permitted": self.config.execution_permitted,
            "exchange": self.config.exchange,
            "environment": self.config.trading_env,
            "market_mode": self.config.market_mode,
            "scanner_enabled": self.config.scanner_enabled,
            "package_health": dict(self.package_health),
            "watch_count": len(self.watches),
            "event_bus": self.bus.snapshot(),
            "metrics": dict(self.metrics),
            "config_hash": self.config.config_hash,
            "compatibility": self.compatibility.to_dict() if self.compatibility else None,
        }

    def get_system_status(self) -> dict[str, Any]:
        return self.get_runtime_status()

    def get_watchlist(self) -> list[dict[str, Any]]:
        return [primitive(watch) for _, watch in sorted(self.watches.items())]

    def get_active_watches(self) -> list[dict[str, Any]]:
        return self.get_watchlist()

    def get_active_signals(self) -> list[dict[str, Any]]:
        return self.store.active_lineage()

    def get_active_positions(self) -> list[dict[str, Any]]:
        value = self.store.get("active_positions", [])
        return list(value) if isinstance(value, list) else []

    def get_risk_state(self) -> dict[str, Any]:
        return {
            "health": str(self.health),
            "reconciled": self.reconciled,
            "accepting_new_entries": self.accepting_new_entries,
            "execution_permitted": self.config.execution_permitted,
        }

    def get_package_health(self) -> dict[str, str]:
        return dict(self.package_health)

    def get_last_events(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.store.last_events(limit)

    def get_metrics(self) -> dict[str, Any]:
        result: dict[str, Any] = dict(self.metrics)
        for total, count, target in (
            ("scan_latency_ms_total", "scan_cycles", "average_scan_latency_ms"),
            ("strategy_latency_ms_total", "strategy_evaluations", "average_strategy_latency_ms"),
            ("risk_latency_ms_total", "risk_approvals", "average_risk_latency_ms"),
        ):
            result[target] = round(result.get(total, 0) / max(1, result.get(count, 0)), 3)
        result["event_bus"] = self.bus.snapshot()
        return result

    def get_config_hashes(self) -> dict[str, str]:
        rows = {"orchestrator": self.config.config_hash}
        rows.update({role: item.build_hash for role, item in self.identities.items()})
        return rows

    def get_champion_config(self) -> dict[str, Any]:
        return primitive_dict(self.strategy.champion())

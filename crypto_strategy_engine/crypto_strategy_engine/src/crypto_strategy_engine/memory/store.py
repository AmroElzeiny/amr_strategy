from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import math
import sqlite3
from typing import Any, Mapping

from ..models import CONTRACT_VERSION, canonical_hash, canonical_json, dotted_get

MEMORY_SCHEMA_VERSION = "HM_TRADE_MEMORY_V1"
RETRIEVAL_POLICY_VERSION = "HM_HISTORICAL_ANALOGUE_V2"
INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def execution_report_integrity_hash(report: Mapping[str, Any]) -> str:
    """Canonical Package-2 verification rule for feedback reports.

    Package 2 never trusts a self-declared hash. The hash is SHA-256 over canonical
    JSON of the complete report excluding ``integrity_hash``. Package 3 can reproduce
    this without importing Package 2.
    """

    return canonical_hash({key: value for key, value in report.items() if key != "integrity_hash"})


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _band(value: Any, *, width: float = 10.0) -> str:
    number = _safe_float(value)
    if number is None:
        return "UNAVAILABLE"
    floor = int(number // width) * int(width)
    return f"{floor}-{floor + int(width)}"


def _decision_features(payload: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = payload.get("snapshot") if isinstance(payload.get("snapshot"), Mapping) else {}
    candidate = payload.get("candidate") if isinstance(payload.get("candidate"), Mapping) else {}
    evidence = candidate.get("evidence") if isinstance(candidate.get("evidence"), Mapping) else {}
    scores = candidate.get("component_scores") if isinstance(candidate.get("component_scores"), Mapping) else {}
    return {
        "pattern": candidate.get("pattern_type"),
        "direction": candidate.get("direction"),
        "branch": candidate.get("branch") or evidence.get("branch"),
        "regime": dotted_get(snapshot, "regime.type", "UNKNOWN"),
        "breakout_quality_band": _band(scores.get("breakout_quality")),
        "pullback_quality_band": _band(scores.get("pullback_quality")),
        "balance_risk_band": _band(evidence.get("balance_risk_score") or dotted_get(snapshot, "regime.balance_risk_score")),
        "value_migration": dotted_get(snapshot, "volume_profile.value_migration", "UNAVAILABLE"),
        "orderflow_state": dotted_get(snapshot, "orderflow.state", dotted_get(snapshot, "orderflow.directional_state", "UNAVAILABLE")),
        "volatility_regime": dotted_get(snapshot, "regime.volatility", dotted_get(snapshot, "regime.volatility_regime", "UNAVAILABLE")),
        "liquidity_bucket": dotted_get(snapshot, "instrument.liquidity_bucket", "UNKNOWN"),
        "session_bucket": dotted_get(snapshot, "instrument.session_bucket", "UNKNOWN"),
        "market_mode": snapshot.get("market_mode"),
        "symbol": snapshot.get("symbol"),
    }


def _similarity(current: Mapping[str, Any], prior: Mapping[str, Any]) -> float:
    """Bounded deterministic analogue similarity; no future information enters it."""

    weights = {
        "pattern": 3.0,
        "regime": 2.5,
        "direction": 2.0,
        "branch": 1.5,
        "breakout_quality_band": 1.0,
        "pullback_quality_band": 1.0,
        "balance_risk_band": 1.2,
        "value_migration": 1.0,
        "orderflow_state": 1.0,
        "volatility_regime": 0.8,
        "liquidity_bucket": 0.8,
        "session_bucket": 0.6,
        "market_mode": 2.0,
        "symbol": 0.5,
    }
    earned = 0.0
    possible = 0.0
    for key, weight in weights.items():
        left = current.get(key)
        right = prior.get(key)
        if left in {None, "", "UNAVAILABLE", "UNKNOWN"} or right in {None, "", "UNAVAILABLE", "UNKNOWN"}:
            continue
        possible += weight
        if str(left) == str(right):
            earned += weight
    return 0.0 if possible <= 0 else earned / possible


class TradeMemoryStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10.0)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def _init(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS decisions(
                    signal_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    candidate_hash TEXT NOT NULL,
                    snapshot_id TEXT NOT NULL,
                    event_time_utc TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    market_mode TEXT NOT NULL,
                    regime TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outcomes(
                    execution_id TEXT PRIMARY KEY,
                    signal_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    candidate_hash TEXT NOT NULL,
                    event_time_utc TEXT NOT NULL,
                    resolved_at_utc TEXT NOT NULL,
                    learning_eligible INTEGER NOT NULL,
                    rejection_reason TEXT NOT NULL,
                    realized_r REAL,
                    target_hit INTEGER,
                    stop_hit INTEGER,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_outcomes_signal ON outcomes(signal_id);
                CREATE INDEX IF NOT EXISTS idx_decisions_time ON decisions(event_time_utc);
                CREATE TABLE IF NOT EXISTS quarantine(
                    quarantine_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                """
            )

    def record_decision(
        self,
        intent: Mapping[str, Any],
        candidate: Mapping[str, Any],
        snapshot: Mapping[str, Any],
    ) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT OR REPLACE INTO decisions(
                    signal_id,candidate_id,candidate_hash,snapshot_id,event_time_utc,pattern,direction,
                    market_mode,regime,confidence,payload_json,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    intent["signal_id"],
                    candidate["candidate_id"],
                    candidate["candidate_hash"],
                    intent["snapshot_id"],
                    snapshot["event_time_utc"],
                    intent["pattern_type"],
                    intent["direction"],
                    intent["market_mode"],
                    str(snapshot.get("regime", {}).get("type", "UNKNOWN")),
                    float(intent["final_confidence"]),
                    canonical_json(
                        {"intent": dict(intent), "candidate": dict(candidate), "snapshot": dict(snapshot)}
                    ),
                    _utc_now(),
                ),
            )

    def quarantine(self, source_id: str, reason: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        recorded = _utc_now()
        qid = "q_" + canonical_hash({"source": source_id, "reason": reason, "payload": payload})[:24]
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO quarantine VALUES(?,?,?,?,?)",
                (qid, source_id, reason, canonical_json(payload), recorded),
            )
        return {
            "learning_eligible": False,
            "learning_rejection_reason": reason,
            "quarantine_id": qid,
        }

    def ingest_execution_report(self, report: Mapping[str, Any]) -> dict[str, Any]:
        execution_id = str(report.get("execution_id") or "")
        signal_id = str(report.get("signal_id") or "")
        source_id = execution_id or "unknown"
        if report.get("contract_version") != CONTRACT_VERSION:
            return self.quarantine(source_id, "contract_mismatch", report)
        if not execution_id or not signal_id:
            return self.quarantine(source_id, "missing_identity", report)
        if report.get("reconciled") is not True:
            return self.quarantine(execution_id, "execution_not_reconciled", report)
        supplied_integrity = str(report.get("integrity_hash") or "")
        expected_integrity = execution_report_integrity_hash(report)
        if supplied_integrity != expected_integrity:
            return self.quarantine(execution_id, "integrity_hash_mismatch", report)

        with self._connect() as db:
            row = db.execute(
                "SELECT candidate_id,candidate_hash,event_time_utc,payload_json FROM decisions WHERE signal_id=?",
                (signal_id,),
            ).fetchone()
        if row is None:
            return self.quarantine(execution_id, "signal_identity_unknown", report)
        candidate_id, candidate_hash, event_time, decision_payload = row
        decision = json.loads(decision_payload)
        intent = decision.get("intent") if isinstance(decision.get("intent"), Mapping) else {}
        reported_candidate_hash = report.get("candidate_hash")
        if reported_candidate_hash is not None and str(reported_candidate_hash) != candidate_hash:
            return self.quarantine(execution_id, "candidate_hash_mismatch", report)
        for field in ("exchange", "environment", "market_mode", "symbol"):
            if str(report.get(field) or "") != str(intent.get(field) or ""):
                return self.quarantine(execution_id, f"execution_{field}_mismatch", report)

        realized_r = report.get("realized_r")
        if realized_r is None:
            realized_r_value = None
        else:
            realized_r_value = _safe_float(realized_r)
            if realized_r_value is None:
                return self.quarantine(execution_id, "realized_r_invalid", report)
        resolved_at = str(report.get("created_at_utc") or "")
        if not resolved_at.endswith("Z"):
            return self.quarantine(execution_id, "execution_timestamp_not_utc", report)
        target_hit = int(str(report.get("take_profit_state") or "").upper() in {"HIT", "FILLED", "TRIGGERED"})
        stop_hit = int(str(report.get("stop_state") or "").upper() in {"HIT", "FILLED", "TRIGGERED"})
        with self._connect() as db:
            db.execute(
                """
                INSERT OR REPLACE INTO outcomes(
                    execution_id,signal_id,candidate_id,candidate_hash,event_time_utc,resolved_at_utc,
                    learning_eligible,rejection_reason,realized_r,target_hit,stop_hit,payload_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    execution_id,
                    signal_id,
                    candidate_id,
                    candidate_hash,
                    event_time,
                    resolved_at,
                    1,
                    "",
                    realized_r_value,
                    target_hit,
                    stop_hit,
                    canonical_json({"report": dict(report), "decision": decision}),
                ),
            )
        return {
            "learning_eligible": True,
            "learning_rejection_reason": "",
            "execution_id": execution_id,
        }

    def historical_analogues(
        self,
        *,
        candidate_time_utc: str,
        pattern: str,
        direction: str,
        market_mode: str,
        regime: str,
        min_sample: int,
        max_results: int,
        candidate_features: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        fetch_limit = max(max_results * 8, min_sample * 3, max_results)
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT d.signal_id,d.pattern,d.direction,d.market_mode,d.regime,d.confidence,d.payload_json,
                       o.realized_r,o.target_hit,o.stop_hit,o.resolved_at_utc
                FROM decisions d JOIN outcomes o ON o.signal_id=d.signal_id
                WHERE o.learning_eligible=1
                  AND d.event_time_utc < ?
                  AND o.resolved_at_utc < ?
                  AND d.pattern=? AND d.direction=? AND d.market_mode=?
                ORDER BY d.event_time_utc DESC
                LIMIT ?
                """,
                (candidate_time_utc, candidate_time_utc, pattern, direction, market_mode, fetch_limit),
            ).fetchall()

        current = dict(candidate_features or {})
        current.update(
            {
                "pattern": pattern,
                "direction": direction,
                "market_mode": market_mode,
                "regime": regime,
            }
        )
        analogues: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(row[6])
            prior_features = _decision_features(payload)
            analogue = {
                "signal_id": row[0],
                "pattern": row[1],
                "direction": row[2],
                "market_mode": row[3],
                "regime": row[4],
                "confidence": row[5],
                "realized_r": row[7],
                "target_hit": bool(row[8]),
                "stop_hit": bool(row[9]),
                "resolved_at_utc": row[10],
                "similarity": round(_similarity(current, prior_features), 6),
                "similarity_features": prior_features,
            }
            analogues.append(analogue)
        analogues.sort(key=lambda row: (-float(row["similarity"]), str(row["resolved_at_utc"])), reverse=False)
        analogues = analogues[:max_results]
        if len(analogues) < min_sample:
            return {
                "state": INSUFFICIENT_SAMPLE,
                "sample_count": len(analogues),
                "retrieval_policy_version": RETRIEVAL_POLICY_VERSION,
                "analogues": analogues,
            }
        wins = sum(1 for row in analogues if row["target_hit"])
        return {
            "state": "AVAILABLE",
            "sample_count": len(analogues),
            "retrieval_policy_version": RETRIEVAL_POLICY_VERSION,
            "empirical_target_hit_rate": wins / len(analogues),
            "analogues": analogues,
        }

    def calibration_samples(
        self,
        *,
        before_utc: str,
        max_results: int = 5_000,
    ) -> tuple[list[float], list[int]]:
        """Return only already-resolved clean past outcomes for time-aware calibration."""

        with self._connect() as db:
            rows = db.execute(
                """
                SELECT d.confidence,o.target_hit
                FROM decisions d JOIN outcomes o ON o.signal_id=d.signal_id
                WHERE o.learning_eligible=1
                  AND d.event_time_utc < ?
                  AND o.resolved_at_utc < ?
                ORDER BY d.event_time_utc DESC
                LIMIT ?
                """,
                (before_utc, before_utc, max_results),
            ).fetchall()
        return [float(row[0]) for row in rows], [1 if int(row[1]) else 0 for row in rows]

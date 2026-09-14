from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..canonical import canonical_json, primitive, utc_text
from ..models import Event, SymbolState, WatchRecord


class OrchestratorStore:
    """Crash-safe local coordination state; it does not duplicate package-owned state."""

    def __init__(self, path: str) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.path = str(target)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._create_schema()

    def _create_schema(self) -> None:
        with self._lock, self._db:
            self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS kv (
                    key TEXT PRIMARY KEY, value_json TEXT NOT NULL, updated_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS processed (
                    kind TEXT NOT NULL, identity TEXT NOT NULL, processed_at_utc TEXT NOT NULL,
                    PRIMARY KEY(kind, identity)
                );
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, priority INTEGER NOT NULL,
                    symbol TEXT NOT NULL, signal_id TEXT NOT NULL, execution_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL, payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS lineage (
                    signal_id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL, thesis_id TEXT NOT NULL,
                    execution_id TEXT NOT NULL, payload_json TEXT NOT NULL, updated_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS watches (
                    symbol TEXT PRIMARY KEY, state TEXT NOT NULL, priority REAL NOT NULL,
                    expires_at_utc TEXT, alert_id TEXT NOT NULL, updated_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS quarantine (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, reason TEXT NOT NULL,
                    identity TEXT NOT NULL, payload_json TEXT NOT NULL, created_at_utc TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY, started_at_utc TEXT NOT NULL,
                    stopped_at_utc TEXT, state TEXT NOT NULL, config_hash TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_quarantine_created ON quarantine(created_at_utc);
                """
            )

    def register_session(self, session_id: str, state: str, config_hash: str) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO sessions(session_id,started_at_utc,stopped_at_utc,state,config_hash) "
                "VALUES(?,?,?,?,?)",
                (session_id, utc_text(), None, state, config_hash),
            )

    def update_session(self, session_id: str, state: str, *, stopped: bool = False) -> None:
        with self._lock, self._db:
            self._db.execute(
                "UPDATE sessions SET state=?, stopped_at_utc=CASE WHEN ? THEN ? ELSE stopped_at_utc END "
                "WHERE session_id=?",
                (state, int(stopped), utc_text(), session_id),
            )

    def set(self, key: str, value: Any) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO kv(key,value_json,updated_at_utc) VALUES(?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at_utc=excluded.updated_at_utc",
                (key, canonical_json(value), utc_text()),
            )

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._db.execute("SELECT value_json FROM kv WHERE key=?", (key,)).fetchone()
        return default if row is None else json.loads(str(row[0]))

    def claim_once(self, kind: str, identity: str) -> bool:
        with self._lock, self._db:
            cursor = self._db.execute(
                "INSERT OR IGNORE INTO processed(kind,identity,processed_at_utc) VALUES(?,?,?)",
                (kind, identity, utc_text()),
            )
            return cursor.rowcount == 1

    def record_event(self, event: Event) -> bool:
        with self._lock, self._db:
            cursor = self._db.execute(
                "INSERT OR IGNORE INTO events(event_id,event_type,priority,symbol,signal_id,execution_id,timestamp,payload_json) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (
                    event.event_id,
                    str(event.event_type),
                    int(event.priority),
                    event.symbol,
                    event.signal_id,
                    event.execution_id,
                    event.timestamp,
                    canonical_json(event.payload),
                ),
            )
            return cursor.rowcount == 1

    def upsert_lineage(self, signal_id: str, payload: Mapping[str, Any]) -> None:
        row = primitive(payload)
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO lineage(signal_id,snapshot_id,thesis_id,execution_id,payload_json,updated_at_utc) "
                "VALUES(?,?,?,?,?,?) ON CONFLICT(signal_id) DO UPDATE SET "
                "snapshot_id=excluded.snapshot_id,thesis_id=excluded.thesis_id,execution_id=excluded.execution_id,"
                "payload_json=excluded.payload_json,updated_at_utc=excluded.updated_at_utc",
                (
                    signal_id,
                    str(row.get("snapshot_id", "")),
                    str(row.get("thesis_id", "")),
                    str(row.get("execution_id", "")),
                    canonical_json(row),
                    utc_text(),
                ),
            )

    def get_lineage(self, signal_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT payload_json FROM lineage WHERE signal_id=?", (signal_id,)
            ).fetchone()
        return None if row is None else dict(json.loads(str(row[0])))

    def active_lineage(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT payload_json FROM lineage ORDER BY updated_at_utc DESC"
            ).fetchall()
        return [dict(json.loads(str(row[0]))) for row in rows]

    def save_watch(self, watch: WatchRecord) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO watches(symbol,state,priority,expires_at_utc,alert_id,updated_at_utc) "
                "VALUES(?,?,?,?,?,?) ON CONFLICT(symbol) DO UPDATE SET state=excluded.state,"
                "priority=excluded.priority,expires_at_utc=excluded.expires_at_utc,"
                "alert_id=excluded.alert_id,updated_at_utc=excluded.updated_at_utc",
                (
                    watch.symbol,
                    str(watch.state),
                    watch.priority,
                    watch.expires_at_utc,
                    watch.alert_id,
                    watch.updated_at_utc,
                ),
            )

    def load_watches(self) -> dict[str, WatchRecord]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM watches").fetchall()
        return {
            str(row["symbol"]): WatchRecord(
                symbol=str(row["symbol"]),
                state=SymbolState(str(row["state"])),
                priority=float(row["priority"]),
                expires_at_utc=row["expires_at_utc"],
                alert_id=str(row["alert_id"]),
                updated_at_utc=str(row["updated_at_utc"]),
            )
            for row in rows
        }

    def quarantine(self, kind: str, reason: str, identity: str, payload: Any) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO quarantine(kind,reason,identity,payload_json,created_at_utc) VALUES(?,?,?,?,?)",
                (kind, reason, identity, canonical_json(payload), utc_text()),
            )

    def counts(self) -> dict[str, int]:
        with self._lock:
            return {
                table: int(self._db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                for table in ("events", "lineage", "watches", "quarantine", "processed")
            }

    def last_events(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT event_id,event_type,priority,symbol,signal_id,execution_id,timestamp,payload_json "
                "FROM events ORDER BY timestamp DESC,event_id DESC LIMIT ?",
                (max(0, limit),),
            ).fetchall()
        return [
            {
                "event_id": str(row["event_id"]),
                "event_type": str(row["event_type"]),
                "priority": int(row["priority"]),
                "symbol": str(row["symbol"]),
                "signal_id": str(row["signal_id"]),
                "execution_id": str(row["execution_id"]),
                "timestamp": str(row["timestamp"]),
                "payload": json.loads(str(row["payload_json"])),
            }
            for row in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def __enter__(self) -> OrchestratorStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

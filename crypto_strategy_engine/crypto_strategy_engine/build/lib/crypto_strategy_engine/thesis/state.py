from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from ..models import canonical_hash, dotted_get


def build_thesis_id(snapshot: Mapping[str, Any], pattern_type: str, direction: str) -> str:
    thesis_family = "BREAKOUT_CONTINUATION" if pattern_type in {"PRE_BREAKOUT", "BREAKOUT", "CONTINUATION"} else pattern_type
    identity = {
        "symbol": snapshot.get("symbol"),
        "direction": direction,
        "pattern_family": thesis_family,
        "major_structure_event": dotted_get(snapshot, "levels.major_structure_event_id"),
        "reference_level": dotted_get(snapshot, "levels.reference_level"),
        "breakout_event_identity": dotted_get(snapshot, "levels.breakout_event_id"),
    }
    return "thesis_" + canonical_hash(identity)[:24]


@dataclass(frozen=True)
class ThesisStatus:
    thesis_id: str
    attempt_no: int
    exhausted: bool
    first_seen: str
    last_seen: str
    state: str
    cooldown_until: str = ""


class ThesisStore:
    def __init__(self, db_path: str | Path) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def _init(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS thesis_state (
                    thesis_id TEXT PRIMARY KEY,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    attempt_no INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    failure_reasons TEXT NOT NULL,
                    invalidation_state TEXT NOT NULL,
                    cooldown_until TEXT NOT NULL,
                    structural_identity TEXT NOT NULL
                )
                """
            )

    def peek(self, thesis_id: str, *, max_attempts: int) -> ThesisStatus:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with self._connect() as db:
            row = db.execute(
                "SELECT first_seen,last_seen,attempt_no,state,cooldown_until FROM thesis_state WHERE thesis_id=?",
                (thesis_id,),
            ).fetchone()
        if row is None:
            return ThesisStatus(thesis_id, 0, False, now, now, "NEW", "")
        return ThesisStatus(thesis_id, int(row[2]), int(row[2]) >= max_attempts, row[0], row[1], row[3], row[4])

    def record_seen(self, thesis_id: str, structural_identity: str) -> None:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO thesis_state(
                    thesis_id,first_seen,last_seen,attempt_no,state,failure_reasons,
                    invalidation_state,cooldown_until,structural_identity
                ) VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(thesis_id) DO UPDATE SET last_seen=excluded.last_seen
                """,
                (thesis_id, now, now, 0, "ACTIVE", "[]", "VALID", "", structural_identity),
            )

    def record_attempt(self, thesis_id: str, *, cooldown_sec: int = 0) -> int:
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat().replace("+00:00", "Z")
        cooldown_until = (now_dt + timedelta(seconds=max(0, cooldown_sec))).isoformat().replace("+00:00", "Z") if cooldown_sec > 0 else ""
        with self._connect() as db:
            db.execute(
                "UPDATE thesis_state SET attempt_no=attempt_no+1,last_seen=?,state='ATTEMPTED',cooldown_until=? WHERE thesis_id=?",
                (now, cooldown_until, thesis_id),
            )
            row = db.execute("SELECT attempt_no FROM thesis_state WHERE thesis_id=?", (thesis_id,)).fetchone()
        return int(row[0]) if row else 0

    def reset_on_major_event(self, old_thesis_id: str, new_thesis_id: str, structural_identity: str) -> None:
        if old_thesis_id == new_thesis_id:
            return
        self.record_seen(new_thesis_id, structural_identity)

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    raise TypeError(type(value).__name__)


class LocalArchive:
    """Free local durable capture using SQLite; optional Parquet/DuckDB export is explicit.

    SQLite is the zero-dependency capture path so recording never silently stops if optional
    analytics dependencies are absent. `export_parquet` requires the declared `storage` extra.
    """

    TABLES = ("public_trades", "bars", "orderbook", "features", "breakout_alerts")

    def __init__(self, data_dir: Path) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = data_dir / "market_intel.sqlite3"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        for table in self.TABLES:
            self.conn.execute(f"CREATE TABLE IF NOT EXISTS {table} (id INTEGER PRIMARY KEY AUTOINCREMENT, event_time TEXT NOT NULL, symbol TEXT NOT NULL, payload TEXT NOT NULL)")
        self.conn.commit()

    def append(self, table: str, event_time: datetime, symbol: str, payload: dict[str, Any]) -> None:
        if table not in self.TABLES:
            raise ValueError(f"unknown_archive_table:{table}")
        text = json.dumps(payload, default=_json_default, sort_keys=True, separators=(",", ":"), allow_nan=False)
        event = event_time.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        self.conn.execute(f"INSERT INTO {table}(event_time,symbol,payload) VALUES(?,?,?)", (event, symbol, text))
        self.conn.commit()

    def replay(self, table: str, symbol: str | None = None) -> Iterator[dict[str, Any]]:
        if table not in self.TABLES:
            raise ValueError(f"unknown_archive_table:{table}")
        query = f"SELECT event_time,symbol,payload FROM {table}"
        params: tuple[Any, ...] = ()
        if symbol is not None:
            query += " WHERE symbol=?"; params = (symbol,)
        query += " ORDER BY event_time,id"
        for event_time, row_symbol, payload in self.conn.execute(query, params):
            yield {"event_time": event_time, "symbol": row_symbol, "payload": json.loads(payload)}

    def close(self) -> None:
        self.conn.close()

    def export_parquet(self, output_dir: Path) -> list[Path]:
        """Export recorded rows to real Parquet without any network-loaded extension."""
        try:
            import pyarrow as pa  # type: ignore[import-not-found]
            import pyarrow.parquet as pq  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("Parquet export requires: pip install crypto-market-intel[storage]") from exc
        output_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for table in self.TABLES:
            rows = [
                {"event_time": event_time, "symbol": symbol, "payload": payload}
                for event_time, symbol, payload in self.conn.execute(
                    f"SELECT event_time,symbol,payload FROM {table} ORDER BY event_time,id"
                )
            ]
            target = output_dir / f"{table}.parquet"
            schema = pa.schema([("event_time", pa.string()), ("symbol", pa.string()), ("payload", pa.string())])
            arrow_table = pa.Table.from_pylist(rows, schema=schema)
            pq.write_table(arrow_table, target, compression="zstd")
            paths.append(target)
        return paths

    def build_duckdb_catalog(self, parquet_dir: Path) -> Path:
        """Create a local DuckDB file exposing the exported Parquet tables as views."""
        try:
            import duckdb  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("DuckDB catalog requires: pip install crypto-market-intel[storage]") from exc
        db_path = parquet_dir / "market_intel.duckdb"
        con = duckdb.connect(str(db_path))
        try:
            for table in self.TABLES:
                target = (parquet_dir / f"{table}.parquet").resolve()
                if not target.exists():
                    raise RuntimeError(f"missing_parquet_for_duckdb:{target.name}")
                escaped = target.as_posix().replace("'", "''")
                con.execute(f"CREATE OR REPLACE VIEW {table} AS SELECT * FROM read_parquet('{escaped}')")
        finally:
            con.close()
        return db_path

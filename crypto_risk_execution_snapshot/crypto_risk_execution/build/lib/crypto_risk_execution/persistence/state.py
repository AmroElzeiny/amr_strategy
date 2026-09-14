from __future__ import annotations
import sqlite3, json, hashlib
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from ..canonical import canonical_json, utc_iso

class StateStore:
    def __init__(self,path:str): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self._init()
    def _connect(self):
        db=sqlite3.connect(self.path,timeout=15,isolation_level=None); db.execute('PRAGMA journal_mode=WAL'); db.execute('PRAGMA synchronous=FULL'); db.row_factory=sqlite3.Row; return db
    def _init(self):
        db=self._connect(); db.executescript("""
        CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY,v TEXT NOT NULL,updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS signals(signal_id TEXT PRIMARY KEY,state TEXT NOT NULL,execution_id TEXT,payload TEXT NOT NULL,updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reservations(id TEXT PRIMARY KEY,signal_id TEXT UNIQUE NOT NULL,symbol TEXT NOT NULL,risk TEXT NOT NULL,capital TEXT NOT NULL,state TEXT NOT NULL,updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS managed_positions(execution_id TEXT PRIMARY KEY,signal_id TEXT NOT NULL,thesis_id TEXT NOT NULL,symbol TEXT NOT NULL,qty TEXT NOT NULL,payload TEXT NOT NULL,updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS managed_orders(client_id TEXT PRIMARY KEY,execution_id TEXT NOT NULL,symbol TEXT NOT NULL,role TEXT NOT NULL,state TEXT NOT NULL,exchange_id TEXT,payload TEXT NOT NULL,updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE NOT NULL,ts TEXT NOT NULL,execution_id TEXT,signal_id TEXT,symbol TEXT,action TEXT NOT NULL,reason TEXT,state_hash TEXT NOT NULL,payload TEXT NOT NULL);
        """); db.close()
    @contextmanager
    def tx(self)->Iterator[sqlite3.Connection]:
        db=self._connect(); db.execute('BEGIN IMMEDIATE')
        try: yield db; db.execute('COMMIT')
        except Exception: db.execute('ROLLBACK'); raise
        finally: db.close()
    def get(self,k:str,default=None):
        db=self._connect(); r=db.execute('SELECT v FROM kv WHERE k=?',(k,)).fetchone(); db.close(); return default if r is None else json.loads(r['v'])
    def set(self,k:str,v:Any):
        enc=canonical_json(v)
        with self.tx() as db: db.execute('INSERT INTO kv(k,v,updated) VALUES(?,?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v,updated=excluded.updated',(k,enc,utc_iso()))
    def audit(self,action:str,*,execution_id='',signal_id='',symbol='',reason='',payload=None):
        payload=payload or {}; raw=canonical_json(payload); h=hashlib.sha256(raw.encode()).hexdigest(); eid=hashlib.sha256(f'{utc_iso()}|{action}|{signal_id}|{h}'.encode()).hexdigest()
        with self.tx() as db: db.execute('INSERT OR IGNORE INTO audit(event_id,ts,execution_id,signal_id,symbol,action,reason,state_hash,payload) VALUES(?,?,?,?,?,?,?,?,?)',(eid,utc_iso(),execution_id,signal_id,symbol,action,reason,h,raw))

"""Thin SQLite layer. The backend is the single source of truth for every
balance, document, status and action that Saarthi talks about."""
import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Iterable

from app.config import DB_PATH

_lock = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, name TEXT, phone TEXT, email TEXT, dob TEXT, pan TEXT,
  kyc_status TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS partners (
  id TEXT PRIMARY KEY, name TEXT, kind TEXT, api_style TEXT
);
CREATE TABLE IF NOT EXISTS accounts (
  id TEXT PRIMARY KEY, user_id TEXT, partner_id TEXT, bank TEXT, account_no TEXT, masked TEXT, ifsc TEXT,
  holder_name TEXT, balance REAL, status TEXT, bank_name_on_record TEXT, name_match REAL,
  journey_id TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS funds (
  id TEXT PRIMARY KEY, name TEXT, amc TEXT, category TEXT, risk TEXT, nav REAL,
  returns_1y REAL, returns_3y REAL, returns_5y REAL, min_sip REAL, expense_ratio REAL, aum_cr REAL
);
CREATE TABLE IF NOT EXISTS mandates (
  id TEXT PRIMARY KEY, user_id TEXT, account_id TEXT, umrn TEXT, max_amount REAL, status TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS sips (
  id TEXT PRIMARY KEY, user_id TEXT, fund_id TEXT, amount REAL, sip_day INTEGER, account_id TEXT,
  mandate_id TEXT, status TEXT, journey_id TEXT, installments_paid INTEGER, units REAL, invested REAL,
  next_due TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS transactions (
  id TEXT PRIMARY KEY, user_id TEXT, sip_id TEXT, kind TEXT, amount REAL, status TEXT, code TEXT,
  nav REAL, units REAL, bank_ref TEXT, ts TEXT
);
CREATE TABLE IF NOT EXISTS journeys (
  id TEXT PRIMARY KEY, user_id TEXT, category TEXT, title TEXT, subtitle TEXT,
  partner_id TEXT, partner_ref TEXT, amount REAL, status TEXT, stage TEXT,
  state_json TEXT, health_score INTEGER, created_at TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS journey_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, journey_id TEXT, ts TEXT, kind TEXT,
  title TEXT, detail TEXT, status TEXT, actor TEXT, loop_stage TEXT, meta_json TEXT
);
CREATE TABLE IF NOT EXISTS partner_responses (
  id INTEGER PRIMARY KEY AUTOINCREMENT, journey_id TEXT, partner_id TEXT,
  endpoint TEXT, request_json TEXT, raw_json TEXT, normalized_json TEXT, ts TEXT
);
CREATE TABLE IF NOT EXISTS failure_patterns (
  id TEXT PRIMARY KEY, partner_id TEXT, partner_code TEXT, failure_type TEXT,
  root_cause TEXT, occurrences INTEGER, resolved INTEGER,
  avg_resolution_s REAL, last_outcome TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, user_id TEXT, doc_type TEXT, name TEXT, status TEXT,
  source TEXT, updated_at TEXT, meta_json TEXT
);
CREATE TABLE IF NOT EXISTS journey_documents (
  journey_id TEXT, document_id TEXT, role TEXT, PRIMARY KEY (journey_id, document_id)
);
CREATE TABLE IF NOT EXISTS decisions (
  id TEXT PRIMARY KEY, journey_id TEXT, option_id TEXT, tier TEXT,
  checks_json TEXT, rationale TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS actions (
  id TEXT PRIMARY KEY, journey_id TEXT, decision_id TEXT, action_type TEXT, tier TEXT,
  status TEXT, params_json TEXT, result_json TEXT, created_at TEXT, completed_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, user_id TEXT, journey_id TEXT, actor TEXT,
  event_type TEXT, summary TEXT, data_json TEXT
);
CREATE TABLE IF NOT EXISTS knowledge_entries (
  id TEXT PRIMARY KEY, kind TEXT, partner_id TEXT, code TEXT, title TEXT,
  body TEXT, data_json TEXT
);
CREATE TABLE IF NOT EXISTS support_cases (
  id TEXT PRIMARY KEY, journey_id TEXT, created_at TEXT, priority TEXT,
  status TEXT, payload_json TEXT
);
CREATE TABLE IF NOT EXISTS partner_state (
  partner_id TEXT, ref TEXT, state_json TEXT, PRIMARY KEY (partner_id, ref)
);
CREATE TABLE IF NOT EXISTS diagnoses (
  journey_id TEXT PRIMARY KEY, payload_json TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS agent_runs (
  id TEXT PRIMARY KEY, journey_id TEXT, status TEXT, mode TEXT, model TEXT,
  trace_json TEXT, error TEXT, started_at TEXT, finished_at TEXT
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def _decode(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    out = dict(row)
    for k in list(out.keys()):
        if k.endswith("_json"):
            raw = out.pop(k)
            out[k[:-5]] = json.loads(raw) if raw else None
    return out


def query(sql: str, params: Iterable[Any] = ()) -> list[dict]:
    with _lock, connect() as conn:
        return [_decode(r) for r in conn.execute(sql, tuple(params)).fetchall()]


def query_one(sql: str, params: Iterable[Any] = ()) -> dict | None:
    with _lock, connect() as conn:
        return _decode(conn.execute(sql, tuple(params)).fetchone())


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    with _lock, connect() as conn:
        cur = conn.execute(sql, tuple(params))
        conn.commit()
        return cur.lastrowid


def insert(table: str, row: dict) -> int:
    cols, vals = [], []
    for k, v in row.items():
        if isinstance(v, (dict, list)):
            cols.append(f"{k}_json" if not k.endswith("_json") else k)
            vals.append(json.dumps(v))
        else:
            cols.append(k)
            vals.append(v)
    sql = f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"
    return execute(sql, vals)


def update(table: str, key: str, key_val: Any, changes: dict) -> None:
    sets, vals = [], []
    for k, v in changes.items():
        if isinstance(v, (dict, list)):
            sets.append(f"{k}_json = ?")
            vals.append(json.dumps(v))
        else:
            sets.append(f"{k} = ?")
            vals.append(v)
    vals.append(key_val)
    execute(f"UPDATE {table} SET {', '.join(sets)} WHERE {key} = ?", vals)


def init_schema(drop: bool = False) -> None:
    with _lock, connect() as conn:
        if drop:
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            for t in tables:
                if t != "sqlite_sequence":
                    conn.execute(f"DROP TABLE IF EXISTS {t}")
        conn.executescript(SCHEMA)
        conn.commit()

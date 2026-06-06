"""SQLite schema and connection helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    portfolio_csv TEXT NOT NULL,
    cash_balance REAL NOT NULL,
    user_goal TEXT NOT NULL,
    constraints_json TEXT NOT NULL DEFAULT '[]',
    plan_json TEXT,
    plan_status TEXT NOT NULL DEFAULT 'none',
    plan_meta_json TEXT NOT NULL DEFAULT '{}',
    prior_plan_json TEXT,
    allocation_before_json TEXT,
    last_approved_plan_json TEXT,
    cycles_json TEXT NOT NULL DEFAULT '[]',
    log_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def db_connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

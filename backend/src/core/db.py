"""SQLite storage for the demo build (ADR-0035). Single clinic, no tenant_id yet."""
import json
import sqlite3
from typing import Any

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS blocks (
  id INTEGER PRIMARY KEY,
  resource_id TEXT,              -- NULL = whole clinic (holiday)
  date TEXT NOT NULL,            -- YYYY-MM-DD
  start TEXT,                    -- HH:MM, NULL = whole day
  "end" TEXT,
  kind TEXT NOT NULL,            -- leave | holiday | late_start | early_close
  source TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bookings (
  id INTEGER PRIMARY KEY,
  resource_id TEXT NOT NULL,
  date TEXT NOT NULL,
  time TEXT NOT NULL,            -- HH:MM slot start
  status TEXT NOT NULL DEFAULT 'booked',   -- booked | arrived | no_show | done | cancelled
  source TEXT NOT NULL,          -- phone | whatsapp | walk_in
  name TEXT NOT NULL,
  phone TEXT,
  reason TEXT,
  call_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
-- The double-booking lock: the database refuses a second active booking for the same slot.
CREATE UNIQUE INDEX IF NOT EXISTS bookings_slot_lock
  ON bookings (resource_id, date, time) WHERE status NOT IN ('cancelled', 'no_show');
CREATE INDEX IF NOT EXISTS bookings_date ON bookings (date);
CREATE TABLE IF NOT EXISTS inbox (
  id INTEGER PRIMARY KEY,
  kind TEXT NOT NULL,            -- escalation | callback | ops
  urgent INTEGER NOT NULL DEFAULT 0,
  name TEXT,
  phone TEXT,
  reason TEXT,
  note TEXT,
  call_id TEXT,
  created_at TEXT NOT NULL,
  done_at TEXT
);
CREATE TABLE IF NOT EXISTS calls (
  id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  booked INTEGER NOT NULL DEFAULT 0,
  changed INTEGER NOT NULL DEFAULT 0,
  escalated INTEGER NOT NULL DEFAULT 0,
  callback INTEGER NOT NULL DEFAULT 0,
  outcome TEXT,
  ended_reason TEXT,
  summary TEXT,
  transcript TEXT,
  recording_url TEXT,
  safety_review INTEGER NOT NULL DEFAULT 0,
  safety_hits TEXT
);
-- Tool results by Vapi toolCallId, so a retried tool call returns the first result (idempotent writes).
CREATE TABLE IF NOT EXISTS tool_calls (
  id TEXT PRIMARY KEY,
  result TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pending_actions (
  sender TEXT PRIMARY KEY,
  action TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    path = config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def stamp() -> str:
    return config.now().isoformat(timespec="seconds")


def get_json(conn: sqlite3.Connection, key: str) -> Any:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value"]) if row else None


def put_json(conn: sqlite3.Connection, key: str, value: Any) -> None:
    with conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value, ensure_ascii=False)),
        )

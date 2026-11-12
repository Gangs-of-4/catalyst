"""One thin SQL layer for SQLite (local, tests) and Postgres (`DATABASE_URL`, production). ADR-0039.

Code writes SQLite-style SQL with `?` placeholders in the subset both databases share. Rows support
`row["col"]`, `row[0]` and `dict(row)` on both. A unique-key clash raises `Conflict` on both.

Tenant isolation (contracts.md §3.1): a connection is scoped to one business with `for_tenant(id)`,
and `conn.tid` is that business's id. Every query that touches a tenant table must filter by
`tenant_id`, or `execute` refuses it with `ScopeError` before it reaches the database.
"""

import json
import re
import sqlite3
from typing import Any

from . import config
from .config import env
from .log import log

# Tables that hold one business's data. Every query on them must mention tenant_id.
TENANT_TABLES = {
    "blocks",
    "bookings",
    "inbox",
    "calls",
    "tool_calls",
    "pending_actions",
    "users",
    "sessions",
    "products",
    "orders",
    "order_items",
    "instruction_versions",
    "events",
    "feedback",
}
_COMMENTS = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)
_LITERALS = re.compile(r"'(?:[^']|'')*'")
_FILTER = re.compile(r"\btenant_id\b\s*=\s*(?:\?|[a-z_]+\.[a-z_]+|[a-z_]+\b)")
_INSERT_COLS = re.compile(r"\binsert\s+into\s+\S+\s*\([^)]*\btenant_id\b")

SCHEMA_VERSION = 1
# {ID} becomes an auto-increment integer primary key in each dialect.
SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS tenants (
  id TEXT PRIMARY KEY,
  public_id TEXT NOT NULL UNIQUE,     -- random URL slug, demo businesses use demo-<template>
  template TEXT NOT NULL,             -- folder under verticals/
  name TEXT NOT NULL,
  settings TEXT NOT NULL,             -- JSON: hours, resources, services, FAQs, address, …
  owner_whatsapp TEXT UNIQUE,         -- E.164; routes WhatsApp messages to this business
  vapi_assistant_id TEXT,
  tool_secret TEXT,
  is_demo INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
-- Every WhatsApp number a business commands from (owner + settings.whatsapp_numbers),
-- normalised; UNIQUE so one business can't claim another's number. A lookup index like
-- tenants.owner_whatsapp, rebuilt from settings on every save and at startup.
CREATE TABLE IF NOT EXISTS tenant_whatsapp_numbers (
  number TEXT PRIMARY KEY,       -- E.164
  tenant_id TEXT NOT NULL REFERENCES tenants(id)
);
CREATE INDEX IF NOT EXISTS tenant_whatsapp_numbers_tenant ON tenant_whatsapp_numbers (tenant_id);
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,         -- lowercased
  password_hash TEXT NOT NULL,        -- scrypt$n$r$p$salt$hash, never the password
  failed_logins INTEGER NOT NULL DEFAULT 0,
  locked_until TEXT,
  last_active_at TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS users_tenant ON users (tenant_id);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,        -- SHA-256 of the cookie token; the token itself is never stored
  user_id TEXT,                       -- NULL for admin
  tenant_id TEXT REFERENCES tenants(id),   -- NULL for admin
  kind TEXT NOT NULL,                 -- user | admin
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions (user_id);
CREATE TABLE IF NOT EXISTS blocks (
  id {ID},
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  resource_id TEXT,              -- NULL = whole business (holiday)
  date TEXT NOT NULL,            -- YYYY-MM-DD
  start TEXT,                    -- HH:MM, NULL = whole day
  "end" TEXT,
  kind TEXT NOT NULL,            -- leave | holiday | late_start | early_close
  source TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS blocks_tenant_date ON blocks (tenant_id, date);
CREATE TABLE IF NOT EXISTS bookings (
  id {ID},
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
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
  ON bookings (tenant_id, resource_id, date, time) WHERE status NOT IN ('cancelled', 'no_show');
CREATE INDEX IF NOT EXISTS bookings_tenant_date ON bookings (tenant_id, date);
CREATE TABLE IF NOT EXISTS inbox (
  id {ID},
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
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
CREATE INDEX IF NOT EXISTS inbox_tenant_open ON inbox (tenant_id, done_at);
-- Wholesale (orders module, contracts.md section 3.1). Money is integer paise.
CREATE TABLE IF NOT EXISTS products (
  id {ID},
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  name TEXT NOT NULL,
  name_key TEXT NOT NULL,        -- lowercased, punctuation folded: one product per name
  pack_size TEXT NOT NULL DEFAULT '',
  rate_paise INTEGER NOT NULL,
  in_stock INTEGER NOT NULL DEFAULT 1,
  active INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS products_name ON products (tenant_id, name_key);
CREATE TABLE IF NOT EXISTS orders (
  id {ID},
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  number INTEGER NOT NULL,       -- per-business counter: "order 42"
  shop_name TEXT NOT NULL,
  contact_name TEXT,
  phone TEXT,
  notes TEXT,
  status TEXT NOT NULL DEFAULT 'new',  -- new | confirmed | dispatched | delivered | cancelled
  source TEXT NOT NULL,          -- phone | whatsapp | walk_in
  call_id TEXT,
  idempotency_key TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS orders_number ON orders (tenant_id, number);
CREATE UNIQUE INDEX IF NOT EXISTS orders_idempotency
  ON orders (tenant_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS orders_tenant_created ON orders (tenant_id, created_at);
CREATE TABLE IF NOT EXISTS order_items (
  id {ID},
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  order_id INTEGER NOT NULL REFERENCES orders(id),
  product_id INTEGER REFERENCES products(id),
  name TEXT NOT NULL,            -- copied at order time: a later catalogue edit never changes an order
  pack_size TEXT NOT NULL DEFAULT '',
  qty INTEGER NOT NULL,
  rate_paise INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS order_items_order ON order_items (tenant_id, order_id);
-- In-app feedback (Phase 2 M7; contracts.md section 3.1). The team's feedback log.
CREATE TABLE IF NOT EXISTS feedback (
  id {ID},
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  person_name TEXT NOT NULL,
  person_role TEXT NOT NULL,
  text TEXT NOT NULL,
  type TEXT NOT NULL,            -- bug | feature | usability | data_integration | pricing_business
  decision TEXT,                 -- shipped | in_progress | planned | wont_do
  decision_reason TEXT,
  shipped_on TEXT,
  evidence_url TEXT,
  partner_reaction TEXT,
  created_at TEXT NOT NULL
);
-- Usage evidence (contracts.md section 3.1). No payload column, so counts never carry names or numbers.
CREATE TABLE IF NOT EXISTS events (
  id {ID},
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  user_id TEXT,
  type TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_type_time ON events (type, created_at);
CREATE TABLE IF NOT EXISTS calls (
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  id TEXT NOT NULL,
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
  safety_hits TEXT,
  PRIMARY KEY (tenant_id, id)
);
-- Tool results by Vapi toolCallId, so a retried tool call returns the first result (idempotent writes).
CREATE TABLE IF NOT EXISTS tool_calls (
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  id TEXT NOT NULL,
  result TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (tenant_id, id)
);
CREATE TABLE IF NOT EXISTS pending_actions (
  tenant_id TEXT NOT NULL REFERENCES tenants(id),
  sender TEXT NOT NULL,
  action TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (tenant_id, sender)
)
"""

_ID = {
    "sqlite": "INTEGER PRIMARY KEY",
    "postgres": "BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY",
}


class Conflict(Exception):
    """A unique key or the slot lock refused the write, on either database."""


class ScopeError(Exception):
    """A query on a tenant table without a tenant filter, or a tenant needed but not set."""


class Row:
    """Postgres rows that behave like sqlite3.Row: row["col"], row[0], dict(row), iteration."""

    __slots__ = ("_keys", "_values")

    def __init__(self, keys: list[str], values: tuple):
        self._keys, self._values = keys, values

    def keys(self) -> list[str]:
        return self._keys

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return self._values[self._keys.index(key)]

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


def _pg_row_factory(cursor):
    keys = [c.name for c in cursor.description or []]
    return lambda values: Row(keys, values)


def _bare(sql: str) -> str:
    """The SQL without comments and string literals, so a word inside them can't fake a filter."""
    return _LITERALS.sub("''", _COMMENTS.sub(" ", sql)).lower().replace('"', "")


def tenant_tables_in(sql: str) -> list[str]:
    """Tenant tables the statement mentions in any form: plain, quoted, schema-qualified, joined,
    comma-joined or in a subquery. One entry per mention."""
    return [w for w in re.findall(r"[a-z_]+", _bare(sql)) if w in TENANT_TABLES]


def check_scope(sql: str) -> None:
    """Refuse a statement on tenant tables unless it filters each one by tenant_id.

    A statement mentioning N tenant tables needs N `tenant_id = ?` (or `a.tenant_id = b.tenant_id`
    join) conditions. An INSERT needs tenant_id in its column list. This catches a forgotten
    filter; it can't prove the filter is the right one, so tests still check isolation.
    """
    bare = _bare(sql)
    tables = tenant_tables_in(sql)
    if not tables:
        return
    if bare.lstrip().startswith("insert"):
        ok = bool(_INSERT_COLS.search(bare))
    else:
        ok = len(_FILTER.findall(bare)) >= len(tables)
    if not ok:
        raise ScopeError(f"query on {sorted(set(tables))} without a tenant_id filter")


class Conn:
    """A connection to either database, optionally scoped to one tenant."""

    def __init__(self, raw: Any, dialect: str, tid: str | None = None, checked: bool = True):
        self.raw, self.dialect, self._tid, self.checked = raw, dialect, tid, checked

    @property
    def tid(self) -> str:
        if not self._tid:
            raise ScopeError("this connection is not scoped to a business")
        return self._tid

    def for_tenant(self, tid: str) -> "Conn":
        """The same connection, scoped to one business."""
        return Conn(self.raw, self.dialect, tid, self.checked)

    def execute(self, sql: str, params: tuple | list = ()):
        if self.checked and tenant_tables_in(sql):
            check_scope(sql)
            if self.tid not in tuple(params):
                raise ScopeError("query on tenant tables doesn't pass this business's tenant id")
        if self.dialect == "sqlite":
            try:
                return self.raw.execute(sql, params)
            except sqlite3.IntegrityError as e:
                if "UNIQUE" in str(e) or "PRIMARY KEY" in str(e):
                    raise Conflict(str(e)) from e
                raise
        import psycopg

        try:
            return self.raw.execute(sql.replace("%", "%%").replace("?", "%s"), tuple(params))
        except psycopg.errors.UniqueViolation as e:
            raise Conflict(str(e)) from e

    def commit(self) -> None:
        self.raw.commit()

    def rollback(self) -> None:
        self.raw.rollback()

    def close(self) -> None:
        self.raw.close()

    def __enter__(self) -> "Conn":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.raw.commit()
        else:
            self.raw.rollback()


def dialect() -> str:
    return "postgres" if env("DATABASE_URL") else "sqlite"


def _connect_raw() -> tuple[Any, str]:
    url = env("DATABASE_URL")
    if url:
        import psycopg

        # prepare_threshold=None: no server-side prepared statements, so Neon's pooled
        # (PgBouncer transaction-mode) endpoint works too.
        raw = psycopg.connect(
            url, row_factory=_pg_row_factory, prepare_threshold=None, connect_timeout=15
        )
        return raw, "postgres"
    path = config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _move_legacy_demo_db(path)
    conn = sqlite3.connect(path, timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn, "sqlite"


def connect() -> Conn:
    """A connection with the tenant-scope check on. Scope it with `.for_tenant(id)`."""
    raw, kind = _connect_raw()
    return Conn(raw, kind)


def connect_unchecked() -> Conn:
    """No tenant-scope check. Only for tests that inspect raw state and for cross-business admin counts."""
    raw, kind = _connect_raw()
    return Conn(raw, kind, checked=False)


_LEGACY_CHECKED: set[str] = set()  # DB files already checked in this process
_CARRIED_SETTINGS: dict[str, dict] = {}  # old demo settings, handed to seed.ensure once


def _move_legacy_demo_db(path) -> None:
    """The single-clinic demo DB (no tenant_id) can't be upgraded in place. Move it aside to
    `<name>.legacy`, keep its settings (doctors, fees, WhatsApp numbers from /setup) for the new
    demo clinic, and say so loudly. Checked once per process. If another program (usually the old
    server) has the file open, fail with a plain message instead of a raw PermissionError."""
    key = str(path)
    if key in _LEGACY_CHECKED:
        return
    if path.exists():
        probe = sqlite3.connect(path)
        try:
            cols = [r[1] for r in probe.execute("PRAGMA table_info(bookings)")]
            row = None
            if cols and "tenant_id" not in cols:
                try:
                    row = probe.execute(
                        "SELECT value FROM settings WHERE key = 'clinic'"
                    ).fetchone()
                except sqlite3.Error:
                    row = None
        finally:
            probe.close()
        if cols and "tenant_id" not in cols:
            try:
                for suffix in ("", "-wal", "-shm"):  # the main file first: it fails fast if in use
                    old = path.with_name(path.name + suffix)
                    if old.exists():
                        old.replace(old.with_name(old.name + ".legacy"))
            except OSError as e:
                raise RuntimeError(
                    f"The old demo database {path} is open in another program (probably the old"
                    " server). Stop it, then start again. The file is upgraded automatically."
                ) from e
            if row:
                _CARRIED_SETTINGS[key] = json.loads(row[0])
            log.warning(
                "db: moved the old single-clinic demo database to %s.legacy; its settings carry over",
                path.name,
            )
    _LEGACY_CHECKED.add(key)


def take_carried_settings() -> dict | None:
    """Settings of the old single-clinic demo, once, if its database was just moved aside."""
    return _CARRIED_SETTINGS.pop(str(config.db_path()), None)


def init(conn: Conn) -> None:
    ddl = re.sub(r"--[^\n]*", "", SCHEMA.replace("{ID}", _ID[conn.dialect]))
    for statement in ddl.split(";"):
        if statement.strip():
            conn.raw.execute(statement)
    if conn.raw.execute("SELECT version FROM schema_version").fetchone() is None:
        conn.raw.execute(f"INSERT INTO schema_version (version) VALUES ({SCHEMA_VERSION})")
    conn.commit()


def stamp() -> str:
    return config.now().isoformat(timespec="seconds")


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)

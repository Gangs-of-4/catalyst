"""The tenant-scope guard and the upgrade of an old single-clinic demo database (ADR-0039)."""

import json
import os
import pathlib
import sqlite3

import pytest

from src import seed
from src.core import config, db
from src.core import settings as cs

# Statements that must be refused: tenant data without a real tenant filter.
BYPASSES = {
    "no filter": "SELECT * FROM bookings WHERE id = ?",
    "word only in a comment": "SELECT * FROM bookings WHERE id = ? -- tenant_id = ?",
    "word only in a block comment": "SELECT * FROM bookings /* tenant_id = ? */ WHERE id = ?",
    "column listed, not filtered": "SELECT tenant_id, name FROM bookings WHERE id = ?",
    "word only in a string": "SELECT * FROM bookings WHERE note = 'tenant_id = x' AND id = ?",
    "quoted table": 'SELECT * FROM "bookings" WHERE id = ?',
    "schema-qualified table": "SELECT * FROM public.bookings WHERE id = ?",
    "comma join": "SELECT * FROM tenants t, bookings b WHERE t.id = ?",
    "second table unfiltered": (
        "SELECT * FROM orders o JOIN order_items i ON i.order_id = o.id "
        "WHERE o.tenant_id = ?"
    ),
    "subquery unfiltered": (
        "SELECT * FROM bookings WHERE tenant_id = ? "
        "AND id IN (SELECT id FROM inbox)"
    ),
    "insert without tenant column": "INSERT INTO inbox (kind, created_at) VALUES (?, ?)",
    "delete without filter": "DELETE FROM blocks WHERE id = ?",
    "update without filter": "UPDATE inbox SET done_at = ? WHERE id = ?",
}

# Statements the app really uses; the guard must let these through.
ALLOWED = {
    "select": "SELECT * FROM bookings WHERE tenant_id = ? AND date = ?",
    "uppercase and spacing": "select *\nFROM   bookings\nWHERE  TENANT_ID=? and id = ?",
    "join filtered on both": (
        "SELECT * FROM orders o JOIN order_items i ON i.order_id = o.id"
        " AND i.tenant_id = o.tenant_id WHERE o.tenant_id = ?"
    ),
    "insert": "INSERT INTO inbox (tenant_id, kind, created_at) VALUES (?, ?, ?) RETURNING id",
    "upsert": (
        "INSERT INTO pending_actions (tenant_id, sender, action, created_at) VALUES (?, ?, ?, ?)"
        " ON CONFLICT (tenant_id, sender) DO UPDATE SET action = excluded.action"
    ),
    "update": "UPDATE inbox SET done_at = ? WHERE tenant_id = ? AND id = ?",
    "not a tenant table": "SELECT * FROM tenants WHERE public_id = ?",
    "tenant word in a string only": "SELECT * FROM tenants WHERE name = 'bookings'",
}


@pytest.mark.parametrize("sql", BYPASSES.values(), ids=BYPASSES.keys())
def test_guard_refuses_bypass(sql):
    with pytest.raises(db.ScopeError):
        db.check_scope(sql)


@pytest.mark.parametrize("sql", ALLOWED.values(), ids=ALLOWED.keys())
def test_guard_allows_scoped_statements(sql):
    db.check_scope(sql)


def test_scoped_connection_must_pass_its_own_tenant_id(conn):
    with pytest.raises(db.ScopeError):
        conn.execute("SELECT * FROM bookings WHERE tenant_id = ?", ("someone-elses-id",))
    conn.execute("SELECT * FROM bookings WHERE tenant_id = ?", (conn.tid,))


def test_unscoped_connection_can_not_query_tenant_tables():
    c = db.connect()
    try:
        with pytest.raises(db.ScopeError):
            c.execute("SELECT * FROM bookings WHERE tenant_id = ?", ("x",))
    finally:
        c.close()


# ---------- upgrading the old single-clinic demo database ----------

# These work on SQLite files, so the Postgres CI run skips them.
sqlite_only = pytest.mark.skipif(
    bool(os.environ.get("TEST_DATABASE_URL")), reason="SQLite file upgrade"
)


@pytest.fixture
def old_db(tmp_path, monkeypatch):
    """An old-format SQLite file (no tenant_id) with settings a teammate saved on /setup."""
    path = tmp_path / "old.db"
    monkeypatch.setenv("CATALYST_DB", str(path))
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    old.execute(
        "INSERT INTO settings VALUES ('clinic', ?)",
        (json.dumps({"whatsapp_numbers": ["+919000000099"], "name": "Edited Clinic"}),),
    )
    old.execute("CREATE TABLE bookings (id INTEGER PRIMARY KEY, name TEXT)")
    old.commit()
    old.close()
    return path


@sqlite_only
def test_old_database_is_moved_aside_and_its_settings_carry_over(old_db):
    c = db.connect()
    c = c.for_tenant(seed.ensure(c, with_demo_data=False))
    try:
        assert old_db.with_name("old.db.legacy").exists()
        s = cs.load(c)
        assert s["whatsapp_numbers"] == ["+919000000099"] and s["name"] == "Edited Clinic"
        assert s["doctors"], "settings the old file lacked still get defaults"
    finally:
        c.close()


@sqlite_only
def test_carried_settings_are_used_once(old_db):
    db.connect().close()
    assert db.take_carried_settings() is not None
    assert db.take_carried_settings() is None


@sqlite_only
def test_database_in_use_by_another_program_gives_a_plain_error(old_db, monkeypatch):
    def locked(self, target):
        raise PermissionError(32, "The process cannot access the file")

    monkeypatch.setattr(pathlib.Path, "replace", locked)
    with pytest.raises(RuntimeError, match="open in another program"):
        db.connect()
    assert old_db.exists(), "nothing was moved"


@sqlite_only
def test_current_database_is_left_alone(tmp_path):
    c = db.connect()
    seed.ensure(c, with_demo_data=False)
    c.close()
    assert not list(config.db_path().parent.glob("*.legacy"))
    db.connect().close()  # connecting again doesn't trigger the upgrade check

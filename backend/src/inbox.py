"""Receptionist inbox: urgent escalations, callbacks and ops items (C7)."""
import sqlite3

from .core import db

KINDS = ("escalation", "callback", "ops")


def create(conn: sqlite3.Connection, kind: str, *, urgent: bool = False, name: str | None = None,
           phone: str | None = None, reason: str | None = None, note: str | None = None,
           call_id: str | None = None) -> int:
    assert kind in KINDS
    with conn:
        cur = conn.execute(
            "INSERT INTO inbox (kind, urgent, name, phone, reason, note, call_id, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (kind, int(urgent), name, phone, reason, (note or "")[:500] or None, call_id, db.stamp()),
        )
    return cur.lastrowid


def open_items(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM inbox WHERE done_at IS NULL ORDER BY urgent DESC, kind = 'escalation' DESC, created_at"
    ).fetchall()
    return [dict(r) for r in rows]


def mark_done(conn: sqlite3.Connection, item_id: int) -> bool:
    with conn:
        cur = conn.execute("UPDATE inbox SET done_at = ? WHERE id = ? AND done_at IS NULL", (db.stamp(), item_id))
    return cur.rowcount == 1

"""Businesses (tenants): create and look up. Every tenant-table query goes through a connection
scoped with `db.Conn.for_tenant` (contracts.md §3.1, ADR-0039)."""

import json
import secrets
import uuid

from . import db
from .config import REPO_ROOT

VERTICALS_DIR = REPO_ROOT / "verticals"
DEMO_PUBLIC_ID = "demo-{template}"


def templates() -> list[str]:
    return sorted(
        p.name
        for p in VERTICALS_DIR.iterdir()
        if p.is_dir() and not p.name.startswith("_") and (p / "vertical.yaml").exists()
    )


def create(
    conn: db.Conn,
    template: str,
    settings: dict,
    *,
    owner_whatsapp: str | None = None,
    public_id: str | None = None,
    is_demo: bool = False,
) -> str:
    """Insert a business and return its id. Raises db.Conflict if public_id or WhatsApp is taken."""
    if template not in templates():
        raise ValueError(f"Unknown template {template!r}")
    tid = str(uuid.uuid4())
    with conn:
        conn.execute(
            "INSERT INTO tenants (id, public_id, template, name, settings, owner_whatsapp,"
            " tool_secret, is_demo, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tid,
                public_id or secrets.token_urlsafe(6).lower().replace("_", "x").replace("-", "y"),
                template,
                settings["name"],
                db.dumps(settings),
                owner_whatsapp,
                secrets.token_urlsafe(24),
                int(is_demo),
                db.stamp(),
            ),
        )
    return tid


def get(conn: db.Conn, tid: str) -> db.Row | None:
    return conn.execute("SELECT * FROM tenants WHERE id = ?", (tid,)).fetchone()


def by_public_id(conn: db.Conn, public_id: str) -> db.Row | None:
    return conn.execute("SELECT * FROM tenants WHERE public_id = ?", (public_id,)).fetchone()


def by_whatsapp(conn: db.Conn, e164: str) -> db.Row | None:
    return conn.execute("SELECT * FROM tenants WHERE owner_whatsapp = ?", (e164,)).fetchone()


def demo_id(conn: db.Conn, template: str = "clinic") -> str | None:
    row = by_public_id(conn, DEMO_PUBLIC_ID.format(template=template))
    return row["id"] if row else None


def set_assistant(conn: db.Conn, assistant_id: str) -> None:
    with conn:
        conn.execute(
            "UPDATE tenants SET vapi_assistant_id = ? WHERE id = ?", (assistant_id, conn.tid)
        )


def delete(conn: db.Conn, tid: str) -> None:
    """Remove a business whose signup never finished, with any owner and session made for it."""
    scoped = conn.for_tenant(tid)
    with conn:
        scoped.execute("DELETE FROM sessions WHERE tenant_id = ?", (tid,))
        scoped.execute("DELETE FROM users WHERE tenant_id = ?", (tid,))
        conn.execute("DELETE FROM tenants WHERE id = ?", (tid,))


def load_settings(conn: db.Conn) -> dict:
    row = conn.execute("SELECT settings FROM tenants WHERE id = ?", (conn.tid,)).fetchone()
    if row is None:
        raise db.ScopeError("business not found")
    return json.loads(row["settings"])


def save_settings(conn: db.Conn, s: dict) -> None:
    with conn:
        conn.execute(
            "UPDATE tenants SET settings = ?, name = ? WHERE id = ?",
            (db.dumps(s), s["name"], conn.tid),
        )

"""Businesses (tenants): create and look up. Every tenant-table query goes through a connection
scoped with `db.Conn.for_tenant` (contracts.md §3.1, ADR-0039)."""

import json
import secrets
import uuid

from . import db
from . import phone as ph
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
        _index_numbers(conn, tid, settings, owner_whatsapp)
    return tid


def whatsapp_numbers(settings: dict, owner_whatsapp: str | None) -> list[str]:
    """Every number this business takes commands from, normalised (E.164), owner first."""
    raw = [owner_whatsapp, *(settings.get("whatsapp_numbers") or [])]
    out: list[str] = []
    for n in (ph.normalize(x) for x in raw if x):
        if n and n not in out:
            out.append(n)
    return out


def _index_numbers(conn: db.Conn, tid: str, settings: dict, owner_whatsapp: str | None) -> None:
    """Inside the caller's transaction. Raises db.Conflict if another business has a number."""
    conn.execute("DELETE FROM tenant_whatsapp_numbers WHERE tenant_id = ?", (tid,))
    for n in whatsapp_numbers(settings, owner_whatsapp):
        conn.execute(
            "INSERT INTO tenant_whatsapp_numbers (number, tenant_id) VALUES (?, ?)", (n, tid)
        )


def reindex_whatsapp(conn: db.Conn) -> None:
    """Rebuild the number index from every business's settings (startup; older databases).
    Two passes: every business's *own* owner number first (owner numbers are unique), then the
    listed numbers nobody owns, older businesses first. So a number always goes to the business
    whose owner number it is, even if an older business also lists it."""
    rows = conn.execute(
        "SELECT id, settings, owner_whatsapp FROM tenants ORDER BY created_at, id"
    ).fetchall()
    with conn:
        conn.execute("DELETE FROM tenant_whatsapp_numbers")
        taken: set[str] = set()

        def claim(number: str, tid: str) -> None:
            if number not in taken:
                taken.add(number)
                conn.execute(
                    "INSERT INTO tenant_whatsapp_numbers (number, tenant_id) VALUES (?, ?)",
                    (number, tid),
                )

        for r in rows:
            owner = ph.normalize(r["owner_whatsapp"]) if r["owner_whatsapp"] else None
            if owner:
                claim(owner, r["id"])
        for r in rows:
            for n in whatsapp_numbers(json.loads(r["settings"]), None):
                claim(n, r["id"])


def get(conn: db.Conn, tid: str) -> db.Row | None:
    return conn.execute("SELECT * FROM tenants WHERE id = ?", (tid,)).fetchone()


def by_public_id(conn: db.Conn, public_id: str) -> db.Row | None:
    return conn.execute("SELECT * FROM tenants WHERE public_id = ?", (public_id,)).fetchone()


def by_whatsapp(conn: db.Conn, e164: str) -> db.Row | None:
    return conn.execute("SELECT * FROM tenants WHERE owner_whatsapp = ?", (e164,)).fetchone()


def for_sender(conn: db.Conn, e164: str) -> str | None:
    """The business a WhatsApp number commands (contracts.md §4): its owner number or one of its
    listed numbers. Numbers are unique across businesses (tenant_whatsapp_numbers), so the answer
    is never ambiguous and one business can't claim another's number."""
    row = conn.execute(
        "SELECT tenant_id FROM tenant_whatsapp_numbers WHERE number = ?", (ph.normalize(e164),)
    ).fetchone()
    return row["tenant_id"] if row else None


def number_taken(conn: db.Conn, e164: str, tid: str | None = None) -> bool:
    """True if another business already commands from this number."""
    row = conn.execute(
        "SELECT tenant_id FROM tenant_whatsapp_numbers WHERE number = ?", (ph.normalize(e164),)
    ).fetchone()
    return row is not None and row["tenant_id"] != tid


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
        scoped.execute("DELETE FROM instruction_versions WHERE tenant_id = ?", (tid,))
        scoped.execute("DELETE FROM events WHERE tenant_id = ?", (tid,))
        scoped.execute("DELETE FROM sessions WHERE tenant_id = ?", (tid,))
        conn.execute("DELETE FROM tenant_whatsapp_numbers WHERE tenant_id = ?", (tid,))
        scoped.execute("DELETE FROM users WHERE tenant_id = ?", (tid,))
        conn.execute("DELETE FROM tenants WHERE id = ?", (tid,))


def load_settings(conn: db.Conn) -> dict:
    row = conn.execute("SELECT settings FROM tenants WHERE id = ?", (conn.tid,)).fetchone()
    if row is None:
        raise db.ScopeError("business not found")
    return json.loads(row["settings"])


def save_settings(conn: db.Conn, s: dict) -> None:
    """Raises db.Conflict (nothing saved) if a WhatsApp number belongs to another business."""
    with conn:
        conn.execute(
            "UPDATE tenants SET settings = ?, name = ? WHERE id = ?",
            (db.dumps(s), s["name"], conn.tid),
        )
        owner = conn.execute(
            "SELECT owner_whatsapp FROM tenants WHERE id = ?", (conn.tid,)
        ).fetchone()
        _index_numbers(conn, conn.tid, s, owner["owner_whatsapp"] if owner else None)

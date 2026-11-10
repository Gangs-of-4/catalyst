"""Receptionist inbox: urgent escalations, callbacks and ops items (C7)."""


from .core import db

KINDS = ("escalation", "callback", "ops")


def create(
    conn: db.Conn,
    kind: str,
    *,
    urgent: bool = False,
    name: str | None = None,
    phone: str | None = None,
    reason: str | None = None,
    note: str | None = None,
    call_id: str | None = None,
) -> int:
    assert kind in KINDS
    with conn:
        row = conn.execute(
            "INSERT INTO inbox (tenant_id, kind, urgent, name, phone, reason, note, call_id,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
            (
                conn.tid,
                kind,
                int(urgent),
                name,
                phone,
                reason,
                (note or "")[:500] or None,
                call_id,
                db.stamp(),
            ),
        ).fetchone()
    return row["id"]


def open_items(conn: db.Conn) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM inbox WHERE tenant_id = ? AND done_at IS NULL"
        " ORDER BY urgent DESC, CASE WHEN kind = 'escalation' THEN 0 ELSE 1 END, created_at",
        (conn.tid,),
    ).fetchall()
    return [dict(r) for r in rows]


def mark_done(conn: db.Conn, item_id: int) -> bool:
    with conn:
        cur = conn.execute(
            "UPDATE inbox SET done_at = ? WHERE tenant_id = ? AND id = ? AND done_at IS NULL",
            (db.stamp(), conn.tid, item_id),
        )
    return cur.rowcount == 1

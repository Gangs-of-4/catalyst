"""First-run setup: schema, the public demo clinic and a few fictional bookings so screens aren't empty."""

from datetime import timedelta

from .booking import service
from .core import config, db, tenancy
from .verticals import loader


def ensure(conn: db.Conn, with_demo_data: bool = True) -> str:
    """Create the schema and the demo clinic if missing. Returns the demo clinic's id."""
    db.init(conn)
    existing = tenancy.demo_id(conn, "clinic")
    if existing:
        return existing
    s = loader.default_settings()
    tid = tenancy.create(
        conn, "clinic", s, public_id=tenancy.DEMO_PUBLIC_ID.format(template="clinic"), is_demo=True
    )
    if with_demo_data:
        _demo_data(conn.for_tenant(tid), s)
    return tid


def _demo_data(conn: db.Conn, s: dict) -> None:
    seed = loader.load_yaml("demo-tenant.yaml").get("seed", {})
    today = config.now().date()
    open_days = [today]
    d = today
    while len(open_days) < 2:
        d += timedelta(days=1)
        if not service.is_closed(s, d):
            open_days.append(d)
    ts = db.stamp()
    with conn:
        for b in seed.get("bookings", []):
            # Direct insert: seed rows may sit in the past today, which `book` rightly refuses.
            conn.execute(
                "INSERT INTO bookings (tenant_id, resource_id, date, time, status, source, name,"
                " phone, reason, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 'booked', ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
                (
                    conn.tid,
                    b["doctor"],
                    open_days[b["day"]].isoformat(),
                    b["time"],
                    b.get("source", "phone"),
                    b["name"],
                    b["phone"],
                    b.get("reason"),
                    ts,
                    ts,
                ),
            )
        for c in seed.get("callbacks", []):
            conn.execute(
                "INSERT INTO inbox (tenant_id, kind, urgent, name, phone, reason, note, created_at)"
                " VALUES (?, 'callback', 0, ?, ?, ?, ?, ?)",
                (conn.tid, c["name"], c["phone"], c["reason"], c.get("note"), ts),
            )

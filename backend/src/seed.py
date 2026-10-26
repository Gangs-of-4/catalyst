"""First-run setup: schema, default settings and a few fictional bookings so screens aren't empty."""
import sqlite3
from datetime import timedelta

from .booking import service
from .core import config, db
from .core import settings as cs
from .verticals import loader


def ensure(conn: sqlite3.Connection, with_demo_data: bool = True) -> None:
    db.init(conn)
    if db.get_json(conn, cs.KEY) is not None:
        return
    s = loader.default_settings()
    cs.save(conn, s)
    if with_demo_data:
        _demo_data(conn, s)


def _demo_data(conn: sqlite3.Connection, s: dict) -> None:
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
                "INSERT OR IGNORE INTO bookings (resource_id, date, time, status, source, name, phone, reason,"
                " created_at, updated_at) VALUES (?, ?, ?, 'booked', ?, ?, ?, ?, ?, ?)",
                (b["doctor"], open_days[b["day"]].isoformat(), b["time"], b.get("source", "phone"),
                 b["name"], b["phone"], b.get("reason"), ts, ts),
            )
        for c in seed.get("callbacks", []):
            conn.execute(
                "INSERT INTO inbox (kind, urgent, name, phone, reason, note, created_at) VALUES ('callback', 0, ?, ?, ?, ?, ?)",
                (c["name"], c["phone"], c["reason"], c.get("note"), ts),
            )

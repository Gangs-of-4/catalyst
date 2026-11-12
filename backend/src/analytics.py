"""Usage evidence (Phase 2 M7; contracts.md §3.1, §6.2): one `events` row per thing that happened,
with no payload, so counts can never carry a name or a phone number.

Weeks are ISO weeks in IST, Monday first. `events.created_at` is written by `db.stamp()` in IST,
so a week is the plain text range [Monday, next Monday).
"""

import csv
import io
from datetime import date, timedelta

from .core import config, db
from .core.log import log

TYPES = (
    "signup",
    "login",
    "booking_created",
    "booking_status",
    "order_created",
    "order_status",
    "callback_created",
    "call_ended",
    "wa_command",
    "settings_saved",
    "instructions_saved",
    "catalog_updated",
    "feedback_sent",
    "web_call_started",
)
RECORDS = ("booking_created", "order_created")  # "records" = bookings or orders created
WEEKS = 4


def record(conn: db.Conn, type_: str, user_id: str | None = None, commit: bool = True) -> None:
    """Count one event for the connection's business. With commit=False it joins the caller's
    open transaction (so the event and the thing it counts are saved together)."""
    if type_ not in TYPES:
        raise ValueError(f"unknown event type {type_}")
    sql = "INSERT INTO events (tenant_id, user_id, type, created_at) VALUES (?, ?, ?, ?)"
    params = (conn.tid, user_id, type_, db.stamp())
    if not commit:
        conn.execute(sql, params)
        return
    try:
        with conn:
            conn.execute(sql, params)
    except Exception as e:  # the thing it counts already happened: never fail it over a count
        log.warning("analytics: could not record %s (%s)", type_, type(e).__name__)


def week_starts(today: date | None = None, weeks: int = WEEKS) -> list[date]:
    """The Mondays of the last `weeks` ISO weeks, oldest first; the last one is this week's."""
    today = today or config.now().date()
    this_monday = today - timedelta(days=today.weekday())
    return [this_monday - timedelta(weeks=i) for i in range(weeks - 1, -1, -1)]


def _counts(conn: db.Conn, start: str | None = None, end: str | None = None) -> dict[str, int]:
    sql = "SELECT type, COUNT(*) FROM events WHERE tenant_id = ?"
    params: list = [conn.tid]
    if start:
        sql += " AND created_at >= ? AND created_at < ?"
        params += [start, end]
    rows = conn.execute(sql + " GROUP BY type", params).fetchall()
    return {r[0]: r[1] for r in rows}


def _summary(counts: dict[str, int]) -> dict[str, int]:
    return {
        "events": sum(counts.values()),
        "records": sum(counts.get(t, 0) for t in RECORDS),
        "calls": counts.get("call_ended", 0),
        "wa_commands": counts.get("wa_command", 0),
        "logins": counts.get("login", 0),
    }


def weeks(conn: db.Conn, today: date | None = None) -> list[dict]:
    """The last 4 weeks for the connection's business, oldest first."""
    out = []
    for monday in week_starts(today):
        start, end = monday.isoformat(), (monday + timedelta(days=7)).isoformat()
        out.append({"week_start": start, **_summary(_counts(conn, start, end))})
    return out


def businesses(conn: db.Conn, today: date | None = None) -> list[dict]:
    """Admin view of every business (contracts.md §6.2) in four grouped queries, whatever the
    number of businesses. `conn` is unchecked: these are cross-business admin counts."""
    mondays = week_starts(today)
    start = mondays[0].isoformat()
    end = (mondays[-1] + timedelta(days=7)).isoformat()
    totals: dict[str, dict[str, int]] = {}
    for tid, type_, n in conn.execute(
        "SELECT tenant_id, type, COUNT(*) FROM events GROUP BY tenant_id, type"
    ).fetchall():
        totals.setdefault(tid, {})[type_] = n
    by_week: dict[tuple[str, str], dict[str, int]] = {}
    for tid, type_, day, n in conn.execute(
        "SELECT tenant_id, type, substr(created_at, 1, 10), COUNT(*) FROM events"
        " WHERE created_at >= ? AND created_at < ? GROUP BY tenant_id, type, substr(created_at, 1, 10)",
        (start, end),
    ).fetchall():
        d = date.fromisoformat(day)
        monday = (d - timedelta(days=d.weekday())).isoformat()
        bucket = by_week.setdefault((tid, monday), {})
        bucket[type_] = bucket.get(type_, 0) + n
    last_event = dict(
        conn.execute("SELECT tenant_id, MAX(created_at) FROM events GROUP BY tenant_id").fetchall()
    )
    users = {
        r[0]: (r[1], r[2])
        for r in conn.execute(
            "SELECT tenant_id, COUNT(*), MAX(last_active_at) FROM users GROUP BY tenant_id"
        ).fetchall()
    }
    out = []
    for t in conn.execute("SELECT * FROM tenants ORDER BY created_at, id").fetchall():
        tid = t["id"]
        summary = _summary(totals.get(tid, {}))
        count, user_active = users.get(tid, (0, None))
        weeks_ = []
        for monday in mondays:
            week = _summary(by_week.get((tid, monday.isoformat()), {}))
            weeks_.append({"week_start": monday.isoformat(), **{k: week[k] for k in WEEK_KEYS[1:]}})
        out.append(
            {
                "id": tid,
                "name": t["name"],
                "public_id": t["public_id"],
                "template": t["template"],
                "created_at": t["created_at"],
                "is_demo": bool(t["is_demo"]),
                "users": count,
                "records": summary["records"],
                "calls": summary["calls"],
                "wa_commands": summary["wa_commands"],
                "last_active": max(
                    (x for x in (last_event.get(tid), user_active) if x), default=None
                ),
                "weeks": weeks_,
            }
        )
    return out


WEEK_KEYS = ("week_start", "events", "records", "calls", "wa_commands")
CSV_COLUMNS = ("week_start", "events", "records", "calls", "wa_commands", "logins")


def usage_csv(conn: db.Conn) -> str:
    """Counts only, never names or numbers: one row per week for the last 4 weeks, then `total`
    (the sum of those weeks)."""
    rows = weeks(conn)
    buf = io.StringIO()
    out = csv.writer(buf, lineterminator="\n")
    out.writerow(CSV_COLUMNS)
    for w in rows:
        out.writerow([w[c] for c in CSV_COLUMNS])
    out.writerow(["total", *(sum(w[c] for w in rows) for c in CSV_COLUMNS[1:])])
    return buf.getvalue()

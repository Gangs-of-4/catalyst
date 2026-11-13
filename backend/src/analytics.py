"""Usage evidence (Phase 2 M7; contracts.md §3.1, §6.2): one `events` row per thing that happened,
with no payload, so counts can never carry a name or a phone number.

Weeks are ISO weeks in IST, Monday first. `events.created_at` is written by `db.stamp()` in IST,
so a week is the plain text range [Monday, next Monday).
"""

import csv
import io
from datetime import date, datetime, timedelta

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


# ---------- Time in the app and the admin dashboard (issue #56; contracts.md §6.2) ----------

DAYS = 28  # the dashboard's day-by-day window, today included
SCOPES = ("real", "demo", "all")


def ping(conn: db.Conn, user_id: str) -> None:
    """One minute in the app for the logged-in owner (`conn` scoped to their business). A second
    ping in the same minute (two tabs, a retry) changes nothing."""
    minute = config.now().strftime("%Y-%m-%dT%H:%M")
    with conn:
        conn.execute(
            "INSERT INTO activity (tenant_id, user_id, day, minutes, last_minute) VALUES (?, ?, ?, 1, ?)"
            " ON CONFLICT (tenant_id, user_id, day) DO UPDATE SET minutes = activity.minutes + 1,"
            " last_minute = excluded.last_minute WHERE activity.last_minute <> excluded.last_minute",
            (conn.tid, user_id, minute[:10], minute),
        )
        conn.execute(
            "UPDATE users SET last_active_at = ? WHERE id = ? AND tenant_id = ?",
            (db.stamp(), user_id, conn.tid),
        )


def _when(text: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(text) if text else None
    except ValueError:
        return None


def _call_minutes(started: str | None, ended: str | None) -> tuple[str, float] | None:
    """(IST day, minutes) of one finished call, or None. Worked out here, not in SQL, because the
    two databases do date maths differently. A duration of zero or less is skipped (started_at is
    rewritten from the end-of-call report, so a bad report could put it after ended_at).
    """
    a, b = _when(started), _when(ended)
    if a is None or b is None or (a.tzinfo is None) != (b.tzinfo is None):
        return None
    seconds = (b - a).total_seconds()
    if seconds <= 0:
        return None
    day = (a.astimezone(config.IST) if a.tzinfo else a).date().isoformat()
    return day, seconds / 60


def _gather(conn: db.Conn, today: date) -> dict:
    """Everything the dashboard adds up, per business, in a fixed number of grouped queries.
    `conn` is unchecked: these are cross-business admin counts."""
    start = (today - timedelta(days=DAYS - 1)).isoformat()
    g: dict = {
        "start": start,
        "week": (today - timedelta(days=6)).isoformat(),
        "demo": {
            r[0]: bool(r[1]) for r in conn.execute("SELECT id, is_demo FROM tenants").fetchall()
        },
        "types": {},
        "daily": {},
        "last_event": {},
        "users": {},
        "calls": {},
        "sources": {},
        "records": {},
        "feedback": {},
        "activity": [],
    }
    for tid, type_, n in conn.execute(
        "SELECT tenant_id, type, COUNT(*) FROM events GROUP BY tenant_id, type"
    ).fetchall():
        g["types"].setdefault(tid, {})[type_] = n
    for tid, day, type_, n in conn.execute(
        "SELECT tenant_id, substr(created_at, 1, 10), type, COUNT(*) FROM events WHERE created_at >= ?"
        " GROUP BY tenant_id, substr(created_at, 1, 10), type",
        (start,),
    ).fetchall():
        bucket = g["daily"].setdefault((tid, day), {})
        bucket[type_] = bucket.get(type_, 0) + n
    for tid, last in conn.execute(
        "SELECT tenant_id, MAX(created_at) FROM events GROUP BY tenant_id"
    ).fetchall():
        g["last_event"][tid] = last
    for tid, last in conn.execute("SELECT tenant_id, last_active_at FROM users").fetchall():
        g["users"].setdefault(tid, []).append(last)
    for tid, started, ended in conn.execute(
        "SELECT tenant_id, started_at, ended_at FROM calls WHERE ended_at IS NOT NULL"
    ).fetchall():
        found = _call_minutes(started, ended)
        if found:
            g["calls"].setdefault(tid, []).append(found)
    for table, kind in (("bookings", "bookings"), ("orders", "orders")):
        for tid, source, n in conn.execute(
            f"SELECT tenant_id, source, COUNT(*) FROM {table} GROUP BY tenant_id, source"
        ).fetchall():
            src = g["sources"].setdefault(tid, {})
            src[source] = src.get(source, 0) + n
            rec = g["records"].setdefault(tid, {"bookings": 0, "orders": 0})
            rec[kind] += n
    for tid, n in conn.execute(
        "SELECT tenant_id, COUNT(*) FROM feedback GROUP BY tenant_id"
    ).fetchall():
        g["feedback"][tid] = n
    g["activity"] = [
        (r[0], r[1], r[2], r[3])
        for r in conn.execute("SELECT tenant_id, user_id, day, minutes FROM activity").fetchall()
    ]
    return g


def _totals(g: dict, ids: set[str]) -> dict:
    types: dict[str, int] = {}
    for tid in ids:
        for k, n in g["types"].get(tid, {}).items():
            types[k] = types.get(k, 0) + n
    active = {tid for tid in ids if (g["last_event"].get(tid) or "") >= g["week"]}
    active |= {a[0] for a in g["activity"] if a[0] in ids and a[2] >= g["week"] and a[3] > 0}
    users = [u for tid in ids for u in g["users"].get(tid, [])]
    sources: dict[str, int] = {}
    records = {"bookings": 0, "orders": 0}
    for tid in ids:
        for k, n in g["sources"].get(tid, {}).items():
            sources[k] = sources.get(k, 0) + n
        for k, n in g["records"].get(tid, {}).items():
            records[k] += n
    return {
        "businesses": len(ids),
        "active_businesses_7d": len(active),
        "users": len(users),
        "active_users_7d": sum(1 for u in users if (u or "") >= g["week"]),
        "calls": types.get("call_ended", 0),
        "call_minutes": round(sum(m for tid in ids for _, m in g["calls"].get(tid, [])), 1),
        "records": records,
        "records_by_source": sources,
        "wa_commands": types.get("wa_command", 0),
        "feedback": sum(g["feedback"].get(tid, 0) for tid in ids),
        "app_minutes": sum(a[3] for a in g["activity"] if a[0] in ids),
    }


def _features(g: dict, ids: set[str]) -> list[dict]:
    counts: dict[str, int] = {}
    for tid in ids:
        for k, n in g["types"].get(tid, {}).items():
            counts[k] = counts.get(k, 0) + n
    return [
        {"type": k, "count": n} for k, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def _daily(g: dict, ids: set[str], today: date) -> list[dict]:
    days = [(today - timedelta(days=i)).isoformat() for i in range(DAYS - 1, -1, -1)]
    out = {
        d: {
            "date": d,
            "active": set(),
            "events": 0,
            "calls": 0,
            "call_minutes": 0.0,
            "app_minutes": 0,
        }
        for d in days
    }
    for (tid, day), types in g["daily"].items():
        if tid in ids and day in out:
            out[day]["events"] += sum(types.values())
            out[day]["calls"] += types.get("call_ended", 0)
            out[day]["active"].add(tid)
    for tid in ids:
        for day, minutes in g["calls"].get(tid, []):
            if day in out:
                out[day]["call_minutes"] += minutes
    for tid, _, day, minutes in g["activity"]:
        if tid in ids and day in out:
            out[day]["app_minutes"] += minutes
            if minutes > 0:
                out[day]["active"].add(tid)
    return [
        {
            "date": d["date"],
            "active_businesses": len(d["active"]),
            "events": d["events"],
            "calls": d["calls"],
            "call_minutes": round(d["call_minutes"], 1),
            "app_minutes": d["app_minutes"],
        }
        for d in out.values()
    ]


def overview(conn: db.Conn, scope: str = "real", today: date | None = None) -> dict:
    """The dashboard's headline numbers. `real` and `demo` totals always both come back; `features`
    and `daily` follow `scope` (real businesses, the demos, or all)."""
    today = today or config.now().date()
    g = _gather(conn, today)
    real = {tid for tid, demo in g["demo"].items() if not demo}
    demo = {tid for tid, is_demo in g["demo"].items() if is_demo}
    ids = {"real": real, "demo": demo, "all": real | demo}[scope]
    return {
        "generated_at": db.stamp(),
        "real": _totals(g, real),
        "demo": _totals(g, demo),
        "features": _features(g, ids),
        "daily": _daily(g, ids, today),
    }


def business_detail(conn: db.Conn, tid: str, today: date | None = None) -> dict | None:
    """One business for the admin sheet: its list row, what it used, day by day, and its people as
    counts only (no names, emails or numbers). `conn` is unchecked. None if there's no such business.
    """
    today = today or config.now().date()
    row = next((b for b in businesses(conn, today) if b["id"] == tid), None)
    if row is None:
        return None
    g = _gather(conn, today)
    logins: dict[str, int] = {}
    event_days: dict[str, set[str]] = {}
    for uid, day, type_ in conn.execute(
        "SELECT user_id, substr(created_at, 1, 10), type FROM events WHERE tenant_id = ? AND user_id IS NOT NULL",
        (tid,),
    ).fetchall():
        event_days.setdefault(uid, set()).add(day)
        if type_ == "login":
            logins[uid] = logins.get(uid, 0) + 1
    people = []
    for uid, last in conn.execute(
        "SELECT id, last_active_at FROM users WHERE tenant_id = ? ORDER BY created_at, id",
        (tid,),
    ).fetchall():
        mine = [a for a in g["activity"] if a[0] == tid and a[1] == uid]
        days = event_days.get(uid, set()) | {a[2] for a in mine if a[3] > 0}
        people.append(
            {
                "id": uid,
                "role": "owner",  # one owner per business (ADR-0038); users has no role column yet
                "last_active": last,
                "logins": logins.get(uid, 0),
                "app_minutes": sum(a[3] for a in mine),
                "active_days": len(days),
            }
        )
    return {
        "business": row,
        "features": _features(g, {tid}),
        "daily": _daily(g, {tid}, today),
        "users": people,
    }


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

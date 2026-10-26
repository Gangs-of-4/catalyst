"""Slots, bookings and blocks for one clinic. The DB index is the double-booking lock (C4)."""
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from ..core import config, db
from ..core import settings as cs

STATUSES = ("booked", "arrived", "no_show", "done", "cancelled")
ACTIVE = ("booked", "arrived", "done")  # occupy the slot; cancelled and no_show free it
SOURCES = ("phone", "whatsapp", "walk_in")
SEARCH_DAYS = 7


class BookingError(Exception):
    def __init__(self, code: str, message: str, alternatives: list | None = None):
        super().__init__(message)
        self.code = code
        self.alternatives = alternatives or []


@dataclass(frozen=True)
class Slot:
    resource_id: str
    date: date
    time: str  # HH:MM


def _minutes(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def session_times(s: dict) -> list[str]:
    """Every slot start in the clinic's sessions."""
    step = int(s["slot_min"])
    out = []
    for start, end in s["sessions"]:
        t = _minutes(start)
        while t + step <= _minutes(end):
            out.append(_hhmm(t))
            t += step
    return out


def is_closed(s: dict, d: date) -> bool:
    return d.weekday() in s.get("closed_weekdays", [])


def blocks_on(conn: sqlite3.Connection, d: date) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM blocks WHERE date = ?", (d.isoformat(),)).fetchall()


def _blocking(blocks: list, resource_id: str, time: str, step: int) -> sqlite3.Row | None:
    t0, t1 = _minutes(time), _minutes(time) + step
    for b in blocks:
        if b["resource_id"] not in (None, resource_id):
            continue
        if b["start"] is None or (_minutes(b["start"]) < t1 and t0 < _minutes(b["end"])):
            return b
    return None


def day_grid(conn: sqlite3.Connection, s: dict, d: date) -> dict:
    """Per doctor, every slot of the day with its state: free, booked, blocked or past."""
    step = int(s["slot_min"])
    now = config.now()
    blocks = blocks_on(conn, d)
    rows = conn.execute(
        "SELECT * FROM bookings WHERE date = ? AND status NOT IN ('cancelled') ORDER BY time, id",
        (d.isoformat(),),
    ).fetchall()
    closed = is_closed(s, d)
    columns = []
    for doc in s["doctors"]:
        slots = []
        for t in session_times(s):
            bookings = [dict(r) for r in rows if r["resource_id"] == doc["id"] and r["time"] == t]
            block = _blocking(blocks, doc["id"], t, step)
            past = d < now.date() or (d == now.date() and _minutes(t) <= now.hour * 60 + now.minute)
            active = [b for b in bookings if b["status"] in ACTIVE]
            if active:
                state = "booked"
            elif closed or block:
                state = "blocked"
            elif past:
                state = "past"
            else:
                state = "free"
            slots.append({
                "time": t, "state": state, "bookings": bookings,
                "block": (block["kind"] if block else ("closed" if closed else None)),
            })
        columns.append({"doctor": doc, "slots": slots})
    # bookings at times outside the grid (e.g. after a slot-length change) still show
    grid_times = set(session_times(s))
    stray = [dict(r) for r in rows if r["time"] not in grid_times]
    return {"date": d.isoformat(), "closed": closed, "columns": columns, "stray": stray}


def free_slots(conn: sqlite3.Connection, s: dict, d: date, resource_id: str | None = None) -> list[Slot]:
    if is_closed(s, d):
        return []
    step = int(s["slot_min"])
    now = config.now()
    if d < now.date():
        return []
    blocks = blocks_on(conn, d)
    taken = {
        (r["resource_id"], r["time"])
        for r in conn.execute(
            f"SELECT resource_id, time FROM bookings WHERE date = ? AND status IN {ACTIVE}", (d.isoformat(),)
        )
    }
    doctors = [doc["id"] for doc in s["doctors"] if resource_id in (None, doc["id"])]
    out = []
    for t in session_times(s):
        if d == now.date() and _minutes(t) <= now.hour * 60 + now.minute:
            continue
        for rid in doctors:
            if (rid, t) not in taken and not _blocking(blocks, rid, t, step):
                out.append(Slot(rid, d, t))
    return out


def find_slots(
    conn: sqlite3.Connection, s: dict, day: date, pref_time: str | None = None,
    resource_id: str | None = None, limit: int = 3,
) -> list[Slot]:
    """The `limit` slots nearest to the preferred time on `day`, or on the next open day within a week."""
    for offset in range(SEARCH_DAYS + 1):
        d = day + timedelta(days=offset)
        slots = free_slots(conn, s, d, resource_id)
        if not slots:
            continue
        # With "any doctor", one slot per time: the first free doctor in settings order.
        by_time: dict[str, Slot] = {}
        for sl in slots:
            by_time.setdefault(sl.time, sl)
        target = _minutes(pref_time) if pref_time else 0
        ordered = sorted(by_time.values(), key=lambda sl: (abs(_minutes(sl.time) - target), sl.time))
        return sorted(ordered[:limit], key=lambda sl: sl.time)
    return []


def book(
    conn: sqlite3.Connection, s: dict, resource_id: str, d: date, time: str, name: str,
    phone: str | None, source: str, reason: str | None = None, call_id: str | None = None,
    _commit: bool = True,
) -> int:
    """Insert a booking. Raises BookingError('SLOT_TAKEN', alternatives=…) if the slot is gone."""
    if source not in SOURCES:
        raise BookingError("VALIDATION", f"Unknown source {source}")
    if not cs.doctor(s, resource_id):
        raise BookingError("VALIDATION", "Unknown doctor")
    if not name.strip():
        raise BookingError("VALIDATION", "Name is required")
    valid = {(sl.resource_id, sl.time) for sl in free_slots(conn, s, d, resource_id)}
    if (resource_id, time) not in valid:
        # Either already booked, blocked, closed, past, or not a slot start. Same answer for the caller.
        code = "SLOT_TAKEN" if time in session_times(s) else "VALIDATION"
        raise BookingError(code, "That slot is not available", find_slots(conn, s, d, time, None))
    ts = db.stamp()
    try:
        cur = conn.execute(
            "INSERT INTO bookings (resource_id, date, time, status, source, name, phone, reason, call_id,"
            " created_at, updated_at) VALUES (?, ?, ?, 'booked', ?, ?, ?, ?, ?, ?, ?)",
            (resource_id, d.isoformat(), time, source, name.strip(), phone,
             (reason or "").strip()[:80] or None, call_id, ts, ts),
        )
        if _commit:
            conn.commit()
    except sqlite3.IntegrityError:
        if _commit:
            conn.rollback()
        raise BookingError("SLOT_TAKEN", "That slot was just taken", find_slots(conn, s, d, time, None))
    return cur.lastrowid


def get(conn: sqlite3.Connection, booking_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()


def upcoming_for_phone(conn: sqlite3.Connection, phone: str) -> list[sqlite3.Row]:
    today = config.now().date().isoformat()
    return conn.execute(
        "SELECT * FROM bookings WHERE phone = ? AND status = 'booked' AND date >= ? ORDER BY date, time",
        (phone, today),
    ).fetchall()


def set_status(conn: sqlite3.Connection, booking_id: int, status: str) -> None:
    if status not in STATUSES:
        raise BookingError("VALIDATION", f"Unknown status {status}")
    row = get(conn, booking_id)
    if not row:
        raise BookingError("NOT_FOUND", "No such booking")
    try:
        with conn:
            conn.execute("UPDATE bookings SET status = ?, updated_at = ? WHERE id = ?", (status, db.stamp(), booking_id))
    except sqlite3.IntegrityError:
        raise BookingError("SLOT_TAKEN", "Another booking now holds that slot")


def cancel(conn: sqlite3.Connection, booking_id: int) -> sqlite3.Row:
    row = get(conn, booking_id)
    if not row or row["status"] != "booked":
        raise BookingError("NOT_FOUND", "No active booking to cancel")
    set_status(conn, booking_id, "cancelled")
    return row


def reschedule(
    conn: sqlite3.Connection, s: dict, booking_id: int, resource_id: str, d: date, time: str,
) -> int:
    """Book the new slot and cancel the old one in one transaction. Returns the new booking id."""
    old = get(conn, booking_id)
    if not old or old["status"] != "booked":
        raise BookingError("NOT_FOUND", "No active booking to move")
    try:
        new_id = book(conn, s, resource_id, d, time, old["name"], old["phone"], old["source"],
                      old["reason"], old["call_id"], _commit=False)
        conn.execute("UPDATE bookings SET status = 'cancelled', updated_at = ? WHERE id = ?", (db.stamp(), booking_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return new_id


def add_block(
    conn: sqlite3.Connection, d: date, kind: str, source: str, resource_id: str | None = None,
    start: str | None = None, end: str | None = None,
) -> int:
    with conn:
        cur = conn.execute(
            'INSERT INTO blocks (resource_id, date, start, "end", kind, source, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (resource_id, d.isoformat(), start, end, kind, source, db.stamp()),
        )
    return cur.lastrowid


def remove_block(conn: sqlite3.Connection, block_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM blocks WHERE id = ?", (block_id,))


def list_blocks(conn: sqlite3.Connection, from_date: date | None = None) -> list[dict]:
    since = (from_date or config.now().date()).isoformat()
    return [dict(r) for r in conn.execute("SELECT * FROM blocks WHERE date >= ? ORDER BY date, id", (since,))]


def affected_bookings(conn: sqlite3.Connection, s: dict, d: date, resource_id: str | None,
                      start: str | None = None, end: str | None = None) -> list[sqlite3.Row]:
    """Active bookings a new block would cover."""
    rows = conn.execute(
        "SELECT * FROM bookings WHERE date = ? AND status = 'booked'", (d.isoformat(),)
    ).fetchall()
    fake = [{"resource_id": resource_id, "start": start, "end": end}]
    step = int(s["slot_min"])
    return [r for r in rows if _blocking(fake, r["resource_id"], r["time"], step)]


def as_datetime(d: date, time: str) -> datetime:
    h, m = map(int, time.split(":"))
    return datetime(d.year, d.month, d.day, h, m, tzinfo=config.IST)

"""Day stats and the doctor's WhatsApp summary (C10). Counts only; no patient details."""
import sqlite3
from datetime import date

from ...booking.when import short_date


def day_stats(conn: sqlite3.Connection, d: date) -> dict:
    day = d.isoformat()
    calls = conn.execute(
        "SELECT outcome, booked, changed, escalated, callback, safety_review FROM calls WHERE substr(started_at, 1, 10) = ?",
        (day,),
    ).fetchall()
    outcomes = {k: 0 for k in ("booked", "changed", "escalated", "callback", "answered", "hung_up")}
    for c in calls:
        if c["outcome"] in outcomes:
            outcomes[c["outcome"]] += 1
    sources = dict(conn.execute(
        "SELECT source, COUNT(*) FROM bookings WHERE date = ? AND status != 'cancelled' GROUP BY source", (day,)
    ).fetchall())
    open_items = conn.execute(
        "SELECT SUM(urgent = 1), SUM(urgent = 0 AND kind = 'callback') FROM inbox WHERE done_at IS NULL"
    ).fetchone()
    return {
        "date": day,
        "calls": len(calls),
        "booked_calls": sum(1 for c in calls if c["booked"]),
        "outcomes": outcomes,
        "safety_review": sum(1 for c in calls if c["safety_review"]),
        "appointments": sum(sources.values()),
        "sources": sources,
        "urgent_open": open_items[0] or 0,
        "callbacks_open": open_items[1] or 0,
    }


def stats_sentence(st: dict) -> str:
    def n(count: int, word: str) -> str:
        return f"{count} {word}" + ("" if count == 1 else "s")
    return (f"Today: {n(st['calls'], 'call')}, {st['booked_calls']} booked, {st['urgent_open']} urgent, "
            f"{n(st['callbacks_open'], 'callback')} open.")


def summary_text(clinic: str, d: date, st: dict) -> str:
    o, src = st["outcomes"], st["sources"]
    lines = [
        f"{clinic} — summary, {short_date(d)}",
        f"Calls: {st['calls']} — {o['booked']} booked, {o['changed']} changed, {o['escalated']} escalated, "
        f"{o['callback']} callback, {o['answered']} answered, {o['hung_up']} hung up.",
        f"Appointments: {st['appointments']} (phone {src.get('phone', 0)}, WhatsApp {src.get('whatsapp', 0)}, "
        f"walk-in {src.get('walk_in', 0)}).",
        f"Open: {st['urgent_open']} urgent, {st['callbacks_open']} callbacks.",
    ]
    if st["safety_review"]:
        lines.append(f"⚠️ {st['safety_review']} call(s) flagged for safety review on the desk.")
    return "\n".join(lines)

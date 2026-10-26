"""The agent's tools. Each returns one plain-text result the voice LLM reads (contracts.md §1, §1.10).

Results state the resolved day and date so the agent reads back exactly what was booked (C2).
"""
import sqlite3
import traceback
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from .. import inbox
from ..booking import service as bk
from ..booking.when import parse_date, parse_time, spoken_date, spoken_time
from ..channels.whatsapp import alerts
from ..core import config, db
from ..core import phone as ph
from ..core import settings as cs
from ..core.log import log
from ..knowledge import answers
from . import calls

FAILOVER = ("TOOL ERROR. Do not guess. Apologise briefly, take the caller's name and number, "
            "and call create_callback with reason failover and urgent true.")


@dataclass
class Ctx:
    conn: sqlite3.Connection
    settings: dict
    call_id: str | None = None
    caller_phone: str | None = None
    defer: list[Callable[[], None]] = field(default_factory=list)  # run after the response is sent


def _today() -> date:
    return config.now().date()


def _when(d: date, t: str) -> str:
    return f"{spoken_date(d)}, {spoken_time(t)}"


def _doctor_arg(ctx: Ctx, text: str | None) -> tuple[dict | None, str | None]:
    """(doctor, error). No text means any doctor."""
    if not text:
        return None, None
    doc = cs.match_doctor(ctx.settings, text)
    if doc:
        return doc, None
    names = ", ".join(d["name"] for d in ctx.settings["doctors"])
    return None, f"No doctor matches '{text}'. The doctors are: {names}. Ask the caller which one."


def _phone_arg(ctx: Ctx, text) -> str | None:
    return ph.normalize(str(text)) if text else ctx.caller_phone


def _no_slots_reason(ctx: Ctx, d: date, doctor: dict | None) -> str:
    s = ctx.settings
    if bk.is_closed(s, d):
        return "the clinic is closed that day"
    for b in bk.blocks_on(ctx.conn, d):
        if b["start"] is None and b["resource_id"] is None:
            return "the clinic is on holiday that day"
        if b["start"] is None and doctor and b["resource_id"] == doctor["id"]:
            return f"{doctor['name']} is on leave that day"
    return "that day is fully booked" if d > _today() else "no time is left today"


def get_clinic_info(ctx: Ctx, args: dict) -> str:
    found = answers.lookup(ctx.conn, ctx.settings, str(args.get("question", "")))
    if not found:
        return ("NOT FOUND in the clinic-approved answers. Say you don't have that answer, take the caller's "
                "name and number, and call create_callback with reason unanswered_question.")
    return "Clinic-approved answer (say only this, in the caller's language): " + " | ".join(found)


def find_slots(ctx: Ctx, args: dict) -> str:
    raw_date = str(args.get("date") or "")
    d = parse_date(raw_date, _today())
    if d is None:
        return f"Could not understand the day '{raw_date}'. Ask the caller which day they want."
    if d < _today():
        return f"{spoken_date(d)} has already passed. Ask the caller for a future day."
    t = parse_time(str(args.get("time") or "")) if args.get("time") else None
    doctor, err = _doctor_arg(ctx, args.get("doctor"))
    if err:
        return err
    limit = int(ctx.settings.get("offer_slots", 3))
    slots = bk.find_slots(ctx.conn, ctx.settings, d, t, doctor["id"] if doctor else None, limit)
    if not slots:
        return (f"No free slots on {spoken_date(d)} or the following week. Offer a callback "
                f"(create_callback with reason other).")
    found_day = slots[0].date
    listing = "; ".join(f"{spoken_time(sl.time)} with {cs.doctor_name(ctx.settings, sl.resource_id)}" for sl in slots)
    head = ""
    if found_day != d:
        head = f"Nothing free on {spoken_date(d)} because {_no_slots_reason(ctx, d, doctor)}. Nearest open day: "
    elif t and all(sl.time != t for sl in slots):
        head = f"{spoken_time(t)} is not free. "
    return (f"{head}Free slots on {spoken_date(found_day)}: {listing}. "
            f"Offer only these. When booking, pass date {found_day.isoformat()} and the doctor's name.")


def book(ctx: Ctx, args: dict) -> str:
    name = str(args.get("name") or "").strip()
    phone = _phone_arg(ctx, args.get("phone"))
    if not name:
        return "NOT BOOKED: ask the caller's name first."
    if not phone:
        return "NOT BOOKED: the phone number must be a 10-digit Indian mobile number. Ask again and read it back."
    d = parse_date(str(args.get("date") or ""), _today())
    t = parse_time(str(args.get("time") or ""))
    if not d or not t:
        return "NOT BOOKED: could not understand the day or time. Call find_slots again and offer its slots."
    doctor, err = _doctor_arg(ctx, args.get("doctor"))
    if err:
        return "NOT BOOKED: " + err
    if not doctor:
        free = [sl for sl in bk.free_slots(ctx.conn, ctx.settings, d) if sl.time == t]
        doctor = cs.doctor(ctx.settings, free[0].resource_id) if free else ctx.settings["doctors"][0]
    try:
        bid = bk.book(ctx.conn, ctx.settings, doctor["id"], d, t, name, phone, "phone", args.get("reason"), ctx.call_id)
    except bk.BookingError as e:
        alt = "; ".join(f"{spoken_date(sl.date)} {spoken_time(sl.time)} with {cs.doctor_name(ctx.settings, sl.resource_id)}"
                        for sl in e.alternatives)
        return (f"NOT BOOKED: {_when(d, t)} with {doctor['name']} is not available. "
                + (f"Free alternatives: {alt}. Offer these." if alt else "Call find_slots for another day."))
    calls.flag(ctx.conn, ctx.call_id, "booked")
    return (f"BOOKED, booking number {bid}: {name}, {_when(d, t)}, with {doctor['name']}, "
            f"phone ending {phone[-4:]}. Now confirm the day, date, time and doctor to the caller.")


def _describe(ctx: Ctx, row) -> str:
    d = date.fromisoformat(row["date"])
    return f"booking {row['id']}: {_when(d, row['time'])} with {cs.doctor_name(ctx.settings, row['resource_id'])}"


def find_booking(ctx: Ctx, args: dict) -> str:
    phone = _phone_arg(ctx, args.get("phone"))
    if not phone:
        return "Need a 10-digit mobile number to look up the appointment. Ask the caller."
    rows = bk.upcoming_for_phone(ctx.conn, phone)
    if not rows:
        return "No upcoming appointment for that number. Read the number back to the caller to check it."
    return "Upcoming: " + "; ".join(f"{_describe(ctx, r)} (name {r['name']})" for r in rows) + "."


def _resolve(ctx: Ctx, args: dict, date_key: str | None = "date"):
    """(booking row, error text). Uses booking_id, else phone (+ optional date)."""
    if args.get("booking_id"):
        try:
            row = bk.get(ctx.conn, int(args["booking_id"]))
        except (TypeError, ValueError):
            row = None
        if not row or row["status"] != "booked":
            return None, "No active booking with that number. Call find_booking with the caller's phone."
        return row, None
    phone = _phone_arg(ctx, args.get("phone"))
    if not phone:
        return None, "Need the booking number or the caller's 10-digit mobile number."
    rows = bk.upcoming_for_phone(ctx.conn, phone)
    d = parse_date(str(args.get(date_key) or ""), _today()) if date_key and args.get(date_key) else None
    if d:
        rows = [r for r in rows if r["date"] == d.isoformat()]
    if not rows:
        return None, "No upcoming appointment found for that number. Read the number back to check it."
    if len(rows) > 1:
        return None, ("More than one appointment: " + "; ".join(_describe(ctx, r) for r in rows)
                      + ". Ask which one, then pass its booking_id.")
    return rows[0], None


def reschedule(ctx: Ctx, args: dict) -> str:
    row, err = _resolve(ctx, args, date_key=None)
    if err:
        return "NOT MOVED: " + err
    d = parse_date(str(args.get("new_date") or ""), _today())
    t = parse_time(str(args.get("new_time") or ""))
    if not d or not t:
        return "NOT MOVED: could not understand the new day or time. Call find_slots and offer its slots."
    doctor, err = _doctor_arg(ctx, args.get("doctor"))
    if err:
        return "NOT MOVED: " + err
    if doctor:
        candidates = [doctor["id"]]
    else:  # keep the same doctor if free, else any free doctor at that time
        free = {sl.resource_id for sl in bk.free_slots(ctx.conn, ctx.settings, d) if sl.time == t}
        candidates = [row["resource_id"]] if row["resource_id"] in free else sorted(free) or [row["resource_id"]]
    old = _describe(ctx, row)
    try:
        new_id = bk.reschedule(ctx.conn, ctx.settings, row["id"], candidates[0], d, t)
    except bk.BookingError as e:
        alt = "; ".join(f"{spoken_date(sl.date)} {spoken_time(sl.time)} with {cs.doctor_name(ctx.settings, sl.resource_id)}"
                        for sl in e.alternatives)
        return f"NOT MOVED: {_when(d, t)} is not free. " + (f"Free alternatives: {alt}." if alt else "")
    calls.flag(ctx.conn, ctx.call_id, "changed")
    return (f"MOVED. Old {old} is cancelled. New booking number {new_id}: {_when(d, t)} with "
            f"{cs.doctor_name(ctx.settings, candidates[0])}. Confirm the new day, date, time and doctor.")


def cancel(ctx: Ctx, args: dict) -> str:
    row, err = _resolve(ctx, args)
    if err:
        return "NOT CANCELLED: " + err
    bk.cancel(ctx.conn, row["id"])
    calls.flag(ctx.conn, ctx.call_id, "changed")
    return f"CANCELLED {_describe(ctx, row)}. The slot is free again. Ask if they want a new time."


def _alert(ctx: Ctx, item_id: int) -> None:
    def run() -> None:
        conn = db.connect()
        try:
            alerts.alert_for_inbox(conn, item_id)
        finally:
            conn.close()
    ctx.defer.append(run)


def create_callback(ctx: Ctx, args: dict) -> str:
    phone = _phone_arg(ctx, args.get("phone"))
    reason = args.get("reason") if args.get("reason") in ("unanswered_question", "staff_request", "failover", "other") else "other"
    urgent = bool(args.get("urgent"))
    item = inbox.create(ctx.conn, "callback", urgent=urgent, name=(args.get("name") or None),
                        phone=phone, reason=reason, note=args.get("note"), call_id=ctx.call_id)
    calls.flag(ctx.conn, ctx.call_id, "callback")
    _alert(ctx, item)
    missing = "" if phone else " The number was not valid; ask for the 10-digit mobile number and call create_callback again."
    return ("Callback logged for the clinic team. Tell the caller the clinic will call them back "
            + ("very soon." if urgent else "today during clinic hours.") + missing)


def _open_now(s: dict) -> bool:
    now = config.now()
    if bk.is_closed(s, now.date()):
        return False
    hhmm = now.strftime("%H:%M")
    return any(a <= hhmm < b for a, b in s["sessions"])


def escalate(ctx: Ctx, args: dict) -> str:
    category = args.get("category") if args.get("category") in ("red_flag", "grey_zone", "caller_request") else "grey_zone"
    summary = str(args.get("summary") or "").strip()
    if args.get("matched_rule"):
        summary = f"[{args['matched_rule']}] {summary}"
    item = inbox.create(ctx.conn, "escalation", urgent=True, name=(args.get("name") or None),
                        phone=_phone_arg(ctx, args.get("phone")), reason=category, note=summary, call_id=ctx.call_id)
    calls.flag(ctx.conn, ctx.call_id, "escalated")
    _alert(ctx, item)
    parts = ["ESCALATED: the doctor has been alerted on WhatsApp as urgent."]
    if category != "caller_request":
        if not _open_now(ctx.settings):
            parts.append("The clinic is closed right now, so the instruction matters even more.")
        parts.append(f"If you have not said it yet, say the emergency instruction now: "
                     f"\"{ctx.settings['emergency_instruction']}\"")
    parts.append("Live transfer is not available on this line. Tell the caller the clinic will call them back "
                 "very soon. If you don't have their name and 10-digit number yet, ask for them and call escalate "
                 "again with them. Give no medical advice.")
    return " ".join(parts)


def transfer(ctx: Ctx, args: dict) -> str:
    return ("Live transfer is not available on web calls. Call escalate instead, and tell the caller the doctor "
            "has been alerted and will call back.")


def log_call_outcome(ctx: Ctx, args: dict) -> str:
    return "OK. The outcome is recorded automatically."


HANDLERS: dict[str, Callable[[Ctx, dict], str]] = {
    f.__name__: f for f in (get_clinic_info, find_slots, book, find_booking, reschedule, cancel,
                            create_callback, escalate, transfer, log_call_outcome)
}


def run(ctx: Ctx, name: str, args: dict) -> str:
    handler = HANDLERS.get(name)
    if not handler:
        return f"Unknown tool {name}. " + FAILOVER
    try:
        return handler(ctx, args if isinstance(args, dict) else {})
    except Exception as e:  # never dead air: the agent falls back to an urgent callback
        # Location only, no message or traceback text: those can carry caller details.
        frame = traceback.extract_tb(e.__traceback__)[-1]
        log.error("tool %s failed for call %s: %s at %s:%s", name, ctx.call_id, type(e).__name__,
                  frame.filename.rsplit("src", 1)[-1], frame.lineno)
        return FAILOVER

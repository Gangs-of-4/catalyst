"""Desk APIs for the logged-in owner's business (C7, C10; contracts.md §6.1).

Every route reads and writes only the business in the session. The /desk page itself is static and
public, like any page on Vercel; without a session its API calls get 401 and it asks the owner to log in.
"""

import json
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .. import inbox
from ..booking import service as bk
from ..booking.when import short_date, spoken_date, spoken_time
from ..channels.whatsapp import alerts, summary
from ..core import config, db
from ..core import phone as ph
from ..core import settings as cs
from ..core.config import FRONTEND_DIR
from ..providers.messaging import twilio_whatsapp
from .deps import get_user_conn, require_bookings, require_csrf_header
from .errors import ApiError

pages = APIRouter()
router = APIRouter(dependencies=[Depends(require_csrf_header)])


@pages.get("/desk", include_in_schema=False)
def desk_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "desk.html")


@router.get("/api/staff/meta")
def meta(conn: db.Conn = Depends(get_user_conn)) -> dict:
    s = cs.load(conn)
    return {
        "clinic": s["name"],
        "city": s.get("city", ""),
        "twilio": twilio_whatsapp.configured(),
        "whatsappNumbers": len(alerts.recipients(s)),
        "today": config.now().date().isoformat(),
    }


def _day(value: str | None) -> date:
    try:
        return date.fromisoformat(value) if value else config.now().date()
    except ValueError:
        raise ApiError(422, "VALIDATION", "Date must look like 2026-11-15.") from None


@router.get("/api/desk/day")
def day(
    date_: str | None = Query(None, alias="date"), conn: db.Conn = Depends(require_bookings)
) -> dict:
    d = _day(date_)
    grid = bk.day_grid(conn, cs.load(conn), d)
    today = config.now().date()
    label = {0: "Today", 1: "Tomorrow", -1: "Yesterday"}.get((d - today).days, d.strftime("%A"))
    return {**grid, "label": label, "long": spoken_date(d), "short": short_date(d)}


def _booking_error(e: bk.BookingError, s: dict) -> ApiError:
    """One mapping from booking errors to the page's error shape. Whenever the booking service found
    free times nearby (a taken slot, a closed day, a time that isn't a slot start), the page gets
    them both in words and as `alternatives`, so the receptionist never has to guess."""
    status, code = {"SLOT_TAKEN": (409, "SLOT_TAKEN"), "NOT_FOUND": (404, "NOT_FOUND")}.get(
        e.code, (422, "VALIDATION")
    )
    alts = e.alternatives[:3]
    said = ", ".join(f"{spoken_time(a.time)} {cs.doctor_name(s, a.resource_id)}" for a in alts)
    detail = "That slot isn't free." if e.code == "SLOT_TAKEN" or alts else f"{str(e).rstrip('.')}."
    return ApiError(
        status,
        code,
        detail + (f" Free nearby: {said}." if said else ""),
        alternatives=[
            {"doctor_id": a.resource_id, "date": a.date.isoformat(), "time": a.time} for a in alts
        ],
    )


class WalkIn(BaseModel):
    doctor_id: str
    date: str
    time: str
    name: str = Field(min_length=1, max_length=80)
    phone: str | None = None
    source: str = "walk_in"


@router.post("/api/desk/bookings")
def add_booking(body: WalkIn, conn: db.Conn = Depends(require_bookings)) -> dict:
    phone = ph.normalize(body.phone) if body.phone else None
    if body.phone and not phone:
        raise ApiError(
            422,
            "VALIDATION",
            "Phone must be a 10-digit Indian mobile number.",
            fields={"phone": "Phone must be a 10-digit Indian mobile number."},
        )
    if body.source not in ("walk_in", "whatsapp"):
        raise ApiError(422, "VALIDATION", "Source must be walk_in or whatsapp.")
    s = cs.load(conn)
    try:
        bid = bk.book(
            conn, s, body.doctor_id, _day(body.date), body.time, body.name, phone, body.source
        )
    except bk.BookingError as e:
        raise _booking_error(e, s) from e
    return {"id": bid}


class StatusChange(BaseModel):
    status: str


@router.post("/api/desk/bookings/{booking_id}/status")
def set_status(
    booking_id: int, body: StatusChange, conn: db.Conn = Depends(require_bookings)
) -> dict:
    try:
        bk.set_status(conn, booking_id, body.status)
    except bk.BookingError as e:
        raise _booking_error(e, cs.load(conn)) from e
    return {"ok": True}


@router.get("/api/inbox")
def get_inbox(conn: db.Conn = Depends(get_user_conn)) -> list[dict]:
    return inbox.open_items(conn)


@router.post("/api/inbox/{item_id}/done")
def inbox_done(item_id: int, conn: db.Conn = Depends(get_user_conn)) -> dict:
    if not inbox.mark_done(conn, item_id):
        raise ApiError(404, "NOT_FOUND", "Already done or not found.")
    return {"ok": True}


@router.get("/api/calls")
def recent_calls(conn: db.Conn = Depends(get_user_conn)) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM calls WHERE tenant_id = ? ORDER BY started_at DESC LIMIT 25", (conn.tid,)
    ).fetchall()
    out = []
    for r in rows:
        c = dict(r)
        c["safety_hits"] = json.loads(c["safety_hits"]) if c["safety_hits"] else []
        out.append(c)
    return out


@router.get("/api/stats")
def stats(conn: db.Conn = Depends(get_user_conn)) -> dict:
    st = summary.day_stats(conn, config.now().date())
    return {**st, "sentence": summary.stats_sentence(st)}


@router.post("/api/desk/summary/send")
def send_summary(conn: db.Conn = Depends(get_user_conn)) -> dict:
    s = cs.load(conn)
    today = config.now().date()
    text = summary.summary_text(s["name"], today, summary.day_stats(conn, today))
    if not alerts.recipients(s):
        return {
            "sent": 0,
            "text": text,
            "note": "No WhatsApp numbers in settings. Add them on the settings page.",
        }
    sent = alerts.broadcast(s, text)
    note = None if sent else "Twilio isn't configured or the send failed; check the server log."
    return {"sent": sent, "text": text, "note": note}

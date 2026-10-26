"""Receptionist desk: pages and APIs behind DESK_PASSWORD (C7, C10)."""
import json
import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .. import inbox
from ..booking import service as bk
from ..booking.when import short_date, spoken_date, spoken_time
from ..channels.whatsapp import alerts, summary
from ..core import config
from ..core import phone as ph
from ..core import settings as cs
from ..core.config import FRONTEND_DIR, env
from ..providers.messaging import twilio_whatsapp
from .deps import get_conn, require_staff

router = APIRouter(dependencies=[Depends(require_staff)])


@router.get("/desk", include_in_schema=False)
def desk_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "desk.html")


@router.get("/api/staff/meta")
def meta(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    s = cs.load(conn)
    return {
        "clinic": s["name"], "city": s.get("city", ""),
        "authOpen": not env("DESK_PASSWORD"),
        "twilio": twilio_whatsapp.configured(),
        "whatsappNumbers": len(alerts.recipients(s)),
        "today": config.now().date().isoformat(),
    }


def _day(value: str | None) -> date:
    try:
        return date.fromisoformat(value) if value else config.now().date()
    except ValueError:
        raise HTTPException(400, "Date must be YYYY-MM-DD")


@router.get("/api/desk/day")
def day(date_: str | None = Query(None, alias="date"), conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    d = _day(date_)
    grid = bk.day_grid(conn, cs.load(conn), d)
    today = config.now().date()
    label = {0: "Today", 1: "Tomorrow", -1: "Yesterday"}.get((d - today).days, d.strftime("%A"))
    return {**grid, "label": label, "long": spoken_date(d), "short": short_date(d)}


class WalkIn(BaseModel):
    doctor_id: str
    date: str
    time: str
    name: str = Field(min_length=1, max_length=80)
    phone: str | None = None
    source: str = "walk_in"


@router.post("/api/desk/bookings")
def add_booking(body: WalkIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    phone = ph.normalize(body.phone) if body.phone else None
    if body.phone and not phone:
        raise HTTPException(422, "Phone must be a 10-digit Indian mobile number.")
    if body.source not in ("walk_in", "whatsapp"):
        raise HTTPException(422, "Source must be walk_in or whatsapp.")
    s = cs.load(conn)
    try:
        bid = bk.book(conn, s, body.doctor_id, _day(body.date), body.time, body.name, phone, body.source)
    except bk.BookingError as e:
        alt = ", ".join(f"{spoken_time(a.time)} {cs.doctor_name(s, a.resource_id)}" for a in e.alternatives[:3])
        status = 409 if e.code == "SLOT_TAKEN" else 422
        raise HTTPException(status, "That slot isn't free." + (f" Free nearby: {alt}." if alt else ""))
    return {"id": bid}


class StatusChange(BaseModel):
    status: str


@router.post("/api/desk/bookings/{booking_id}/status")
def set_status(booking_id: int, body: StatusChange, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    try:
        bk.set_status(conn, booking_id, body.status)
    except bk.BookingError as e:
        raise HTTPException(409 if e.code == "SLOT_TAKEN" else 422, str(e))
    return {"ok": True}


@router.get("/api/desk/inbox")
def get_inbox(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return inbox.open_items(conn)


@router.post("/api/desk/inbox/{item_id}/done")
def inbox_done(item_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    if not inbox.mark_done(conn, item_id):
        raise HTTPException(404, "Already done or not found.")
    return {"ok": True}


@router.get("/api/desk/calls")
def recent_calls(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    rows = conn.execute("SELECT * FROM calls ORDER BY started_at DESC LIMIT 25").fetchall()
    out = []
    for r in rows:
        c = dict(r)
        c["safety_hits"] = json.loads(c["safety_hits"]) if c["safety_hits"] else []
        out.append(c)
    return out


@router.get("/api/desk/stats")
def stats(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    st = summary.day_stats(conn, config.now().date())
    return {**st, "sentence": summary.stats_sentence(st)}


@router.post("/api/desk/summary/send")
def send_summary(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    s = cs.load(conn)
    today = config.now().date()
    text = summary.summary_text(s["name"], today, summary.day_stats(conn, today))
    if not alerts.recipients(s):
        return {"sent": 0, "text": text, "note": "No WhatsApp numbers in settings. Add them on the setup page."}
    sent = alerts.broadcast(s, text)
    note = None if sent else "Twilio isn't configured or the send failed; check the server log."
    return {"sent": sent, "text": text, "note": note}

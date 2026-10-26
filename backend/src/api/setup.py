"""Clinic settings page and API (C12). Saving re-syncs the voice agent and reports the result."""
import re
import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from ..booking import service as bk
from ..booking.when import short_date, spoken_time
from ..core import config
from ..core import phone as ph
from ..core import settings as cs
from ..core.config import FRONTEND_DIR
from .deps import get_conn, require_staff
from .sync import agent_configured, sync_agent

router = APIRouter(dependencies=[Depends(require_staff)])
HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class Doctor(BaseModel):
    id: str | None = None
    name: str = Field(min_length=2, max_length=60)


class Service(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    fee: str = Field(min_length=1, max_length=40)


class Faq(BaseModel):
    q: str = Field(min_length=2, max_length=200)
    a: str = Field(min_length=1, max_length=400)


class SettingsIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    city: str = Field(default="", max_length=60)
    address: str = Field(min_length=2, max_length=200)
    landmark: str = Field(default="", max_length=120)
    sessions: list[tuple[str, str]] = Field(min_length=1, max_length=4)
    closed_weekdays: list[int] = []
    slot_min: int = Field(ge=10, le=120)
    doctors: list[Doctor] = Field(min_length=1, max_length=8)
    services: list[Service] = []
    faqs: list[Faq] = []
    red_flags: list[str] = []
    emergency_instruction: str = Field(min_length=10, max_length=600)
    whatsapp_numbers: list[str] = []
    voice: str = "female"

    @field_validator("sessions")
    @classmethod
    def _sessions(cls, v):
        for start, end in v:
            if not (HHMM.match(start) and HHMM.match(end)) or start >= end:
                raise ValueError(f"Clinic hours '{start}-{end}' must look like 10:00-14:00, start before end.")
        return sorted(v)

    @field_validator("closed_weekdays")
    @classmethod
    def _weekdays(cls, v):
        if any(d not in range(7) for d in v):
            raise ValueError("Closed days must be 0 (Monday) to 6 (Sunday).")
        return sorted(set(v))

    @field_validator("whatsapp_numbers")
    @classmethod
    def _numbers(cls, v):
        out = []
        for raw in v:
            if not raw.strip():
                continue
            n = ph.normalize(raw)
            if not n:
                raise ValueError(f"'{raw}' is not a 10-digit Indian mobile number.")
            out.append(n)
        return sorted(set(out))

    @field_validator("voice")
    @classmethod
    def _voice(cls, v):
        if v not in ("female", "male"):
            raise ValueError("Voice must be female or male.")
        return v


def _slug(name: str, taken: set[str]) -> str:
    base = "dr-" + (re.sub(r"[^a-z0-9]+", "-", name.lower().replace("dr.", "").replace("dr ", "")).strip("-") or "x")
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    return slug


@router.get("/setup", include_in_schema=False)
def setup_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "setup.html")


def _blocks(conn: sqlite3.Connection, s: dict) -> list[dict]:
    out = []
    for b in bk.list_blocks(conn):
        d = date.fromisoformat(b["date"])
        what = {"leave": "Leave", "holiday": "Clinic closed", "late_start": f"In from {spoken_time(b['end'] or '00:00')}",
                "early_close": f"Leaves at {spoken_time(b['start'] or '23:59')}"}.get(b["kind"], b["kind"])
        out.append({**b, "label": f"{short_date(d)} · {cs.doctor_name(s, b['resource_id']) if b['resource_id'] else 'Whole clinic'} · {what}"})
    return out


@router.get("/api/setup")
def get_setup(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    s = cs.load(conn)
    return {"settings": s, "blocks": _blocks(conn, s), "agentConfigured": agent_configured()}


@router.put("/api/setup")
def save_setup(body: SettingsIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    s = cs.load(conn)
    old_ids = {d["id"] for d in s["doctors"]}
    doctors, taken = [], set()
    for d in body.doctors:
        did = d.id if d.id and re.fullmatch(r"[a-z0-9-]{1,40}", d.id) else _slug(d.name, taken | old_ids)
        if did in taken:
            raise HTTPException(422, f"Two doctors share the id '{did}'.")
        taken.add(did)
        prev = cs.doctor(s, did) or {}
        doctors.append({**prev, "id": did, "name": d.name.strip()})
    today = config.now().date().isoformat()
    for gone in old_ids - taken:
        n = conn.execute("SELECT COUNT(*) FROM bookings WHERE resource_id = ? AND date >= ? AND status = 'booked'",
                         (gone, today)).fetchone()[0]
        if n:
            raise HTTPException(422, f"{cs.doctor_name(s, gone)} has {n} upcoming booking(s). Move or cancel them before removing the doctor.")
    s.update(body.model_dump(exclude={"doctors"}))
    s["doctors"] = doctors
    s["sessions"] = [list(x) for x in body.sessions]
    s["red_flags"] = [r.strip() for r in body.red_flags if r.strip()]
    cs.save(conn, s)
    return {"ok": True, "agent": sync_agent(), "settings": s}


class BlockIn(BaseModel):
    date: str
    doctor_id: str | None = None


@router.post("/api/setup/blocks")
def add_block(body: BlockIn, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    s = cs.load(conn)
    try:
        d = date.fromisoformat(body.date)
    except ValueError:
        raise HTTPException(422, "Pick a date.")
    if d < config.now().date():
        raise HTTPException(422, "That date has passed.")
    if body.doctor_id and not cs.doctor(s, body.doctor_id):
        raise HTTPException(422, "Unknown doctor.")
    affected = bk.affected_bookings(conn, s, d, body.doctor_id)
    bk.add_block(conn, d, "leave" if body.doctor_id else "holiday", "setup", body.doctor_id)
    note = f"{len(affected)} booking(s) that day still stand; the desk shows them so staff can move them." if affected else None
    return {"blocks": _blocks(conn, s), "note": note, "agent": sync_agent()}


@router.delete("/api/setup/blocks/{block_id}")
def delete_block(block_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    bk.remove_block(conn, block_id)
    s = cs.load(conn)
    return {"blocks": _blocks(conn, s), "agent": sync_agent()}

"""Public routes: the Try-it page, its config and the clinic register shown beside the call."""
import sqlite3
from datetime import timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from ..booking import service as bk
from ..booking.when import short_date, spoken_date
from ..core import config
from ..core import settings as cs
from ..core.config import FRONTEND_DIR, env
from .deps import get_conn

router = APIRouter()


@router.get("/", include_in_schema=False)
def try_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@router.get("/api/public-config")
def public_config(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    s = cs.load(conn)
    missing = [k for k in ("VAPI_PUBLIC_KEY", "VAPI_ASSISTANT_ID") if not env(k)]
    return {
        "publicKey": env("VAPI_PUBLIC_KEY"),
        "assistantId": env("VAPI_ASSISTANT_ID"),
        "missing": missing,
        "clinic": {"name": s["name"], "city": s.get("city", ""), "address": s["address"]},
    }


def _mask(name: str) -> str:
    """Public page shows 'Ramesh G.', never a full name or phone."""
    parts = name.split()
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][0]}."


@router.get("/api/register")
def register(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    """Today and tomorrow, per doctor, with masked names."""
    s = cs.load(conn)
    today = config.now().date()
    days = []
    for d in (today, today + timedelta(days=1)):
        grid = bk.day_grid(conn, s, d)
        cols = []
        for col in grid["columns"]:
            slots = []
            for sl in col["slots"]:
                b = next((x for x in sl["bookings"] if x["status"] in bk.ACTIVE), None)
                slots.append({
                    "time": sl["time"], "state": sl["state"], "past": sl["past"], "block": sl["block"],
                    "booking": {"id": b["id"], "name": _mask(b["name"]), "source": b["source"]} if b else None,
                })
            cols.append({"doctor": col["doctor"]["name"], "slots": slots})
        label = "Today" if d == today else "Tomorrow"
        days.append({"date": d.isoformat(), "label": label, "short": short_date(d), "long": spoken_date(d),
                     "closed": grid["closed"], "columns": cols})
    return {"clinic": s["name"], "days": days}

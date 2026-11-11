"""Public routes: the Try-it page, its config and the clinic register shown beside the call."""

from datetime import timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from ..booking import service as bk
from ..booking.when import short_date, spoken_date
from ..core import config, db
from ..core import settings as cs
from ..core.config import FRONTEND_DIR, env
from .deps import get_conn

router = APIRouter()


@router.get("/", include_in_schema=False)
def try_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@router.get("/api/public-config")
def public_config(conn: db.Conn = Depends(get_conn)) -> dict:
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


def masked_days(conn: db.Conn, s: dict, resource_key: str = "doctor") -> list[dict]:
    """Today and tomorrow, one column per resource, with masked names and no phones. Shared by the
    old try page and /api/try/{public_id}/board."""
    today = config.now().date()
    days = []
    for d in (today, today + timedelta(days=1)):
        grid = bk.day_grid(conn, s, d)
        cols = []
        for col in grid["columns"]:
            slots = []
            for sl in col["slots"]:
                b = next((x for x in sl["bookings"] if x["status"] in bk.ACTIVE), None)
                slots.append(
                    {
                        "time": sl["time"],
                        "state": sl["state"],
                        "past": sl["past"],
                        "block": sl["block"],
                        "booking": (
                            {"id": b["id"], "name": _mask(b["name"]), "source": b["source"]}
                            if b
                            else None
                        ),
                    }
                )
            cols.append({resource_key: col["doctor"]["name"], "slots": slots})
        days.append(
            {
                "date": d.isoformat(),
                "label": "Today" if d == today else "Tomorrow",
                "short": short_date(d),
                "long": spoken_date(d),
                "closed": grid["closed"],
                "columns": cols,
            }
        )
    return days


@router.get("/api/register")
def register(conn: db.Conn = Depends(get_conn)) -> dict:
    """The old demo try page's register. Replaced by /api/try/{public_id}/board."""
    s = cs.load(conn)
    return {"clinic": s["name"], "days": masked_days(conn, s)}

"""The public, per-business test page's API (contracts.md §6.1, issue #24): page info, the call-cap
check before a web call, and the live register or order board.

Public: no login. The business comes from `public_id`. Names are masked and phone numbers never
leave this module.
"""

from collections.abc import Iterator
from datetime import timedelta

from fastapi import APIRouter, Depends

from ..core import config, db, tenancy
from ..core import settings as cs
from ..core.config import env
from ..orders import service as orders
from ..providers.voice_orchestrator import vapi
from ..verticals import loader
from .deps import require_csrf_header
from .errors import ApiError
from .public import mask, masked_days
from .sync import uses_env_assistant

router = APIRouter(dependencies=[Depends(require_csrf_header)])

CALL_EVENT = "web_call_started"
DEMO_CALLS_PER_DAY = 20
CALLS_PER_BUSINESS_PER_DAY = 10


def get_public_conn(public_id: str) -> Iterator[db.Conn]:
    """A connection scoped to the business named in the URL. Unknown id is 404 (these pages are
    meant to be shared, so there is nothing to hide about which ids exist)."""
    conn = db.connect()
    try:
        t = tenancy.by_public_id(conn, public_id)
        if t is None:
            raise ApiError(404, "NOT_FOUND", "We couldn't find that business. Check the link.")
        yield conn.for_tenant(t["id"])
    finally:
        conn.close()


def voice(conn: db.Conn, t: db.Row) -> dict | None:
    """What the browser needs to start a web call to this business's assistant, or None.

    The assistant is the business's own (its row); for the demo clinic only, while its row has none,
    the original one in .env (contracts.md §1.10)."""
    public_key = env("VAPI_PUBLIC_KEY")
    assistant = t["vapi_assistant_id"] or (
        env("VAPI_ASSISTANT_ID") if uses_env_assistant(conn, t) else ""
    )
    if not (public_key and assistant):
        return None
    return {"public_key": public_key, "assistant_id": assistant}


@router.get("/api/try/{public_id}")
def info(public_id: str, conn: db.Conn = Depends(get_public_conn)) -> dict:
    t = tenancy.get(conn, conn.tid)
    s = cs.load(conn)
    return {
        "public_id": t["public_id"],
        "name": s["name"],
        "city": s.get("city", ""),
        "template": t["template"],
        "modules": loader.modules(t["template"]),
        "labels": s.get("labels", {}),
        "voice": voice(conn, t),
        "try_saying": loader.try_saying(t["template"]),
    }


def _cap(name: str, default: int) -> int:
    raw = env(name)
    return int(raw) if raw.isdigit() else default


def _day_bounds() -> tuple[str, str]:
    """Today in IST as [start, end) stamps, comparable with `db.stamp()` text."""
    today = config.now().date()
    return today.isoformat(), (today + timedelta(days=1)).isoformat()


def _calls_today(conn: db.Conn, tenant_id: str | None) -> int:
    start, end = _day_bounds()
    sql = "SELECT COUNT(*) FROM events WHERE type = ? AND created_at >= ? AND created_at < ?"
    params: tuple = (CALL_EVENT, start, end)
    if tenant_id is not None:
        sql += " AND tenant_id = ?"
        params += (tenant_id,)
    return conn.execute(sql, params).fetchone()[0]


@router.post("/api/try/{public_id}/start")
def start(public_id: str, conn: db.Conn = Depends(get_public_conn)) -> dict:
    """The call-cap check before the browser starts a web call (contracts.md §1.10). Counts the call
    when it allows it. There is no Vapi budget, so the caps are what keep the demo minutes in check.
    """
    t = tenancy.get(conn, conn.tid)
    if voice(conn, t) is None:
        raise ApiError(
            503, "VOICE_NOT_CONFIGURED", "This business's voice agent isn't switched on yet."
        )
    used_up = ApiError(
        429, "MINUTES_USED_UP", "Today's free demo minutes are used up. Please try again tomorrow."
    )
    per_business = _cap("CALLS_PER_BUSINESS_PER_DAY", CALLS_PER_BUSINESS_PER_DAY)
    overall = _cap("DEMO_CALLS_PER_DAY", DEMO_CALLS_PER_DAY)
    if _calls_today(conn, conn.tid) >= per_business:
        raise used_up
    everyone = db.connect_unchecked()  # the overall cap counts every business's calls
    try:
        if _calls_today(everyone, None) >= overall:
            raise used_up
    finally:
        everyone.close()
    with conn:
        conn.execute(
            "INSERT INTO events (tenant_id, type, created_at) VALUES (?, ?, ?)",
            (conn.tid, CALL_EVENT, db.stamp()),
        )
    return {"max_call_seconds": vapi.max_call_seconds()}


@router.get("/api/try/{public_id}/board")
def board(public_id: str, conn: db.Conn = Depends(get_public_conn)) -> dict:
    """Today's register (bookings) or order board (orders), with masked names and no phones. Polled
    every few seconds during a call, so it reads only today and tomorrow."""
    t = tenancy.get(conn, conn.tid)
    if "bookings" in loader.modules(t["template"]):
        days = masked_days(conn, cs.load(conn), resource_key="resource")
        for d in days:
            d.pop("long", None)
            for col in d["columns"]:
                col["slots"] = [
                    {"time": sl["time"], "state": sl["state"], "booking": sl["booking"]}
                    for sl in col["slots"]
                ]
        return {"kind": "bookings", "days": days}
    today = config.now().date().isoformat()
    return {
        "kind": "orders",
        "orders": [
            {
                "id": o["id"],
                "number": str(o["number"]),
                "shop": mask(o["shop_name"]),
                "items": len(o["items"]),
                "total": o["total"],
                "status": o["status"],
                "source": o["source"],
                "created_at": o["created_at"],
            }
            for o in orders.list_orders(conn, day=today)
        ],
    }

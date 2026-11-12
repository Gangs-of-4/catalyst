"""Owner custom instructions for the logged-in business (contracts.md §6.1, Phase 2 M5).

Each save is screened line by line, kept as a new version, and re-syncs only this business's
assistant. Undo brings the previous version back.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..agents import instructions
from ..core import db
from .deps import get_user_conn, require_csrf_header
from .errors import ApiError
from .sync import sync_agent

router = APIRouter(dependencies=[Depends(require_csrf_header)])


class InstructionsIn(BaseModel):
    text: str = Field(default="", max_length=instructions.MAX_CHARS)


@router.get("/api/instructions")
def get_instructions(conn: db.Conn = Depends(get_user_conn)) -> dict:
    now = instructions.current(conn)
    return {
        "text": now["text"] if now else "",
        "version_id": now["id"] if now else None,
        "rejected": now["rejected"] if now else [],
        "max_chars": instructions.MAX_CHARS,
        "history": instructions.history(conn),
    }


@router.put("/api/instructions")
def save_instructions(body: InstructionsIn, conn: db.Conn = Depends(get_user_conn)) -> dict:
    """Saves the accepted lines; reports each rejected line with its reason. If every line is
    rejected nothing changes (`version_id` null)."""
    try:
        version_id, screened = instructions.save(conn, body.text, "web")
    except instructions.TooLong as e:
        raise ApiError(422, "VALIDATION", str(e), fields={"text": str(e)}) from e
    agent = (
        sync_agent(conn.tid)
        if version_id is not None
        else "Nothing was saved: every line was rejected."
    )
    return {
        "accepted": screened.accepted,
        "rejected": screened.rejected,
        "version_id": version_id,
        "agent": agent,
    }


@router.post("/api/instructions/undo")
def undo_instructions(conn: db.Conn = Depends(get_user_conn)) -> dict:
    back = instructions.undo(conn)
    if back is None:
        raise ApiError(404, "NOT_FOUND", "There is nothing to undo.")
    return {"text": back["text"], "version_id": back["id"], "agent": sync_agent(conn.tid)}

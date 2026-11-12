"""In-app feedback from a logged-in owner (contracts.md §6.1, Phase 2 M7). Our team reviews it on
the admin page and records a decision (api/admin.py)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from .. import accounts, analytics
from ..core import db
from .deps import current_session, get_user_conn, require_csrf_header

router = APIRouter(dependencies=[Depends(require_csrf_header)])

TYPES = ("bug", "feature", "usability", "data_integration", "pricing_business")


class FeedbackIn(BaseModel):
    person_name: str = Field(min_length=1, max_length=80)
    person_role: str = Field(min_length=1, max_length=60)
    text: str = Field(min_length=3, max_length=2000)
    type: str

    @field_validator("type")
    @classmethod
    def _type(cls, v: str) -> str:
        if v not in TYPES:
            raise ValueError(f"Type must be one of: {', '.join(TYPES)}.")
        return v


@router.post("/api/feedback")
def send_feedback(
    body: FeedbackIn,
    session: accounts.Session = Depends(current_session),
    conn: db.Conn = Depends(get_user_conn),
) -> dict:
    with conn:
        row = conn.execute(
            "INSERT INTO feedback (tenant_id, person_name, person_role, text, type, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
            (
                conn.tid,
                body.person_name.strip(),
                body.person_role.strip(),
                body.text.strip(),
                body.type,
                db.stamp(),
            ),
        ).fetchone()
        analytics.record(conn, "feedback_sent", session.user_id, commit=False)
    return {"id": row["id"], "saved": True}

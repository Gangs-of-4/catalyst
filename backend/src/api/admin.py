"""Admin pages' API for our team (contracts.md §6.1–§6.2, Phase 2 M7): every business's usage
evidence (counts only), and the feedback log with decisions.

Admin login is one shared password (ADMIN_PASSWORD; unset = no admin), its own cookie and session
kind. These routes read across businesses, so they use unchecked connections: the cross-business
admin counts the tenancy guard documents as allowed.
"""

import csv
import io
import re
from datetime import date

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from .. import accounts, analytics
from ..core import db, tenancy
from .deps import cookie_secure, require_csrf_header
from .errors import ApiError
from .feedback import TYPES

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_csrf_header)])
DECISIONS = ("shipped", "in_progress", "planned", "wont_do")
DECISION_WORDS = {
    "shipped": "Shipped",
    "in_progress": "In progress",
    "planned": "Planned",
    "wont_do": "Won't do",
}
TYPE_WORDS = {
    "bug": "Bug",
    "feature": "Feature",
    "usability": "Usability",
    "data_integration": "Data / integration",
    "pricing_business": "Pricing / business",
}
FEEDBACK_COLUMNS = (
    "Date",
    "Partner and person",
    "What they said",
    "Type",
    "Decision",
    "Shipped on",
    "Evidence",
    "Partner's reaction",
)


def require_admin(request: Request) -> None:
    conn = db.connect_unchecked()
    try:
        ok = accounts.is_admin(conn, request.cookies.get(accounts.ADMIN_COOKIE))
    finally:
        conn.close()
    if not ok:
        raise ApiError(401, "UNAUTHENTICATED", "Please log in as admin to continue.")


class AdminLoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


@router.post("/login")
def admin_login(body: AdminLoginIn, request: Request, response: Response) -> dict:
    conn = db.connect_unchecked()
    try:
        cookie = accounts.admin_login(conn, body.password)
    except accounts.Locked:
        raise ApiError(
            429, "LOCKED", "Too many wrong passwords. Try again in 15 minutes."
        ) from None
    except accounts.BadLogin:
        raise ApiError(401, "UNAUTHENTICATED", "That password isn't right.") from None
    finally:
        conn.close()
    response.set_cookie(
        accounts.ADMIN_COOKIE,
        cookie,
        max_age=accounts.ADMIN_HOURS * 3600,
        httponly=True,
        secure=cookie_secure(request),
        samesite="lax",
        path="/",
    )
    return {"ok": True}


def _businesses(conn: db.Conn) -> list[db.Row]:
    return conn.execute("SELECT * FROM tenants ORDER BY created_at, id").fetchall()


@router.get("/businesses", dependencies=[Depends(require_admin)])
def businesses() -> dict:
    conn = db.connect_unchecked()
    try:
        return {
            "businesses": [
                analytics.business(conn.for_tenant(t["id"]), t) for t in _businesses(conn)
            ]
        }
    finally:
        conn.close()


@router.get("/businesses/{tenant_id}/usage.csv", dependencies=[Depends(require_admin)])
def usage_csv(tenant_id: str) -> Response:
    conn = db.connect_unchecked()
    try:
        t = tenancy.get(conn, tenant_id)
        if t is None:
            raise ApiError(404, "NOT_FOUND", "No such business.")
        text = analytics.usage_csv(conn.for_tenant(tenant_id))
    finally:
        conn.close()
    name = re.sub(r"[^a-z0-9]+", "-", t["public_id"].lower()).strip("-") or "business"
    return Response(
        text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="usage-{name}.csv"'},
    )


def _feedback_rows(conn: db.Conn) -> list[dict]:
    rows = conn.execute(
        "SELECT f.*, t.name AS business FROM feedback f JOIN tenants t ON t.id = f.tenant_id"
        " ORDER BY f.created_at DESC, f.id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/feedback", dependencies=[Depends(require_admin)])
def feedback_list() -> dict:
    conn = db.connect_unchecked()
    try:
        return {"feedback": _feedback_rows(conn), "types": TYPES, "decisions": DECISIONS}
    finally:
        conn.close()


class DecisionIn(BaseModel):
    decision: str | None = None
    decision_reason: str = Field(default="", max_length=500)
    shipped_on: str | None = None
    evidence_url: str = Field(default="", max_length=500)
    partner_reaction: str = Field(default="", max_length=1000)


@router.put("/feedback/{feedback_id}", dependencies=[Depends(require_admin)])
def feedback_decide(feedback_id: int, body: DecisionIn) -> dict:
    fields: dict[str, str] = {}
    if body.decision is not None and body.decision not in DECISIONS:
        fields["decision"] = f"Decision must be one of: {', '.join(DECISIONS)}."
    if body.decision == "wont_do" and not body.decision_reason.strip():
        fields["decision_reason"] = "Say why it won't be done."
    if body.shipped_on:
        try:
            date.fromisoformat(body.shipped_on)
        except ValueError:
            fields["shipped_on"] = "Shipped on must look like 2026-11-15."
    if body.evidence_url and not re.match(r"^https?://\S+$", body.evidence_url.strip()):
        fields["evidence_url"] = "Evidence must be a link starting with https://."
    if fields:
        raise ApiError(422, "VALIDATION", " ".join(fields.values()), fields)
    conn = db.connect_unchecked()
    try:
        with conn:
            n = conn.execute(
                "UPDATE feedback SET decision = ?, decision_reason = ?, shipped_on = ?,"
                " evidence_url = ?, partner_reaction = ? WHERE id = ?",
                (
                    body.decision,
                    body.decision_reason.strip() or None,
                    body.shipped_on or None,
                    body.evidence_url.strip() or None,
                    body.partner_reaction.strip() or None,
                    feedback_id,
                ),
            ).rowcount
        if n != 1:
            raise ApiError(404, "NOT_FOUND", "No such feedback.")
        row = next(r for r in _feedback_rows(conn) if r["id"] == feedback_id)
    finally:
        conn.close()
    return row


@router.get("/feedback.csv", dependencies=[Depends(require_admin)])
def feedback_csv() -> Response:
    """Newest first, in the columns of the team's feedback Google Sheet (contracts.md §6.2)."""
    conn = db.connect_unchecked()
    try:
        rows = _feedback_rows(conn)
    finally:
        conn.close()
    buf = io.StringIO()
    out = csv.writer(buf, lineterminator="\n")
    out.writerow(FEEDBACK_COLUMNS)
    for r in rows:
        decision = DECISION_WORDS.get(r["decision"] or "", "")
        if r["decision"] == "wont_do" and r["decision_reason"]:
            decision += f": {r['decision_reason']}"
        out.writerow(
            [
                r["created_at"][:10],
                f"{r['business']} — {r['person_name']} ({r['person_role']})",
                r["text"],
                TYPE_WORDS.get(r["type"], r["type"]),
                decision,
                r["shipped_on"] or "",
                r["evidence_url"] or "",
                r["partner_reaction"] or "",
            ]
        )
    return Response(
        buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="feedback.csv"'},
    )

"""Time in the app (issue #56; contracts.md §6.2): the React app sends `POST /api/activity` once a
minute while a logged-in owner is using it. No body: the business and the person come from the
session, never from the request. Counts only, for the admin dashboard."""

from fastapi import APIRouter, Depends, Response

from .. import accounts, analytics
from ..core import db
from .deps import current_session, require_csrf_header

router = APIRouter(dependencies=[Depends(require_csrf_header)])


@router.post("/api/activity", status_code=204)
def activity(session: accounts.Session = Depends(current_session)) -> Response:
    conn = db.connect()
    try:
        analytics.ping(conn.for_tenant(session.tenant_id), session.user_id)
    finally:
        conn.close()
    return Response(status_code=204)

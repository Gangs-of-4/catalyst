"""Shared request dependencies: a DB connection per request, scoped to one business."""

import hmac
from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException, Request

from .. import accounts
from ..core import db, tenancy
from ..core.config import env
from ..verticals import loader
from .errors import ApiError


def get_conn() -> Iterator[db.Conn]:
    """A connection scoped to the public demo clinic.

    Transitional: only the old public try page (/api/public-config, /api/register; replaced by
    /api/try/{public_id}), the legacy Vapi webhook and WhatsApp (until M6 routes by sender) use it.
    The desk and settings use `get_user_conn`.
    """
    conn = db.connect()
    try:
        tid = tenancy.demo_id(conn, "clinic")
        if tid is None:
            raise HTTPException(503, "The demo clinic isn't set up yet. Restart the backend.")
        yield conn.for_tenant(tid)
    finally:
        conn.close()


def get_webhook_conn(
    public_id: str, x_catalyst_secret: str | None = Header(default=None)
) -> Iterator[db.Conn]:
    """A connection scoped to the business named in the webhook path (contracts.md §1.10).

    An unknown `public_id` and a missing or wrong secret are both 401, so the response doesn't tell a
    caller which business ids exist. The secret is the one stored on that business's own row, so
    business A's secret never authorises business B.
    """
    conn = db.connect()
    try:
        t = tenancy.by_public_id(conn, public_id)
        expected = (t["tool_secret"] or "") if t is not None else ""
        if not (
            expected
            and x_catalyst_secret
            and hmac.compare_digest(x_catalyst_secret.encode(), expected.encode())
        ):
            raise HTTPException(401, "Bad or missing x-catalyst-secret")
        yield conn.for_tenant(t["id"])
    finally:
        conn.close()


LOCAL_HOSTS = {"localhost", "127.0.0.1", "testserver"}


def require_csrf_header(request: Request) -> None:
    """Every write must carry `X-Requested-With: catalyst` (contracts.md §6). A cross-site form
    post can't set it, which together with SameSite=Lax blocks CSRF."""
    is_write = request.method in ("POST", "PUT", "DELETE", "PATCH")
    if is_write and request.headers.get("x-requested-with") != "catalyst":
        raise ApiError(403, "FORBIDDEN", "That request wasn't sent from the app. Reload the page.")


def cookie_secure(request: Request) -> bool:
    """Secure cookies everywhere except plain-http local development."""
    return (request.url.hostname or "") not in LOCAL_HOSTS


def current_session(request: Request) -> accounts.Session:
    """The logged-in owner, or 401. Auth lookups run before the business is known."""
    conn = db.connect_unchecked()
    try:
        found = accounts.lookup(conn, request.cookies.get(accounts.COOKIE))
    finally:
        conn.close()
    if found is None:
        raise ApiError(401, "UNAUTHENTICATED", "Please log in to continue.")
    return found


def get_user_conn(session: accounts.Session = Depends(current_session)) -> Iterator[db.Conn]:
    """A connection scoped to the logged-in owner's business."""
    conn = db.connect()
    try:
        yield conn.for_tenant(session.tenant_id)
    finally:
        conn.close()


def modules(conn: db.Conn) -> list[str]:
    """The business's desk modules from its template (vertical.yaml `modules`): bookings, orders."""
    return loader.modules(tenancy.get(conn, conn.tid)["template"])


def require_bookings(conn: db.Conn = Depends(get_user_conn)) -> db.Conn:
    """The session's business connection, for schedule routes. A business whose template has no
    bookings module (wholesale) gets 404: it has an order board instead (M4)."""
    if "bookings" not in modules(conn):
        raise ApiError(404, "NOT_FOUND", "This business doesn't keep a schedule.")
    return conn


def require_orders(conn: db.Conn = Depends(get_user_conn)) -> db.Conn:
    """The session's business connection, for catalogue and order routes. A business whose template
    has no orders module (a clinic) gets 404."""
    if "orders" not in modules(conn):
        raise ApiError(404, "NOT_FOUND", "This business doesn't take orders.")
    return conn


def secret_ok(given: str | None, name: str) -> bool:
    expected = env(name)
    return bool(expected and given) and hmac.compare_digest(given.encode(), expected.encode())

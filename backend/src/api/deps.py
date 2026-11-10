"""Shared request dependencies: a DB connection per request, and staff auth."""

import base64
import hmac
from collections.abc import Iterator

from fastapi import HTTPException, Request

from ..core import db, tenancy
from ..core.config import env


def get_conn() -> Iterator[db.Conn]:
    """A connection scoped to the public demo clinic.

    Transitional (Phase 2 M1): the desk, setup, try page, Vapi and WhatsApp routes still serve the
    single demo clinic. M2 scopes desk/setup to the logged-in business, M3 scopes the Vapi webhook by
    its path, and M6 scopes WhatsApp by the sender's number.
    """
    conn = db.connect()
    try:
        tid = tenancy.demo_id(conn, "clinic")
        if tid is None:
            raise HTTPException(503, "The demo clinic isn't set up yet. Restart the backend.")
        yield conn.for_tenant(tid)
    finally:
        conn.close()


def require_staff(request: Request) -> None:
    """HTTP Basic auth with DESK_PASSWORD (any username). Open, with a warning on the page, if unset."""
    password = env("DESK_PASSWORD")
    if not password:
        return
    header = request.headers.get("authorization", "")
    if header.lower().startswith("basic "):
        try:
            _, _, given = base64.b64decode(header[6:]).decode("utf-8").partition(":")
        except (ValueError, UnicodeDecodeError):
            given = ""
        if hmac.compare_digest(given.encode(), password.encode()):
            return
    raise HTTPException(
        401, "Password required", headers={"WWW-Authenticate": 'Basic realm="Clinic desk"'}
    )


def secret_ok(given: str | None, name: str) -> bool:
    expected = env(name)
    return bool(expected and given) and hmac.compare_digest(given.encode(), expected.encode())

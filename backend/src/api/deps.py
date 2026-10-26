"""Shared request dependencies: a DB connection per request, and staff auth."""
import base64
import hmac
import sqlite3
from typing import Iterator

from fastapi import HTTPException, Request

from ..core import db
from ..core.config import env


def get_conn() -> Iterator[sqlite3.Connection]:
    conn = db.connect()
    try:
        yield conn
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
    raise HTTPException(401, "Password required", headers={"WWW-Authenticate": 'Basic realm="Clinic desk"'})


def secret_ok(given: str | None, name: str) -> bool:
    expected = env(name)
    return bool(expected and given) and hmac.compare_digest(given.encode(), expected.encode())

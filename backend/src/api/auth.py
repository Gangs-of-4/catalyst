"""Login, logout and "who am I" for business owners (contracts.md §6)."""

import re

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from .. import accounts
from ..core import db, tenancy
from ..core import settings as cs
from .deps import cookie_secure, current_session, get_user_conn, require_csrf_header
from .errors import ApiError

router = APIRouter(prefix="/api", dependencies=[Depends(require_csrf_header)])
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def set_session_cookie(response: Response, request: Request, value: str) -> None:
    response.set_cookie(
        accounts.COOKIE,
        value,
        max_age=accounts.SESSION_DAYS * 86400,
        httponly=True,
        secure=cookie_secure(request),
        samesite="lax",
        path="/",
    )


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response) -> dict:
    conn = db.connect_unchecked()  # the email tells us which business; nothing is scoped yet
    try:
        cookie, _, tid = accounts.login(conn, body.email, body.password)
        business = tenancy.get(conn, tid)
    except accounts.Locked:
        raise ApiError(
            429, "LOCKED", "Too many wrong passwords. Please wait 15 minutes and try again."
        ) from None
    except accounts.BadLogin:
        raise ApiError(401, "UNAUTHENTICATED", "That email or password is wrong.") from None
    finally:
        conn.close()
    set_session_cookie(response, request, cookie)
    return {"public_id": business["public_id"], "template": business["template"]}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    conn = db.connect_unchecked()
    try:
        accounts.logout(conn, request.cookies.get(accounts.COOKIE))
    finally:
        conn.close()
    response.delete_cookie(accounts.COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(
    session: accounts.Session = Depends(current_session),
    conn: db.Conn = Depends(get_user_conn),
) -> dict:
    accounts.touch(conn, session.user_id)
    business = tenancy.get(conn, session.tenant_id)
    s = cs.load(conn)
    return {
        "user": {"name": session.name, "email": session.email},
        "business": {
            "name": business["name"],
            "template": business["template"],
            "public_id": business["public_id"],
            "labels": s.get("labels", {}),
        },
    }

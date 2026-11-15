"""Login, logout and "who am I" for business owners (contracts.md §6)."""

import re

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from .. import accounts, analytics
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
        cookie, uid, tid = accounts.login(conn, body.email, body.password)
        analytics.record(conn.for_tenant(tid), "login", uid)
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


class ProfileUpdateIn(BaseModel):
    name: str | None = None
    current_password: str | None = None
    new_password: str | None = None


@router.patch("/me")
def update_profile(
    body: ProfileUpdateIn,
    session: accounts.Session = Depends(current_session),
    conn: db.Conn = Depends(get_user_conn),
) -> dict:
    if body.new_password:
        if not body.current_password:
            raise ApiError(
                422,
                "VALIDATION",
                "Current password is required to set a new password.",
                {"current_password": "Enter your current password."},
            )
        if len(body.new_password) < accounts.MIN_PASSWORD:
            raise ApiError(
                422,
                "VALIDATION",
                f"Choose a password of at least {accounts.MIN_PASSWORD} characters.",
                {
                    "new_password": f"Choose a password of at least {accounts.MIN_PASSWORD} characters."
                },
            )
        try:
            accounts.change_password(
                conn, session.user_id, body.current_password, body.new_password
            )
        except accounts.WrongPassword:
            raise ApiError(
                401,
                "UNAUTHENTICATED",
                "Current password is incorrect.",
                {"current_password": "Current password is incorrect."},
            ) from None

    if body.name is not None:
        trimmed = body.name.strip()
        if len(trimmed) < 2 or len(trimmed) > 80:
            raise ApiError(
                422,
                "VALIDATION",
                "Name must be between 2 and 80 characters.",
                {"name": "Name must be between 2 and 80 characters."},
            )
        accounts.update_name(conn, session.user_id, trimmed)

    accounts.touch(conn, session.user_id)
    row = conn.execute(
        "SELECT name, email FROM users WHERE tenant_id = ? AND id = ?",
        (conn.tid, session.user_id),
    ).fetchone()
    analytics.record(conn, "profile_updated", session.user_id)
    return {"user": {"name": row["name"], "email": row["email"]}}

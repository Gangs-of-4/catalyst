"""Owner accounts: scrypt passwords, signed session cookies, login lockout (ADR-0038, contracts.md §6).

Auth lookups run before the business is known (the session or the email *tells* us which business),
so they use `db.connect_unchecked()`. Everything after login goes through a connection scoped with
`for_tenant`.
"""

import base64
import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from ..core import config, db
from ..core.config import env, set_env
from ..core.log import log

COOKIE = "catalyst_session"
SESSION_DAYS = 30
MAX_FAILED = 5
LOCK_MINUTES = 15
MIN_PASSWORD = 8
_N, _R, _P = 2**14, 8, 1


class EmailTaken(Exception):
    pass


class BadLogin(Exception):
    """Wrong email or password. Deliberately the same for both, so emails can't be probed."""


class Locked(Exception):
    pass


@dataclass(frozen=True)
class Session:
    user_id: str
    tenant_id: str
    name: str
    email: str


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"scrypt${_N}${_R}${_P}${b64(salt)}${b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, digest = stored.split("$")
        expected = base64.b64decode(digest)
        got = hashlib.scrypt(
            password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, expected)


_DUMMY_HASH = hash_password("not-a-real-password")  # so an unknown email costs the same time


def normalize_email(email: str) -> str:
    return email.strip().lower()


def session_secret() -> bytes:
    """SESSION_SECRET from the environment. If unset, make one and keep it in `.env` (local dev).
    On a host with an ephemeral disk set it in the dashboard, or every restart logs people out."""
    value = env("SESSION_SECRET")
    if not value:
        value = secrets.token_urlsafe(32)
        set_env({"SESSION_SECRET": value})
        log.warning("accounts: SESSION_SECRET was not set; generated one in .env")
    return value.encode()


def _sign(token: str) -> str:
    return hmac.new(session_secret(), token.encode(), hashlib.sha256).hexdigest()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _later(**delta) -> str:
    return (config.now() + timedelta(**delta)).isoformat(timespec="seconds")


def create_user(conn: db.Conn, tenant_id: str, name: str, email: str, password: str) -> str:
    """Insert the owner. Raises EmailTaken. `conn` is the connection the business was made on."""
    uid = str(uuid.uuid4())
    try:
        with conn:
            conn.execute(
                "INSERT INTO users (id, tenant_id, name, email, password_hash, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    uid,
                    tenant_id,
                    name.strip(),
                    normalize_email(email),
                    hash_password(password),
                    db.stamp(),
                ),
            )
    except db.Conflict as e:
        raise EmailTaken from e
    return uid


def email_taken(conn: db.Conn, email: str) -> bool:
    return (
        conn.execute("SELECT 1 FROM users WHERE email = ?", (normalize_email(email),)).fetchone()
        is not None
    )


def start_session(conn: db.Conn, user_id: str, tenant_id: str) -> str:
    """Store a new session and return the cookie value: `<token>.<hmac>`."""
    token = secrets.token_urlsafe(32)
    with conn:
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, tenant_id, kind, expires_at, created_at)"
            " VALUES (?, ?, ?, 'user', ?, ?)",
            (_hash_token(token), user_id, tenant_id, _later(days=SESSION_DAYS), db.stamp()),
        )
    return f"{token}.{_sign(token)}"


def _token_from_cookie(value: str | None) -> str | None:
    token, _, sig = (value or "").partition(".")
    if token and sig and hmac.compare_digest(sig, _sign(token)):
        return token
    return None


def login(conn: db.Conn, email: str, password: str) -> tuple[str, str, str]:
    """Check the password and open a session. Returns (cookie value, user id, tenant id).

    Raises BadLogin or Locked. Five wrong passwords lock that account for 15 minutes.
    """
    now = config.now()
    row = conn.execute(
        "SELECT id, tenant_id, password_hash, failed_logins, locked_until FROM users WHERE email = ?",
        (normalize_email(email),),
    ).fetchone()
    if row and row["locked_until"] and row["locked_until"] > now.isoformat(timespec="seconds"):
        raise Locked
    ok = verify_password(password, row["password_hash"] if row else _DUMMY_HASH)
    if not row or not ok:
        if row:
            failed = (row["failed_logins"] or 0) + 1
            locked = _later(minutes=LOCK_MINUTES) if failed >= MAX_FAILED else None
            with conn:
                conn.execute(
                    "UPDATE users SET failed_logins = ?, locked_until = ? WHERE id = ?",
                    (0 if locked else failed, locked, row["id"]),
                )
            if locked:
                raise Locked
        raise BadLogin
    with conn:
        conn.execute(
            "UPDATE users SET failed_logins = 0, locked_until = NULL, last_active_at = ? WHERE id = ?",
            (db.stamp(), row["id"]),
        )
    return start_session(conn, row["id"], row["tenant_id"]), row["id"], row["tenant_id"]


def lookup(conn: db.Conn, cookie: str | None) -> Session | None:
    """The logged-in owner for this cookie, or None (missing, forged, expired or logged out)."""
    token = _token_from_cookie(cookie)
    if not token:
        return None
    row = conn.execute(
        "SELECT u.id, u.tenant_id, u.name, u.email FROM sessions s JOIN users u ON u.id = s.user_id"
        " WHERE s.token_hash = ? AND s.kind = 'user' AND s.expires_at > ?",
        (_hash_token(token), config.now().isoformat(timespec="seconds")),
    ).fetchone()
    if not row:
        return None
    return Session(row["id"], row["tenant_id"], row["name"], row["email"])


def logout(conn: db.Conn, cookie: str | None) -> None:
    token = _token_from_cookie(cookie)
    if token:
        with conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(token),))


def touch(conn: db.Conn, user_id: str) -> None:
    """Record activity. `conn` is scoped to the owner's business."""
    with conn:
        conn.execute(
            "UPDATE users SET last_active_at = ? WHERE id = ? AND tenant_id = ?",
            (db.stamp(), user_id, conn.tid),
        )

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


def ensure_session_secret() -> None:
    """Run once at startup. With Postgres (a deployed host) SESSION_SECRET must be set, so refuse to
    start without it: generating one there would differ per worker and vanish on each deploy. For
    local SQLite dev, generate one into `.env` once, here, rather than during a request."""
    if env("SESSION_SECRET"):
        return
    if db.dialect() == "postgres":
        raise RuntimeError("SESSION_SECRET is not set. Set it in the host's environment.")
    set_env({"SESSION_SECRET": secrets.token_urlsafe(32)})
    log.warning("accounts: SESSION_SECRET was not set; generated one in .env (local dev only)")


def session_secret() -> bytes:
    value = env("SESSION_SECRET")
    if not value:
        raise RuntimeError("SESSION_SECRET is not set (ensure_session_secret runs at startup).")
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
    now = config.now().isoformat(timespec="seconds")
    row = conn.execute(
        "SELECT id, tenant_id, password_hash, locked_until FROM users WHERE email = ?",
        (normalize_email(email),),
    ).fetchone()
    # Always pay for scrypt, even when locked or unknown, so timing doesn't tell them apart.
    ok = verify_password(password, row["password_hash"] if row else _DUMMY_HASH)
    if row and row["locked_until"] and row["locked_until"] > now:
        raise Locked
    if not row or not ok:
        if row:
            _record_failure(conn, row["id"])
        raise BadLogin
    with conn:
        conn.execute(
            "UPDATE users SET failed_logins = 0, locked_until = NULL, last_active_at = ? WHERE id = ?",
            (db.stamp(), row["id"]),
        )
        conn.execute(  # tidy this owner's expired sessions
            "DELETE FROM sessions WHERE user_id = ? AND tenant_id = ? AND expires_at <= ?",
            (row["id"], row["tenant_id"], now),
        )
    return start_session(conn, row["id"], row["tenant_id"]), row["id"], row["tenant_id"]


def _record_failure(conn: db.Conn, user_id: str) -> None:
    """Count one wrong password, atomically, so parallel attempts can't overwrite each other's
    count. The attempt that reaches MAX_FAILED locks the account and raises Locked."""
    with conn:
        failed = conn.execute(
            "UPDATE users SET failed_logins = failed_logins + 1 WHERE id = ? RETURNING failed_logins",
            (user_id,),
        ).fetchone()[0]
        if failed >= MAX_FAILED:
            conn.execute(
                "UPDATE users SET failed_logins = 0, locked_until = ? WHERE id = ?",
                (_later(minutes=LOCK_MINUTES), user_id),
            )
    if failed >= MAX_FAILED:
        raise Locked


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


DEMO_EMAIL = "demo.clinic@example.com"


DEMO_EMAILS = {  # template -> (default email, variable that overrides it)
    "clinic": (DEMO_EMAIL, "DEMO_LOGIN_EMAIL"),
    "wholesale": ("demo.wholesale@example.com", "DEMO_WHOLESALE_LOGIN_EMAIL"),
}


def ensure_demo_login(conn: db.Conn, tenant_id: str, template: str = "clinic") -> str | None:
    """Give a demo business (clinic or wholesale) an owner login, so its desk and settings sit behind
    a session like every other business. Both use DEMO_LOGIN_PASSWORD. The password comes only from DEMO_LOGIN_PASSWORD (never the repo). Runs at every
    start, so the variable is the truth:

    - unset (or too short): no demo login; any earlier one and its sessions are removed;
    - a new DEMO_LOGIN_EMAIL: the old demo login is removed;
    - a new password: the hash is replaced and the old sessions end.

    Returns the email, or None when there is no demo login. `conn` is unchecked: startup, before any
    request.
    """
    password = env("DEMO_LOGIN_PASSWORD")
    default, variable = DEMO_EMAILS[template]
    email = normalize_email(env(variable) or default)
    usable = len(password) >= MIN_PASSWORD
    if password and not usable:
        log.warning(
            "accounts: DEMO_LOGIN_PASSWORD is under %s characters; no demo login", MIN_PASSWORD
        )
    _remove_demo_logins(conn, tenant_id, keep=email if usable else None)
    if not usable:
        return None
    row = _user_by_email(conn, email)
    if row is None:
        try:
            create_user(conn, tenant_id, "Demo owner", email, password)
        except EmailTaken:  # another worker starting at the same moment created it first
            row = _user_by_email(conn, email)
    if row is None:
        return email
    if row["tenant_id"] != tenant_id:
        log.warning("accounts: DEMO_LOGIN_EMAIL belongs to another business; no demo login")
        return None
    if not verify_password(password, row["password_hash"]):
        with conn:
            conn.execute(
                "UPDATE users SET password_hash = ?, failed_logins = 0, locked_until = NULL"
                " WHERE id = ?",
                (hash_password(password), row["id"]),
            )
            conn.execute(  # the old password's sessions end with it
                "DELETE FROM sessions WHERE user_id = ? AND tenant_id = ?", (row["id"], tenant_id)
            )
    return email


def _user_by_email(conn: db.Conn, email: str) -> db.Row | None:
    return conn.execute(
        "SELECT id, tenant_id, password_hash FROM users WHERE email = ?", (email,)
    ).fetchone()


def _remove_demo_logins(conn: db.Conn, tenant_id: str, keep: str | None) -> None:
    """Delete the demo clinic's logins (and their sessions) other than `keep`. Only the demo clinic's
    tenant id is ever passed here: no real owner belongs to it."""
    rows = conn.execute("SELECT id, email FROM users WHERE tenant_id = ?", (tenant_id,)).fetchall()
    gone = [r["id"] for r in rows if r["email"] != keep]
    if not gone:
        return
    with conn:
        for uid in gone:
            conn.execute(
                "DELETE FROM sessions WHERE user_id = ? AND tenant_id = ?", (uid, tenant_id)
            )
            conn.execute("DELETE FROM users WHERE id = ? AND tenant_id = ?", (uid, tenant_id))
    log.info("accounts: removed %s old demo login(s)", len(gone))


# Admin (our team): one shared password from ADMIN_PASSWORD, its own cookie and session kind.
ADMIN_COOKIE = "catalyst_admin"
ADMIN_HOURS = 12
_admin_failures: list[str] = []  # stamps of recent wrong admin passwords (this process)


def admin_login(conn: db.Conn, password: str) -> str:
    """Check ADMIN_PASSWORD and open an admin session. Returns the cookie value.

    Raises BadLogin (wrong, or ADMIN_PASSWORD unset: there is no admin then) or Locked after 5
    wrong passwords within 15 minutes."""
    expected = env("ADMIN_PASSWORD")
    now = config.now()
    window = (now - timedelta(minutes=LOCK_MINUTES)).isoformat(timespec="seconds")
    _admin_failures[:] = [t for t in _admin_failures if t > window]
    if len(_admin_failures) >= MAX_FAILED:
        raise Locked
    if not expected or not hmac.compare_digest(password.encode(), expected.encode()):
        _admin_failures.append(now.isoformat(timespec="seconds"))
        raise BadLogin
    _admin_failures.clear()
    token = secrets.token_urlsafe(32)
    with conn:
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, tenant_id, kind, expires_at, created_at)"
            " VALUES (?, NULL, NULL, 'admin', ?, ?)",
            (_hash_token(token), _later(hours=ADMIN_HOURS), db.stamp()),
        )
    return f"{token}.{_sign(token)}"


def is_admin(conn: db.Conn, cookie: str | None) -> bool:
    token = _token_from_cookie(cookie)
    if not token or not env("ADMIN_PASSWORD"):  # unsetting the password ends every admin session
        return False
    row = conn.execute(
        "SELECT 1 FROM sessions WHERE token_hash = ? AND kind = 'admin' AND expires_at > ?",
        (_hash_token(token), config.now().isoformat(timespec="seconds")),
    ).fetchone()
    return row is not None

# `backend/src/accounts/`

**Purpose.** Owner accounts for self-serve businesses: scrypt password hashing, signed session cookies, per-account login lockout. One owner per business (ADR-0038).

**Capabilities served.** C12 (self-serve setup), C11 (business isolation: the session decides which business a request may touch).

**Contracts used.** `contracts.md` §3.1 (`users`, `sessions`) and §6 (cookie, CSRF header, error shape, `/api/signup`, `/api/login`, `/api/logout`, `/api/me`).

**How it works.**
- Passwords are `hashlib.scrypt` with a per-user salt. The stored form is `scrypt$n$r$p$salt$hash`.
- The cookie `catalyst_session` is `<token>.<HMAC-SHA256 of the token>` using `SESSION_SECRET`. The database stores only the token's SHA-256, so a database leak can't be replayed as logins. Logout deletes the row.
- Five wrong passwords lock the account for 15 minutes (`LOCKED`). A good login resets the count. The count is updated atomically, so parallel guesses can't skip the lock. Wrong email and wrong password give the same answer and take the same time (scrypt always runs). Only a real account can reach `LOCKED`, so the lock does show that an email has an account; contracts §6 accepts that for a per-email lock. A per-IP limit is not here yet.
- `SESSION_SECRET` is checked once at startup. With `DATABASE_URL` set, the backend refuses to start without it. For local SQLite dev, one is generated into `.env`.
- Auth lookups run on `db.connect_unchecked()` because the session or email is what *tells us* the business. After that every route uses `get_user_conn`, a connection scoped to the owner's business.

**Must not.** Log or return emails, passwords or tokens. Skip the tenant scope once the business is known.

**Not here yet.** `events` (login/signup usage events, M7), admin sessions (M7), password reset and email verification (backlog).

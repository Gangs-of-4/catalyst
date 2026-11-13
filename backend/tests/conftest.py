import os
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from src import accounts, seed
from src.core import config, db
from src.core import settings as cs
from src.main import app

# Tuesday 27 Oct 2026, 09:00 IST: before clinic hours, so all of today's slots are open.
FIXED_NOW = datetime(2026, 10, 27, 9, 0, tzinfo=config.IST)

# Set TEST_DATABASE_URL to run the suite on a throwaway Postgres database (CI does).
# Its public schema is dropped before every test, so never point it at real data.
# DATABASE_URL itself is always ignored by tests.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()


def _reset_postgres() -> None:
    db.clear_pool()  # pooled connections from the last test would be terminated below
    c = db.connect_unchecked()
    try:
        # A connection left open by an earlier test would hold locks and make DROP wait forever.
        c.raw.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
            " WHERE datname = current_database() AND pid <> pg_backend_pid()"
        )
        c.raw.execute("DROP SCHEMA public CASCADE")
        c.raw.execute("CREATE SCHEMA public")
        c.commit()
    finally:
        c.close()


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Every test gets its own DB, an empty .env and a fixed clock."""
    monkeypatch.setenv("CATALYST_DB", str(tmp_path / "test.db"))
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("CATALYST_ENV_FILE", str(env_file))
    if TEST_DATABASE_URL:
        monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
        # Fail with an error instead of hanging if a test ever waits on a lock (libpq reads this).
        monkeypatch.setenv("PGOPTIONS", "-c lock_timeout=20000")
        _reset_postgres()
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    for name in (
        "CATALYST_TOOL_SECRET",
        "DEMO_LOGIN_PASSWORD",
        "DEMO_LOGIN_EMAIL",
        "DEMO_VOICE",
        "DEMO_HISTORY",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "GROQ_API_KEY",
        "VAPI_PRIVATE_KEY",
        "PUBLIC_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    # Tests rewrite .env freely, so the cookie secret comes from the process environment.
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret")
    monkeypatch.setattr(config, "now", lambda: FIXED_NOW)
    yield env_file


@pytest.fixture
def conn():
    """A connection scoped to the demo clinic (seeded without demo bookings)."""
    c = db.connect()
    c = c.for_tenant(seed.ensure(c, with_demo_data=False))
    yield c
    c.close()


@pytest.fixture
def raw():
    """Unchecked connection for asserting stored state directly."""
    c = db.connect_unchecked()
    yield c
    c.close()


@pytest.fixture
def settings(conn):
    return cs.load(conn)


DEMO_PASSWORD = "demo-pass-123"
APP_HEADERS = {"X-Requested-With": "catalyst"}


@pytest.fixture
def owner(isolated, monkeypatch):
    """A client logged in as the demo clinic's owner (DEMO_LOGIN_PASSWORD), sending the app's
    CSRF header like the pages do."""
    monkeypatch.setenv("DEMO_LOGIN_PASSWORD", DEMO_PASSWORD)
    with TestClient(app, headers=APP_HEADERS) as c:
        r = c.post("/api/login", json={"email": accounts.DEMO_EMAIL, "password": DEMO_PASSWORD})
        assert r.status_code == 200, r.text
        yield c


@pytest.fixture
def no_wholesale_prompt(tmp_path, monkeypatch):
    """The wholesale template as it was before it had a voice agent: no agent-prompt.md. For the
    tests of how a template without a prompt behaves (no assistant, `not_configured`)."""
    import shutil

    from src.verticals import loader

    real = loader.template_dir
    copy = tmp_path / "templates" / "wholesale"
    shutil.copytree(real("wholesale"), copy, ignore=shutil.ignore_patterns("agent-prompt.md"))
    monkeypatch.setattr(
        loader, "template_dir", lambda name: copy if name == "wholesale" else real(name)
    )

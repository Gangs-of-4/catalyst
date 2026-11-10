import os
from datetime import datetime

import pytest

from src import seed
from src.core import config, db
from src.core import settings as cs

# Tuesday 27 Oct 2026, 09:00 IST: before clinic hours, so all of today's slots are open.
FIXED_NOW = datetime(2026, 10, 27, 9, 0, tzinfo=config.IST)

# Set TEST_DATABASE_URL to run the suite on a throwaway Postgres database (CI does).
# Its public schema is dropped before every test, so never point it at real data.
# DATABASE_URL itself is always ignored by tests.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()


def _reset_postgres() -> None:
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
        "DESK_PASSWORD",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "GROQ_API_KEY",
        "VAPI_PRIVATE_KEY",
        "PUBLIC_URL",
    ):
        monkeypatch.delenv(name, raising=False)
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

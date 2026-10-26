from datetime import datetime

import pytest

from src.core import config, db
from src.core import settings as cs
from src import seed

# Tuesday 27 Oct 2026, 09:00 IST: before clinic hours, so all of today's slots are open.
FIXED_NOW = datetime(2026, 10, 27, 9, 0, tzinfo=config.IST)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Every test gets its own DB, an empty .env and a fixed clock."""
    monkeypatch.setenv("CATALYST_DB", str(tmp_path / "test.db"))
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("CATALYST_ENV_FILE", str(env_file))
    for name in ("CATALYST_TOOL_SECRET", "DESK_PASSWORD", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN",
                 "GROQ_API_KEY", "VAPI_PRIVATE_KEY", "PUBLIC_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "now", lambda: FIXED_NOW)
    yield env_file


@pytest.fixture
def conn():
    c = db.connect()
    seed.ensure(c, with_demo_data=False)
    yield c
    c.close()


@pytest.fixture
def settings(conn):
    return cs.load(conn)

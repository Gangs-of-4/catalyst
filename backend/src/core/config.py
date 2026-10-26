"""Paths, environment and clock. `.env` is re-read on every call so setup scripts apply without a restart."""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"
VERTICAL_DIR = REPO_ROOT / "verticals" / "clinic"

# Windows Python ships without a tz database, so IST is a fixed offset.
IST = timezone(timedelta(hours=5, minutes=30), "IST")


def env_path() -> Path:
    return Path(os.environ.get("CATALYST_ENV_FILE", REPO_ROOT / ".env"))


def env(name: str, default: str = "") -> str:
    """Value from `.env` (fresh read), else the process environment, else `default`."""
    path = env_path()
    values = dotenv_values(path) if path.exists() else {}
    value = values.get(name) or os.environ.get(name) or default
    return value.strip()


def db_path() -> Path:
    return Path(os.environ.get("CATALYST_DB", BACKEND_DIR / "data" / "clinic.db"))


def now() -> datetime:
    """Current IST time. Tests monkeypatch this."""
    return datetime.now(IST)

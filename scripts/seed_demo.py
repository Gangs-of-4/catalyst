"""Reset the two demo businesses: clear their data, then seed today's data and the last 4 weeks of
fictional usage again, anchored to today. Settings and the demo logins are kept.

Run with the backend venv active, from the repo root:  python scripts/seed_demo.py
It uses DATABASE_URL when set (the deployed Neon database), else the local SQLite file. Rerun it
before a demo, or monthly, so the history stays fresh until the program ends.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from src import seed  # noqa: E402
from src.core import db  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
    conn = db.connect()
    try:
        seed.ensure(conn)
    finally:
        conn.close()
    conn = db.connect_unchecked()
    try:
        done = seed.reset_demo(conn)
    finally:
        conn.close()
    print(f"Reset the demo {', '.join(done)} with {seed.HISTORY_DAYS} days of history.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Issue #53: Postgres connections are reused instead of opened per request."""

import logging

import pytest
from fastapi.testclient import TestClient

from src import main
from src.core import db


class FakeRaw:
    def __init__(self):
        self.closed = False
        self.broken = False
        self.rollbacks = 0
        self.selects = 0

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True

    def execute(self, sql):
        self.selects += 1


@pytest.fixture
def pool(monkeypatch):
    db.clear_pool()
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/db")
    yield
    db.clear_pool()


def test_a_released_connection_is_reused_clean(pool):
    raw = FakeRaw()
    db._release(raw)
    assert raw.rollbacks == 1 and not raw.closed  # no open transaction is handed on
    assert db._take("postgresql://example/db") is raw
    assert db._take("postgresql://example/db") is None  # taken once


def test_the_same_connection_is_never_pooled_twice(pool):
    raw = FakeRaw()
    db._release(raw)
    db._release(raw)  # two Conn views of one connection, both closed
    assert db._take("postgresql://example/db") is raw
    assert db._take("postgresql://example/db") is None


def test_broken_old_or_other_database_connections_are_dropped(pool, monkeypatch):
    broken = FakeRaw()
    broken.broken = True
    db._release(broken)
    assert broken.closed and db._take("postgresql://example/db") is None
    other = FakeRaw()
    db._release(other)
    assert db._take("postgresql://elsewhere/db") is None and other.closed
    old = FakeRaw()
    db._release(old)
    now = db.time.monotonic()
    monkeypatch.setattr(db.time, "monotonic", lambda: now + db.POOL_MAX_IDLE_S + 1)
    assert db._take("postgresql://example/db") is None and old.closed


def test_a_connection_idle_a_while_is_checked_first(pool, monkeypatch):
    raw = FakeRaw()
    db._release(raw)
    now = db.time.monotonic()
    monkeypatch.setattr(db.time, "monotonic", lambda: now + 60)
    assert db._take("postgresql://example/db") is raw and raw.selects == 1


def test_the_pool_has_a_size_limit(pool):
    raws = [FakeRaw() for _ in range(db.POOL_SIZE + 2)]
    for raw in raws:
        db._release(raw)
    assert sum(r.closed for r in raws) == 2


def test_slow_requests_are_logged(isolated, monkeypatch, caplog):
    monkeypatch.setattr(main, "SLOW_REQUEST_S", -1)
    with TestClient(main.app) as c, caplog.at_level(logging.WARNING, logger="catalyst"):
        c.get("/healthz?secret=x")
    assert "slow request: GET /healthz -> 200" in caplog.text and "secret" not in caplog.text

"""Phase 2 M9: the two demo businesses, their logins, and the 4-week fictional history."""

import importlib.util
from datetime import timedelta
from pathlib import Path

import pytest
from conftest import APP_HEADERS, DEMO_PASSWORD, FIXED_NOW
from fastapi.testclient import TestClient

from src import seed
from src.accounts import service as accounts_service
from src.core import config, db, tenancy
from src.main import app

ADMIN = "admin-pass-123"


@pytest.fixture
def history_env(isolated, monkeypatch):
    monkeypatch.setenv("DEMO_HISTORY", "1")
    monkeypatch.setenv("DEMO_LOGIN_PASSWORD", DEMO_PASSWORD)
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN)
    accounts_service._admin_failures.clear()
    return isolated


def raw_rows(sql, params=()):
    conn = db.connect_unchecked()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def demo(template):
    conn = db.connect_unchecked()
    try:
        return tenancy.demo_id(conn, template)
    finally:
        conn.close()


def login(c, email):
    r = c.post("/api/login", json={"email": email, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text


# Both demo businesses, today


def test_both_demos_exist_with_todays_data(isolated, monkeypatch):
    monkeypatch.setenv("DEMO_LOGIN_PASSWORD", DEMO_PASSWORD)
    with TestClient(app, headers=APP_HEADERS) as c:
        board = c.get("/api/try/demo-wholesale/board").json()
        assert board["kind"] == "orders"
        assert [o["status"] for o in board["orders"]] == ["dispatched", "confirmed", "new"]
        assert all(o["shop"].endswith(".") for o in board["orders"])  # masked
        info = c.get("/api/try/demo-wholesale").json()
        assert info["name"] == "Navjeevan Medical Agencies" and info["modules"] == ["orders"]
        login(c, "demo.wholesale@example.com")
        assert len(c.get("/api/catalog").json()["products"]) == 10
        assert c.get("/api/settings").json()["settings"]["min_order"] == "₹1,500"
        c.post("/api/logout")
        login(c, "demo.clinic@example.com")
        assert c.get("/api/me").json()["business"]["template"] == "clinic"


def test_no_history_unless_asked(isolated):
    with TestClient(app):
        pass
    today = FIXED_NOW.date().isoformat()
    assert raw_rows("SELECT 1 FROM events WHERE created_at < ?", (today,)) == []
    assert raw_rows("SELECT 1 FROM bookings WHERE date < ?", (today,)) == []


# The history


def test_history_fills_four_weeks_for_both_demos(history_env):
    with TestClient(app, headers=APP_HEADERS) as c:
        assert c.post("/api/admin/login", json={"password": ADMIN}).status_code == 200
        found = {b["public_id"]: b for b in c.get("/api/admin/businesses").json()["businesses"]}
        for public_id in ("demo-clinic", "demo-wholesale"):
            b = found[public_id]
            assert b["records"] > 20 and b["calls"] > 20 and b["wa_commands"] > 0, public_id
            past_weeks = b["weeks"][:-1]  # this week has only Monday's history so far
            assert all(w["records"] > 0 and w["calls"] > 0 for w in past_weeks), public_id
        login(c, "demo.clinic@example.com")
        assert len(c.get("/api/calls").json()) == 25  # the desk's call log is full
        assert c.get("/api/desk/day", params={"date": "2026-10-20"}).json()["columns"]
        c.post("/api/logout")
        login(c, "demo.wholesale@example.com")
        delivered = c.get("/api/orders", params={"status": "delivered"}).json()["orders"]
        assert len(delivered) > 20 and all(o["items"] and o["total_paise"] > 0 for o in delivered)


def test_history_leaves_today_as_it_was(history_env):
    with TestClient(app, headers=APP_HEADERS) as c:
        login(c, "demo.clinic@example.com")
        assert c.get("/api/stats").json()["sentence"].startswith("Today: 0 calls")
        open_items = c.get("/api/inbox").json()
        assert len(open_items) == 1  # the one seeded callback; history callbacks are done


def test_history_is_added_once(history_env):
    with TestClient(app):
        pass
    first = raw_rows("SELECT COUNT(*) FROM events")[0][0]
    with TestClient(app):  # a restart with DEMO_HISTORY still set
        pass
    assert raw_rows("SELECT COUNT(*) FROM events")[0][0] == first and first > 100


def test_history_is_deterministic(history_env):
    def snapshot():
        return [
            tuple(r)
            for r in raw_rows(
                "SELECT resource_id, date, time, status, name FROM bookings ORDER BY date, time,"
                " resource_id"
            )
        ]

    with TestClient(app):
        pass
    before = snapshot()
    conn = db.connect_unchecked()
    try:
        seed.reset_demo(conn)
    finally:
        conn.close()
    assert snapshot() == before


def test_reset_reanchors_to_today_and_keeps_settings_and_logins(history_env, monkeypatch):
    with TestClient(app, headers=APP_HEADERS) as c:
        login(c, "demo.wholesale@example.com")
        s = c.get("/api/settings").json()["settings"]
        body = {k: s[k] for k in ("name", "address", "sessions")} | {"delivery_area": "Changed"}
        assert c.put("/api/settings", json=body).status_code == 200
    later = FIXED_NOW + timedelta(days=40)
    monkeypatch.setattr(config, "now", lambda: later)
    conn = db.connect_unchecked()
    try:
        assert sorted(seed.reset_demo(conn)) == ["clinic", "wholesale"]
    finally:
        conn.close()
    newest = raw_rows(
        "SELECT MAX(created_at) FROM events WHERE created_at < ?", (later.date().isoformat(),)
    )[0][0]
    assert newest[:10] >= (later.date() - timedelta(days=2)).isoformat()
    oldest = raw_rows("SELECT MIN(date) FROM bookings")[0][0]
    assert oldest >= (later.date() - timedelta(days=seed.HISTORY_DAYS)).isoformat()
    with TestClient(app, headers=APP_HEADERS) as c:
        login(c, "demo.wholesale@example.com")  # the login survived the reset
        assert c.get("/api/settings").json()["settings"]["delivery_area"] == "Changed"
        assert len(c.get("/api/catalog").json()["products"]) == 10  # re-imported once


def test_no_real_looking_personal_data(history_env):
    with TestClient(app):
        pass
    phones = [
        r[0]
        for sql in (
            "SELECT phone FROM bookings",
            "SELECT phone FROM orders",
            "SELECT phone FROM inbox",
        )
        for r in raw_rows(sql)
        if r[0]
    ]
    assert phones and all(p.startswith("+919000") for p in phones)
    import yaml

    names = set()
    for template, key in (("clinic", "patients"), ("wholesale", "shops")):
        path = Path(__file__).resolve().parents[2] / "verticals" / template / "demo-tenant.yaml"
        y = yaml.safe_load(path.read_text(encoding="utf-8"))
        names |= set(y["history"][key])
        names |= {b["name"] for b in y.get("seed", {}).get("bookings", [])}
        names |= {c["name"] for c in y.get("seed", {}).get("callbacks", [])}
        names |= {o["shop"] for o in y.get("seed", {}).get("orders", [])}
    used = {r[0] for r in raw_rows("SELECT name FROM bookings")}
    used |= {r[0] for r in raw_rows("SELECT shop_name FROM orders")}
    assert used <= names  # only the fictional lists


def test_the_reset_script_runs(history_env, capsys):
    with TestClient(app):
        pass
    path = Path(__file__).resolve().parents[2] / "scripts" / "seed_demo.py"
    spec = importlib.util.spec_from_file_location("seed_demo", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main() == 0
    assert "Reset the demo clinic, wholesale" in capsys.readouterr().out
    assert demo("clinic") and demo("wholesale")

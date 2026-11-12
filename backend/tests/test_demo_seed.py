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

ADMIN = "admin-pass-1234567"


@pytest.fixture
def history_env(isolated, monkeypatch):
    monkeypatch.setenv("DEMO_HISTORY", "1")
    monkeypatch.setenv("DEMO_LOGIN_PASSWORD", DEMO_PASSWORD)
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN)
    accounts_service._admin_failures.clear()
    accounts_service._admin_all_failures.clear()
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


# Review fixes (#40)


def test_history_still_comes_if_the_demo_was_used_first(isolated, monkeypatch):
    monkeypatch.setenv("DEMO_LOGIN_PASSWORD", DEMO_PASSWORD)
    with TestClient(app, headers=APP_HEADERS) as c:  # no DEMO_HISTORY yet
        login(c, "demo.clinic@example.com")  # writes a login event
    conn = db.connect_unchecked()
    try:
        with conn:  # make that event an old one, as on a host used for a few days
            conn.execute("UPDATE events SET created_at = '2026-10-20T10:00:00+05:30'")
    finally:
        conn.close()
    monkeypatch.setenv("DEMO_HISTORY", "1")
    with TestClient(app):
        pass
    for template in ("clinic", "wholesale"):
        tid = demo(template)
        assert raw_rows("SELECT 1 FROM calls WHERE tenant_id = ? AND id LIKE 'demo-%'", (tid,))


def test_order_numbers_run_with_the_dates(history_env):
    with TestClient(app):
        pass
    rows = raw_rows(
        "SELECT number, created_at FROM orders WHERE tenant_id = ? ORDER BY number",
        (demo("wholesale"),),
    )
    dates = [r[1] for r in rows]
    assert dates == sorted(dates)  # older orders have smaller numbers
    assert [r[0] for r in rows] == list(range(1, len(rows) + 1))  # 1, 2, 3 … with no gaps
    today = FIXED_NOW.date().isoformat()
    assert all(r[1].startswith(today) for r in rows[-3:])  # today's three come last


def test_every_history_event_has_its_row(history_env):
    with TestClient(app):
        pass
    for template in ("clinic", "wholesale"):
        tid = demo(template)
        calls = raw_rows("SELECT COUNT(*) FROM calls WHERE tenant_id = ?", (tid,))[0][0]
        ended = raw_rows(
            "SELECT COUNT(*) FROM events WHERE tenant_id = ? AND type = 'call_ended'", (tid,)
        )[0][0]
        assert calls == ended > 0
    tid = demo("clinic")
    past = raw_rows(
        "SELECT COUNT(*) FROM bookings WHERE tenant_id = ? AND date < ?",
        (tid, FIXED_NOW.date().isoformat()),
    )[0][0]
    made = raw_rows(
        "SELECT COUNT(*) FROM events WHERE tenant_id = ? AND type = 'booking_created'", (tid,)
    )[0][0]
    assert past == made > 0


def test_a_broken_config_stops_the_reset_before_it_deletes(history_env, monkeypatch):
    with TestClient(app):
        pass
    before = raw_rows("SELECT COUNT(*) FROM orders")[0][0]
    from src.verticals import loader

    real = loader.load_yaml

    def broken(name, base=None, *a):
        if base is not None and base.name == "wholesale" and name == "demo-tenant.yaml":
            raise ValueError("bad yaml")
        return real(name, base) if base is not None else real(name)

    monkeypatch.setattr(loader, "load_yaml", broken)
    conn = db.connect_unchecked()
    try:
        with pytest.raises(ValueError):
            seed.reset_demo(conn)
    finally:
        conn.close()
    assert raw_rows("SELECT COUNT(*) FROM orders")[0][0] == before > 0


def test_a_second_worker_making_the_wholesale_demo_is_harmless(isolated, monkeypatch):
    with TestClient(app):
        pass
    real = tenancy.demo_id
    monkeypatch.setattr(  # this worker looked before the other one's insert
        seed.tenancy, "demo_id", lambda c, t="clinic": None if t == "wholesale" else real(c, t)
    )
    conn = db.connect()
    try:
        seed.ensure(conn)  # no crash
    finally:
        conn.close()
    assert len(raw_rows("SELECT id FROM tenants WHERE public_id = 'demo-wholesale'")) == 1


def test_todays_orders_open_the_order_board(history_env):
    """The board pages newest-first by id: today's orders must be on its first page, first."""
    from src.orders import service as orders

    with TestClient(app):
        pass
    conn = db.connect().for_tenant(demo("wholesale"))
    try:
        first_page = orders.list_orders(conn, None, None, None, 50)
    finally:
        conn.close()
    today = FIXED_NOW.date().isoformat()
    assert [o["created_at"][:10] for o in first_page[:3]] == [today] * 3
    assert {o["status"] for o in first_page[:3]} == {"new", "confirmed", "dispatched"}
    assert all(o["items"] for o in first_page[:3])  # their lines came back with them


def test_orders_placed_on_the_demo_survive_the_history_run(isolated, monkeypatch):
    """The live demo already had today's orders (and maybe a visitor's) before DEMO_HISTORY."""
    with TestClient(app):
        pass
    tid = demo("wholesale")
    before = {
        (r[0], r[1], r[2])
        for r in raw_rows("SELECT shop_name, status, phone FROM orders WHERE tenant_id = ?", (tid,))
    }
    monkeypatch.setenv("DEMO_HISTORY", "1")
    with TestClient(app):
        pass
    newest = raw_rows(
        "SELECT shop_name, status, phone FROM orders WHERE tenant_id = ? ORDER BY id DESC LIMIT 3",
        (tid,),
    )
    assert {(r[0], r[1], r[2]) for r in newest} == before

"""Issue #56: time in the app (`POST /api/activity`) and the admin dashboard
(`/api/admin/overview`, `/api/admin/businesses/{id}`). Counts only."""

from datetime import timedelta

import pytest
from conftest import APP_HEADERS, FIXED_NOW
from fastapi.testclient import TestClient

from src import analytics
from src.core import config, db, tenancy
from src.main import app

ADMIN_PASSWORD = "admin-pass-1234567"


def signup(c, n=1):
    body = {
        "user": {
            "name": "Owner",
            "email": f"dash{n}@example.com",
            "password": "another pass",
        },
        "business": {
            "template": "clinic",
            "name": f"Dashboard Business {n}",
            "address": "1 Test Road",
            "hours": [["09:00", "19:00"]],
            "owner_whatsapp": f"900000050{n}",
            "consent": True,
        },
        "details": {"doctors": [{"name": "Dr. Test"}]},
    }
    r = c.post("/api/signup", json=body)
    assert r.status_code == 200, r.text
    conn = db.connect_unchecked()
    try:
        return tenancy.by_public_id(conn, r.json()["public_id"])["id"]
    finally:
        conn.close()


@pytest.fixture
def env(isolated, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN_PASSWORD)
    from src.accounts import service

    service._admin_failures.clear()
    service._admin_all_failures.clear()
    return isolated


def admin_client():
    c = TestClient(app, headers=APP_HEADERS)
    assert c.post("/api/admin/login", json={"password": ADMIN_PASSWORD}).status_code == 200
    return c


def activity_rows(tid):
    conn = db.connect_unchecked()
    try:
        return [
            dict(r)
            for r in conn.execute("SELECT * FROM activity WHERE tenant_id = ?", (tid,)).fetchall()
        ]
    finally:
        conn.close()


def test_activity_counts_a_minute_once_and_needs_a_login(env, monkeypatch):
    with TestClient(app, headers=APP_HEADERS) as c:
        assert c.post("/api/activity").status_code == 401  # not logged in
        tid = signup(c)
        assert c.post("/api/activity").status_code == 204
        assert c.post("/api/activity").status_code == 204  # same minute: a second tab
        rows = activity_rows(tid)
        assert len(rows) == 1 and rows[0]["minutes"] == 1
        assert rows[0]["day"] == FIXED_NOW.date().isoformat()
        monkeypatch.setattr(config, "now", lambda: FIXED_NOW + timedelta(minutes=1))
        assert c.post("/api/activity").status_code == 204
        assert activity_rows(tid)[0]["minutes"] == 2
        # The person comes from the session: a body naming someone else is ignored.
        assert c.post("/api/activity", json={"user_id": "someone-else"}).status_code == 204
        assert {r["user_id"] for r in activity_rows(tid)} == {rows[0]["user_id"]}


def test_activity_needs_the_csrf_header(env):
    with TestClient(app, headers=APP_HEADERS) as c:
        signup(c)
        assert TestClient(app, cookies=c.cookies).post("/api/activity").status_code == 403


def test_overview_totals_minutes_sources_and_scope(env):
    with TestClient(app, headers=APP_HEADERS) as owner:
        tid = signup(owner)
        owner.post("/api/activity")
    conn = db.connect_unchecked()
    try:
        scoped = conn.for_tenant(tid)
        start = FIXED_NOW - timedelta(hours=1)
        with scoped:
            for i, (secs, src) in enumerate([(150, "phone"), (90, "phone"), (-30, "walk_in")]):
                scoped.execute(
                    "INSERT INTO calls (tenant_id, id, started_at, ended_at) VALUES (?, ?, ?, ?)",
                    (
                        tid,
                        f"c{i}",
                        start.isoformat(),
                        (start + timedelta(seconds=secs)).isoformat(),
                    ),
                )
                scoped.execute(
                    "INSERT INTO bookings (tenant_id, resource_id, date, time, source, name,"
                    " created_at, updated_at) VALUES (?, 'r', '2026-10-28', ?, ?, 'Test', ?, ?)",
                    (tid, f"1{i}:00", src, start.isoformat(), start.isoformat()),
                )
                analytics.record(scoped, "call_ended", commit=False)
        demo_ids = {r[0] for r in conn.execute("SELECT id FROM tenants WHERE is_demo = 1")}
    finally:
        conn.close()

    with admin_client() as a:
        r = a.get("/api/admin/overview")
        assert r.status_code == 200, r.text
        body = r.json()
        real = body["real"]
        assert real["businesses"] == 1 and real["users"] == 1
        assert real["calls"] == 3
        assert real["call_minutes"] == 4.0  # 2.5 + 1.5; the negative one is skipped
        assert real["records"] == {"bookings": 3, "orders": 0}
        assert real["records_by_source"] == {"phone": 2, "walk_in": 1}
        assert real["app_minutes"] == 1
        assert real["active_businesses_7d"] == 1 and real["active_users_7d"] == 1
        assert body["demo"]["businesses"] == len(demo_ids)
        assert len(body["daily"]) == analytics.DAYS
        assert body["daily"][-1]["date"] == FIXED_NOW.date().isoformat()
        assert body["daily"][-1]["call_minutes"] == 4.0
        assert body["daily"][-1]["app_minutes"] == 1
        assert {"type": "call_ended", "count": 3} in body["features"]

        # Scope picks whose features and days come back; both totals always do.
        all_ = a.get("/api/admin/overview?scope=all").json()
        assert all_["real"] == real
        assert sum(d["events"] for d in all_["daily"]) >= sum(d["events"] for d in body["daily"])
        assert a.get("/api/admin/overview?scope=nope").status_code == 422


def test_business_detail_is_counts_only(env):
    with TestClient(app, headers=APP_HEADERS) as owner:
        tid = signup(owner)
        owner.post("/api/activity")
    with admin_client() as a:
        r = a.get(f"/api/admin/businesses/{tid}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["business"]["id"] == tid
        assert len(body["daily"]) == analytics.DAYS
        (person,) = body["users"]
        assert person["role"] == "owner"
        assert person["app_minutes"] == 1 and person["active_days"] == 1
        assert person["logins"] >= 0
        assert "@" not in r.text  # never an email
        assert a.get("/api/admin/businesses/nope").status_code == 404


def test_dashboard_routes_need_the_admin_login(env):
    with TestClient(app, headers=APP_HEADERS) as c:
        tid = signup(c)  # an owner session is not an admin session
        assert c.get("/api/admin/overview").status_code == 401
        assert c.get(f"/api/admin/businesses/{tid}").status_code == 401


def test_deleting_an_unfinished_signup_clears_its_activity(env):
    with TestClient(app, headers=APP_HEADERS) as c:
        tid = signup(c)
        c.post("/api/activity")
    conn = db.connect_unchecked()
    try:
        tenancy.delete(conn, tid)
    finally:
        conn.close()
    assert activity_rows(tid) == []

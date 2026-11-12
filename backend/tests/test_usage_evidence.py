"""Phase 2 M7: usage events, the admin view (counts and weekly breakdown), usage CSV, feedback."""

import csv
import io
from datetime import date
from urllib.parse import urlencode

import pytest
from conftest import APP_HEADERS, FIXED_NOW
from fastapi.testclient import TestClient

from src import analytics
from src.core import db, tenancy
from src.main import app

ADMIN_PASSWORD = "admin-pass-123"
OWNER = "+919000000401"


def signup(c, template="clinic", n=1, owner=OWNER, email=None):
    body = {
        "user": {
            "name": "Owner",
            "email": email or f"u{n}@example.com",
            "password": "another pass",
        },
        "business": {
            "template": template,
            "name": f"Usage Business {n}",
            "address": "1 Test Road",
            "hours": [["09:00", "19:00"]],
            "owner_whatsapp": owner[3:],
            "consent": True,
        },
        "details": {"doctors": [{"name": "Dr. Test"}]} if template == "clinic" else {},
    }
    r = c.post("/api/signup", json=body)
    assert r.status_code == 200, r.text
    return r.json()["public_id"]


@pytest.fixture
def env(isolated, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN_PASSWORD)
    from src.accounts import service

    service._admin_failures.clear()
    return isolated


@pytest.fixture
def admin(env):
    with TestClient(app, headers=APP_HEADERS) as c:
        assert c.post("/api/admin/login", json={"password": ADMIN_PASSWORD}).status_code == 200
        yield c


@pytest.fixture
def owner(env):
    with TestClient(app, headers=APP_HEADERS) as c:
        signup(c)
        yield c


def tid_of(c):
    conn = db.connect_unchecked()
    try:
        pid = c.get("/api/me").json()["business"]["public_id"]
        return tenancy.by_public_id(conn, pid)["id"]
    finally:
        conn.close()


def counts(tid):
    conn = db.connect_unchecked()
    try:
        rows = conn.execute(
            "SELECT type, COUNT(*) FROM events WHERE tenant_id = ? GROUP BY type", (tid,)
        ).fetchall()
        return {r[0]: r[1] for r in rows}
    finally:
        conn.close()


# Events


def test_the_things_owners_do_are_counted(owner):
    tid = tid_of(owner)
    owner.post("/api/logout")
    owner.post("/api/login", json={"email": "u1@example.com", "password": "another pass"})
    walk_in = {"doctor_id": "dr-test", "date": "2026-10-28", "time": "10:00", "name": "Walk In"}
    bid = owner.post("/api/desk/bookings", json=walk_in).json()["id"]
    owner.post(f"/api/desk/bookings/{bid}/status", json={"status": "arrived"})
    s = owner.get("/api/settings").json()["settings"]
    owner.put(
        "/api/settings",
        json={
            k: s[k]
            for k in ("name", "address", "sessions", "slot_min", "doctors", "emergency_instruction")
        },
    )
    owner.post(
        "/api/feedback",
        json={
            "person_name": "Doctor A",
            "person_role": "Owner",
            "text": "Works well",
            "type": "feature",
        },
    )
    got = counts(tid)
    assert got == {
        "signup": 1,
        "login": 1,
        "booking_created": 1,
        "booking_status": 1,
        "settings_saved": 1,
        "feedback_sent": 1,
    }


def test_orders_catalogue_and_callbacks_are_counted(env):
    with TestClient(app, headers=APP_HEADERS) as shop:
        signup(shop, "wholesale", 2, "+919000000402")
        tid = tid_of(shop)
        shop.post("/api/catalog", json={"name": "Surgical gloves", "rate": "450"})
        shop.post(
            "/api/catalog/import",
            content=b"name,rate\nCotton roll,58\n",
            headers={"Content-Type": "text/csv"},
        )
        pid = shop.get("/api/catalog").json()["products"][0]["id"]
        oid = shop.post(
            "/api/orders",
            json={"shop_name": "Test Medical", "items": [{"product_id": pid, "qty": 1}]},
        ).json()["id"]
        shop.post(f"/api/orders/{oid}/status", json={"status": "confirmed"})
        shop.post(f"/api/orders/{oid}/status", json={"status": "delivered"})  # invalid: not counted
    conn = db.connect().for_tenant(tid)
    try:
        from src import inbox

        inbox.create(conn, "callback", name="Caller", reason="other")
        inbox.create(conn, "ops", reason="whatsapp_unparsed")  # not a callback
    finally:
        conn.close()
    got = counts(tid)
    assert (got["catalog_updated"], got["order_created"], got["order_status"]) == (2, 1, 1)
    assert got["callback_created"] == 1


def test_whatsapp_messages_and_ended_calls_are_counted(owner):
    tid = tid_of(owner)
    r = owner.post(
        "/whatsapp/incoming",
        content=urlencode({"From": f"whatsapp:{OWNER}", "Body": "help"}),
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    owner.post(  # an unknown number: no business, nothing counted
        "/whatsapp/incoming",
        content=urlencode({"From": "whatsapp:+919000000499", "Body": "help"}),
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    conn = db.connect_unchecked()
    try:
        t = tenancy.get(conn, tid)
    finally:
        conn.close()
    report = {"message": {"type": "end-of-call-report", "call": {"id": "call-x"}}}
    for _ in range(2):  # Vapi may resend the report: it counts once
        owner.post(
            f"/vapi/webhook/{t['public_id']}",
            json=report,
            headers={"x-catalyst-secret": t["tool_secret"]},
        )
    got = counts(tid)
    assert got["wa_command"] == 1 and got["call_ended"] == 1


def test_an_unknown_event_type_is_refused(conn):
    with pytest.raises(ValueError):
        analytics.record(conn, "made_up")


# Weekly buckets


def test_week_starts_are_the_last_four_mondays():
    assert analytics.week_starts(FIXED_NOW.date()) == [
        date(2026, 10, 5),
        date(2026, 10, 12),
        date(2026, 10, 19),
        date(2026, 10, 26),
    ]
    assert analytics.week_starts(date(2026, 10, 26))[-1] == date(2026, 10, 26)  # Monday itself


def put_event(tid, type_, at):
    conn = db.connect_unchecked()
    try:
        with conn:
            conn.execute(
                "INSERT INTO events (tenant_id, type, created_at) VALUES (?, ?, ?)",
                (tid, type_, at),
            )
    finally:
        conn.close()


def test_admin_counts_and_weekly_breakdown(admin, env):
    with TestClient(app, headers=APP_HEADERS) as owner:
        signup(owner)
        tid = tid_of(owner)
    for type_, at in (
        ("booking_created", "2026-10-25T23:59:59+05:30"),  # Sunday: week of 19 Oct
        ("booking_created", "2026-10-26T00:00:00+05:30"),  # Monday: this week
        ("call_ended", "2026-10-26T10:00:00+05:30"),
        ("wa_command", "2026-10-12T09:00:00+05:30"),
        ("order_created", "2026-10-04T23:59:59+05:30"),  # before the 4 weeks: totals only
    ):
        put_event(tid, type_, at)
    found = {b["id"]: b for b in admin.get("/api/admin/businesses").json()["businesses"]}
    b = found[tid]
    assert (b["template"], b["users"], b["is_demo"]) == ("clinic", 1, False)
    assert (b["records"], b["calls"], b["wa_commands"]) == (3, 1, 1)
    assert b["last_active"].startswith("2026-10-27")  # the signup and login, on the fixed clock
    weeks = {w["week_start"]: w for w in b["weeks"]}
    assert list(weeks) == ["2026-10-05", "2026-10-12", "2026-10-19", "2026-10-26"]
    assert weeks["2026-10-19"]["records"] == 1 and weeks["2026-10-26"]["records"] == 1
    assert weeks["2026-10-26"]["calls"] == 1 and weeks["2026-10-12"]["wa_commands"] == 1
    assert weeks["2026-10-05"]["records"] == 0
    assert any(x["is_demo"] for x in found.values())  # the demo clinic is listed too


def test_usage_csv_is_counts_only(admin, env):
    with TestClient(app, headers=APP_HEADERS) as owner:
        signup(owner)
        tid = tid_of(owner)
        walk_in = {
            "doctor_id": "dr-test",
            "date": "2026-10-28",
            "time": "10:00",
            "name": "Ramesh Kumar",
            "phone": "98765 43210",
        }
        owner.post("/api/desk/bookings", json=walk_in)
    r = admin.get(f"/api/admin/businesses/{tid}/usage.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0] == ["week_start", "events", "records", "calls", "wa_commands", "logins"]
    assert [x[0] for x in rows[1:]] == [
        "2026-10-05",
        "2026-10-12",
        "2026-10-19",
        "2026-10-26",
        "total",
    ]
    assert rows[4][2] == "1" and rows[5][2] == "1"  # this week's booking, and the total
    for secret in ("Ramesh", "98765", "43210", "Usage Business", OWNER[3:]):
        assert secret not in r.text
    assert admin.get("/api/admin/businesses/nope/usage.csv").status_code == 404


# Admin login


def test_admin_routes_need_the_admin_login(env):
    with TestClient(app, headers=APP_HEADERS) as c:
        signup(c)  # an owner session is not an admin session
        for path in ("/api/admin/businesses", "/api/admin/feedback", "/api/admin/feedback.csv"):
            r = c.get(path)
            assert r.status_code == 401 and r.json()["code"] == "UNAUTHENTICATED", path


def test_admin_login_wrong_password_and_lockout(env):
    with TestClient(app, headers=APP_HEADERS) as c:
        for _ in range(5):
            assert c.post("/api/admin/login", json={"password": "wrong"}).status_code == 401
        r = c.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
        assert r.status_code == 429 and r.json()["code"] == "LOCKED"


def test_no_admin_password_means_no_admin(isolated, monkeypatch):
    from src.accounts import service

    service._admin_failures.clear()  # the lockout counter lives in the process
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    with TestClient(app, headers=APP_HEADERS) as c:
        assert c.post("/api/admin/login", json={"password": ""}).status_code == 422
        assert c.post("/api/admin/login", json={"password": "anything"}).status_code == 401


def test_unsetting_the_password_ends_admin_sessions(admin, monkeypatch):
    assert admin.get("/api/admin/businesses").status_code == 200
    monkeypatch.delenv("ADMIN_PASSWORD")
    assert admin.get("/api/admin/businesses").status_code == 401


# Feedback


def send(c, **kw):
    body = {
        "person_name": "Doctor A",
        "person_role": "Owner",
        "text": "Calls are clear",
        "type": "feature",
    }
    return c.post("/api/feedback", json=body | kw)


def test_feedback_needs_a_login_and_a_known_type(owner, env):
    assert send(owner, type="complaint").status_code == 422
    assert send(owner, text="").status_code == 422
    assert send(owner).json()["saved"] is True
    with TestClient(app, headers=APP_HEADERS) as anon:
        assert send(anon).status_code == 401


def test_feedback_log_decisions_and_csv(owner, admin):
    first = send(owner, text="Booking read-back is slow", type="usability").json()["id"]
    second = send(
        owner,
        text="Please add SMS",
        type="feature",
        person_name="The receptionist",
        person_role="Staff",
    ).json()["id"]
    listed = admin.get("/api/admin/feedback").json()["feedback"]
    assert [f["id"] for f in listed] == [second, first]  # newest first
    r = admin.put(f"/api/admin/feedback/{second}", json={"decision": "wont_do"})
    assert r.status_code == 422 and "decision_reason" in r.json()["fields"]
    r = admin.put(
        f"/api/admin/feedback/{first}", json={"decision": "shipped", "evidence_url": "not a link"}
    )
    assert r.status_code == 422 and "evidence_url" in r.json()["fields"]
    admin.put(
        f"/api/admin/feedback/{second}",
        json={"decision": "wont_do", "decision_reason": "SMS needs DLT approval first"},
    )
    admin.put(
        f"/api/admin/feedback/{first}",
        json={
            "decision": "shipped",
            "shipped_on": "2026-11-14",
            "evidence_url": "https://github.com/example/pull/1",
            "partner_reaction": "Much better",
        },
    )
    assert admin.put("/api/admin/feedback/9999", json={"decision": "planned"}).status_code == 404
    rows = list(csv.reader(io.StringIO(admin.get("/api/admin/feedback.csv").text)))
    assert rows[0] == [
        "Date",
        "Partner and person",
        "What they said",
        "Type",
        "Decision",
        "Shipped on",
        "Evidence",
        "Partner's reaction",
    ]
    assert rows[1] == [
        "2026-10-27",
        "Usage Business 1 — The receptionist (Staff)",
        "Please add SMS",
        "Feature",
        "Won't do: SMS needs DLT approval first",
        "",
        "",
        "",
    ]
    assert rows[2][3:] == [
        "Usability",
        "Shipped",
        "2026-11-14",
        "https://github.com/example/pull/1",
        "Much better",
    ]

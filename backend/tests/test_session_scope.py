"""Phase 2 M2b: the desk and settings serve only the logged-in owner's business."""

import httpx
import pytest
from conftest import APP_HEADERS, DEMO_PASSWORD
from fastapi.testclient import TestClient

from src import accounts
from src.core import db, tenancy
from src.main import app


def signup_body(template="clinic", n=1):
    body = {
        "user": {"name": "Owner Two", "email": f"owner{n}@example.com", "password": "another pass"},
        "business": {
            "template": template,
            "name": f"Second Business {n}",
            "address": "1 Test Road",
            "hours": [["09:00", "13:00"]],
            "owner_whatsapp": f"90000 0000{n}",
            "consent": True,
        },
        "details": {"doctors": [{"name": "Dr. Second One"}]} if template == "clinic" else {},
    }
    return body


@pytest.fixture
def other(owner):
    """A second business (clinic), logged in on its own client. `owner` is the demo clinic."""
    with TestClient(app, headers=APP_HEADERS) as c:
        r = c.post("/api/signup", json=signup_body())
        assert r.status_code == 200, r.text
        yield c


def demo_id():
    conn = db.connect_unchecked()
    try:
        return tenancy.demo_id(conn, "clinic")
    finally:
        conn.close()


def test_each_owner_sees_only_their_inbox(owner, other):
    mine = owner.get("/api/inbox").json()
    assert mine, "the demo seed has an open callback"
    assert other.get("/api/inbox").json() == []
    r = other.post(f"/api/inbox/{mine[0]['id']}/done")
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"
    assert owner.get("/api/inbox").json() == mine  # still open


def test_each_owner_sees_only_their_schedule(owner, other):
    names = {c["doctor"]["name"] for c in other.get("/api/desk/day").json()["columns"]}
    assert names == {"Dr. Second One"}
    walk_in = {"doctor_id": "dr-b", "date": "2026-10-28", "time": "12:00", "name": "Walk In"}
    bid = owner.post("/api/desk/bookings", json=walk_in).json()["id"]
    r = other.post(f"/api/desk/bookings/{bid}/status", json={"status": "cancelled"})
    assert r.status_code == 404
    day = owner.get("/api/desk/day", params={"date": "2026-10-28"}).json()
    held = [b for c in day["columns"] for s in c["slots"] for b in s["bookings"] if b["id"] == bid]
    assert held and held[0]["status"] == "booked"


def test_each_owner_sees_only_their_calls(owner, other, raw):
    with raw:
        raw.execute(
            "INSERT INTO calls (tenant_id, id, started_at) VALUES (?, ?, ?)",
            (demo_id(), "call-demo", "2026-10-27T08:00:00+05:30"),
        )
    assert [c["id"] for c in owner.get("/api/calls").json()] == ["call-demo"]
    assert other.get("/api/calls").json() == []
    assert other.get("/api/stats").json()["sentence"].startswith("Today: 0 calls")


def test_settings_save_changes_only_this_business(owner, other):
    before = owner.get("/api/settings").json()["settings"]
    mine = other.get("/api/settings").json()["settings"]
    assert mine["name"] == "Second Business 1" and before["name"] != mine["name"]
    fields = ("name", "city", "address", "landmark", "sessions", "closed_weekdays", "slot_min")
    body = {k: mine[k] for k in fields} | {
        "doctors": mine["doctors"],
        "emergency_instruction": mine["emergency_instruction"],
        "name": "Renamed Second",
    }
    r = other.put("/api/settings", json=body)
    assert r.status_code == 200 and r.json()["saved"] is True
    assert other.get("/api/settings").json()["settings"]["name"] == "Renamed Second"
    assert owner.get("/api/settings").json()["settings"] == before


def test_leave_of_another_business_cant_be_removed(owner, other):
    block = owner.post("/api/settings/blocks", json={"date": "2026-10-28", "doctor_id": "dr-b"})
    bid = block.json()["blocks"][0]["id"]
    assert other.delete(f"/api/settings/blocks/{bid}").status_code == 404
    assert len(owner.get("/api/settings").json()["blocks"]) == 1


def test_settings_save_patches_only_its_own_assistant(owner, isolated, monkeypatch):
    """The demo assistant is configured in .env too: a save by the second business must PATCH only
    the second business's own assistant."""
    isolated.write_text(
        "PUBLIC_URL=https://api.example.com\nVAPI_PRIVATE_KEY=k\nVAPI_ASSISTANT_ID=asst-demo\n"
        "CATALYST_TOOL_SECRET=s\n",
        encoding="utf-8",
    )
    seen = []

    def fake(method, url, json=None, timeout=None, headers=None):
        seen.append((method, url))
        return httpx.Response(200, json={"id": "asst-second"}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "request", fake)
    with TestClient(app, headers=APP_HEADERS) as c:
        assert c.post("/api/signup", json=signup_body()).json()["agent"] == "updated"
        s = c.get("/api/settings").json()
        assert s["agentConfigured"] is True
        seen.clear()
        body = {
            k: s["settings"][k]
            for k in ("name", "address", "sessions", "slot_min", "doctors", "emergency_instruction")
        }
        assert c.put("/api/settings", json=body).json()["agent"].startswith("Saved. The agent")
    assert seen == [("PATCH", "https://api.vapi.ai/assistant/asst-second")]


def test_wholesale_owner_has_no_schedule_but_has_the_shared_panels(isolated):
    with TestClient(app, headers=APP_HEADERS) as c:
        assert c.post("/api/signup", json=signup_body("wholesale", 2)).status_code == 200
        r = c.get("/api/desk/day")
        assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"
        assert c.get("/api/inbox").json() == [] and c.get("/api/calls").json() == []
        assert c.get("/api/settings").json()["blocks"] == []
        assert c.post("/api/settings/blocks", json={"date": "2026-10-28"}).status_code == 404


def login(c, password):
    return c.post("/api/login", json={"email": accounts.DEMO_EMAIL, "password": password})


def test_no_demo_login_without_the_variable(isolated):
    with TestClient(app, headers=APP_HEADERS) as c:
        assert login(c, DEMO_PASSWORD).status_code == 401


def test_too_short_demo_password_makes_no_login(isolated, monkeypatch):
    monkeypatch.setenv("DEMO_LOGIN_PASSWORD", "short")
    with TestClient(app, headers=APP_HEADERS) as c:
        assert login(c, "short").status_code == 401


def test_changing_the_demo_password_takes_effect_on_restart(isolated, monkeypatch):
    monkeypatch.setenv("DEMO_LOGIN_PASSWORD", DEMO_PASSWORD)
    with TestClient(app, headers=APP_HEADERS) as c:
        assert login(c, DEMO_PASSWORD).status_code == 200
        old_cookie = c.cookies.get(accounts.COOKIE)
    monkeypatch.setenv("DEMO_LOGIN_PASSWORD", "a-new-demo-pass")
    with TestClient(app, headers=APP_HEADERS) as c:
        assert login(c, DEMO_PASSWORD).status_code == 401
        c.cookies.set(accounts.COOKIE, old_cookie)
        assert c.get("/api/me").status_code == 401  # the old password's sessions ended
        assert login(c, "a-new-demo-pass").status_code == 200
        assert c.get("/api/me").json()["business"]["template"] == "clinic"


def test_demo_email_taken_by_another_business_is_left_alone(isolated, monkeypatch):
    with TestClient(app, headers=APP_HEADERS) as c:
        body = signup_body()
        body["user"]["email"] = accounts.DEMO_EMAIL
        assert c.post("/api/signup", json=body).status_code == 200
    monkeypatch.setenv("DEMO_LOGIN_PASSWORD", DEMO_PASSWORD)
    with TestClient(app, headers=APP_HEADERS) as c:
        assert login(c, DEMO_PASSWORD).status_code == 401  # that owner's password is unchanged
        assert login(c, "another pass").status_code == 200
        assert c.get("/api/me").json()["business"]["name"] == "Second Business 1"

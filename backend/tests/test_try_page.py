"""Issue #24: the public per-business test page API (/api/try/{public_id})."""

from datetime import timedelta

import pytest
from conftest import APP_HEADERS, FIXED_NOW
from fastapi.testclient import TestClient

from src.core import config, db, tenancy
from src.main import app

DEMO = "demo-clinic"


@pytest.fixture
def client(isolated):
    with TestClient(app, headers=APP_HEADERS) as c:
        yield c


def signup(client, template="clinic", n=1):
    body = {
        "user": {"name": "Owner", "email": f"o{n}@example.com", "password": "another pass"},
        "business": {
            "template": template,
            "name": f"Business {n}",
            "city": "Test City",
            "address": "1 Test Road",
            "hours": [["09:00", "13:00"]],
            "owner_whatsapp": f"90000 0001{n}",
            "consent": True,
        },
        "details": {"doctors": [{"name": "Dr. Test"}]} if template == "clinic" else {},
    }
    r = client.post("/api/signup", json=body)
    assert r.status_code == 200, r.text
    client.cookies.clear()  # the test page is public: no session needed
    return r.json()["public_id"]


def set_assistant(public_id, assistant_id):
    conn = db.connect_unchecked()
    try:
        t = tenancy.by_public_id(conn, public_id)
        tenancy.set_assistant(conn.for_tenant(t["id"]), assistant_id)
    finally:
        conn.close()


def env(isolated, **values):
    isolated.write_text("".join(f"{k}={v}\n" for k, v in values.items()), encoding="utf-8")


@pytest.mark.parametrize("path", ["", "/board"])
def test_unknown_business_is_404(client, path):
    r = client.get(f"/api/try/nope{path}")
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"


def test_unknown_business_start_is_404(client):
    r = client.post("/api/try/nope/start")
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"


def test_page_info_comes_from_the_business_and_its_template(client):
    pid = signup(client, "wholesale", 2)
    info = client.get(f"/api/try/{pid}").json()
    assert info["public_id"] == pid and info["name"] == "Business 2" and info["city"] == "Test City"
    assert info["template"] == "wholesale" and info["modules"] == ["orders"]
    assert info["labels"]["tenant"] == "Distributor"
    assert 3 <= len(info["try_saying"]) <= 5
    assert info["voice"] is None


def test_voice_is_the_businesses_own_assistant(client, isolated):
    pid = signup(client)
    env(isolated, VAPI_PUBLIC_KEY="pk", VAPI_ASSISTANT_ID="asst-demo")
    assert client.get(f"/api/try/{pid}").json()["voice"] is None  # never the demo's assistant
    set_assistant(pid, "asst-own")
    voice = client.get(f"/api/try/{pid}").json()["voice"]
    assert voice == {"public_key": "pk", "assistant_id": "asst-own"}


def test_demo_clinic_falls_back_to_the_env_assistant(client, isolated):
    env(isolated, VAPI_PUBLIC_KEY="pk", VAPI_ASSISTANT_ID="asst-demo")
    voice = client.get(f"/api/try/{DEMO}").json()["voice"]
    assert voice == {"public_key": "pk", "assistant_id": "asst-demo"}
    assert client.post(f"/api/try/{DEMO}/start").status_code == 200


def test_no_public_key_means_no_voice(client, isolated):
    env(isolated, VAPI_ASSISTANT_ID="asst-demo")
    assert client.get(f"/api/try/{DEMO}").json()["voice"] is None
    r = client.post(f"/api/try/{DEMO}/start")
    assert r.status_code == 503 and r.json()["code"] == "VOICE_NOT_CONFIGURED"


def test_start_needs_the_app_header(client, isolated):
    env(isolated, VAPI_PUBLIC_KEY="pk", VAPI_ASSISTANT_ID="asst-demo")
    r = client.post(f"/api/try/{DEMO}/start", headers={"X-Requested-With": ""})
    assert r.status_code == 403


def test_per_business_daily_cap(client, isolated):
    env(isolated, VAPI_PUBLIC_KEY="pk", VAPI_ASSISTANT_ID="asst-demo", CALLS_PER_BUSINESS_PER_DAY=2)
    for _ in range(2):
        r = client.post(f"/api/try/{DEMO}/start")
        assert r.status_code == 200 and r.json() == {"max_call_seconds": 180}
    r = client.post(f"/api/try/{DEMO}/start")
    assert r.status_code == 429 and r.json()["code"] == "MINUTES_USED_UP"
    assert "tomorrow" in r.json()["detail"]


def test_overall_daily_cap_counts_every_business(client, isolated):
    pid = signup(client)
    set_assistant(pid, "asst-own")
    env(isolated, VAPI_PUBLIC_KEY="pk", VAPI_ASSISTANT_ID="asst-demo", DEMO_CALLS_PER_DAY=3)
    for public_id in (DEMO, DEMO, pid):
        assert client.post(f"/api/try/{public_id}/start").status_code == 200
    assert client.post(f"/api/try/{pid}/start").status_code == 429
    assert client.post(f"/api/try/{DEMO}/start").status_code == 429


def test_caps_reset_the_next_day(client, isolated, monkeypatch):
    env(isolated, VAPI_PUBLIC_KEY="pk", VAPI_ASSISTANT_ID="asst-demo", CALLS_PER_BUSINESS_PER_DAY=1)
    assert client.post(f"/api/try/{DEMO}/start").status_code == 200
    assert client.post(f"/api/try/{DEMO}/start").status_code == 429
    monkeypatch.setattr(config, "now", lambda: FIXED_NOW + timedelta(days=1))
    assert client.post(f"/api/try/{DEMO}/start").status_code == 200


def test_board_has_masked_names_and_no_phones(client, raw):
    board = client.get(f"/api/try/{DEMO}/board").json()
    assert board["kind"] == "bookings" and [d["label"] for d in board["days"]] == [
        "Today",
        "Tomorrow",
    ]
    slots = [s for d in board["days"] for c in d["columns"] for s in c["slots"]]
    assert all(set(s) == {"time", "state", "booking"} for s in slots)
    assert all("resource" in c for d in board["days"] for c in d["columns"])
    booked = [s["booking"] for s in slots if s["booking"]]
    assert booked, "the demo seed has bookings today or tomorrow"
    full = {r["name"] for r in raw.execute("SELECT name FROM bookings").fetchall()}
    phones = [
        r["phone"] for r in raw.execute("SELECT phone FROM bookings").fetchall() if r["phone"]
    ]
    text = str(board)
    assert not any(p in text or p[-10:] in text for p in phones)
    assert all(b["name"] not in full or " " not in b["name"] for b in booked)


def test_one_business_board_never_shows_another(client):
    pid = signup(client)
    board = client.get(f"/api/try/{pid}/board").json()
    assert [c["resource"] for c in board["days"][0]["columns"]] == ["Dr. Test"]
    assert not [s for d in board["days"] for c in d["columns"] for s in c["slots"] if s["booking"]]


def test_orders_board_is_empty_until_m4(client):
    pid = signup(client, "wholesale", 3)
    assert client.get(f"/api/try/{pid}/board").json() == {"kind": "orders", "orders": []}

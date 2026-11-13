import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client(owner):
    return owner


def test_desk_apis_need_a_login(isolated):
    with TestClient(app) as anon:
        for path in ("/api/inbox", "/api/calls", "/api/stats", "/api/desk/day", "/api/staff/meta"):
            r = anon.get(path)
            assert r.status_code == 401 and r.json()["code"] == "UNAUTHENTICATED", path
        # The desk page is the React app on Vercel; this backend serves no HTML.
        assert anon.get("/desk").status_code == 404
        assert anon.get("/api/register").status_code == 200  # the public page stays public


def test_writes_need_the_app_header(client):
    r = client.post("/api/desk/summary/send", headers={"X-Requested-With": ""})
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"


def test_walk_in_conflict_and_status(client):
    body = {
        "doctor_id": "dr-b",
        "date": "2026-10-28",
        "time": "12:00",
        "name": "Walk In",
        "phone": "98765 43210",
    }
    first = client.post("/api/desk/bookings", json=body)
    assert first.status_code == 200
    again = client.post("/api/desk/bookings", json={**body, "name": "Other"})
    assert again.status_code == 409 and "Free nearby" in again.json()["detail"]
    assert again.json()["code"] == "SLOT_TAKEN" and again.json()["alternatives"]
    bid = first.json()["id"]
    assert (
        client.post(f"/api/desk/bookings/{bid}/status", json={"status": "arrived"}).status_code
        == 200
    )
    day = client.get("/api/desk/day", params={"date": "2026-10-28"}).json()
    slot = next(
        s
        for c in day["columns"]
        if c["doctor"]["id"] == "dr-b"
        for s in c["slots"]
        if s["time"] == "12:00"
    )
    assert slot["state"] == "booked" and slot["bookings"][0]["status"] == "arrived"
    assert (
        client.post(f"/api/desk/bookings/{bid}/status", json={"status": "bogus"}).status_code == 422
    )


def test_bad_phone_rejected(client):
    r = client.post(
        "/api/desk/bookings",
        json={
            "doctor_id": "dr-a",
            "date": "2026-10-28",
            "time": "12:00",
            "name": "X",
            "phone": "12345",
        },
    )
    assert r.status_code == 422


def test_inbox_done_and_stats(client):
    items = client.get("/api/inbox").json()
    assert items, "the seed has one open callback"
    assert client.post(f"/api/inbox/{items[0]['id']}/done").status_code == 200
    assert client.post(f"/api/inbox/{items[0]['id']}/done").status_code == 404
    assert (
        client.get("/api/stats").json()["sentence"]
        == "Today: 0 calls, 0 booked, 0 urgent, 0 callbacks open."
    )


def test_summary_without_numbers_explains(client):
    r = client.post("/api/desk/summary/send").json()
    assert r["sent"] == 0 and "settings page" in r["note"] and "summary" in r["text"]

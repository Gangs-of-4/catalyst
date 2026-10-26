import httpx
import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client(isolated):
    with TestClient(app) as c:
        yield c


def current(client):
    s = client.get("/api/setup").json()["settings"]
    return {k: s[k] for k in ("name", "city", "address", "landmark", "sessions", "closed_weekdays", "slot_min",
                              "doctors", "services", "faqs", "red_flags", "emergency_instruction",
                              "whatsapp_numbers", "voice")}


def test_save_without_agent_says_so(client):
    body = {**current(client), "name": "Muskaan Dental Care", "whatsapp_numbers": ["98765 43210"]}
    r = client.put("/api/setup", json=body).json()
    assert r["settings"]["name"] == "Muskaan Dental Care"
    assert r["settings"]["whatsapp_numbers"] == ["+919876543210"]
    assert "isn't set up" in r["agent"]


def test_save_syncs_agent_and_reports_error(client, isolated, monkeypatch):
    isolated.write_text("VAPI_PRIVATE_KEY=k\nVAPI_ASSISTANT_ID=a1\nPUBLIC_URL=https://x.trycloudflare.com\n"
                        "CATALYST_TOOL_SECRET=s\n", encoding="utf-8")
    calls = []

    def fake(method, url, json=None, **kw):
        calls.append((method, url, json))
        return httpx.Response(200, json={"id": "a1"}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "request", fake)
    r = client.put("/api/setup", json={**current(client), "voice": "male"}).json()
    assert r["agent"] == "Agent updated (a1)."
    method, url, payload = calls[-1]
    assert (method, url) == ("PATCH", "https://api.vapi.ai/assistant/a1")
    assert payload["voice"]["voiceId"] == "hi-IN-MadhurNeural"

    monkeypatch.setattr(httpx, "request", lambda m, u, **k: httpx.Response(
        400, text='{"message":"bad voice"}', request=httpx.Request(m, u)))
    r = client.put("/api/setup", json=current(client)).json()
    assert "failed" in r["agent"] and "bad voice" in r["agent"]


@pytest.mark.parametrize("change, message", [
    ({"sessions": [["14:00", "10:00"]]}, "start before end"),
    ({"whatsapp_numbers": ["12345"]}, "not a 10-digit"),
    ({"doctors": []}, ""),
])
def test_validation_is_readable(client, change, message):
    r = client.put("/api/setup", json={**current(client), **change})
    assert r.status_code == 422 and isinstance(r.json()["detail"], str) and message in r.json()["detail"]


def test_new_doctor_gets_stable_id_and_old_ids_kept(client):
    body = current(client)
    body["doctors"] = body["doctors"] + [{"id": None, "name": "Dr. Meera Joshi"}]
    docs = client.put("/api/setup", json=body).json()["settings"]["doctors"]
    assert [d["id"] for d in docs] == ["dr-a", "dr-b", "dr-meera-joshi"]


def test_cannot_remove_doctor_with_upcoming_bookings(client):
    body = current(client)
    body["doctors"] = [d for d in body["doctors"] if d["id"] != "dr-a"]
    r = client.put("/api/setup", json=body)
    assert r.status_code == 422 and "upcoming booking" in r.json()["detail"]


def test_leave_add_and_remove(client):
    r = client.post("/api/setup/blocks", json={"date": "2026-10-28", "doctor_id": "dr-b"}).json()
    assert len(r["blocks"]) == 1 and "Dr. Vikram Saxena" in r["blocks"][0]["label"] and r["note"]
    r = client.delete(f"/api/setup/blocks/{r['blocks'][0]['id']}").json()
    assert r["blocks"] == []
    assert client.post("/api/setup/blocks", json={"date": "2026-01-01"}).status_code == 422

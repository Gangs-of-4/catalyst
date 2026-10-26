import httpx

from src.agents import prompt
from src.core import config
from src.providers.voice_orchestrator import vapi


def test_prompt_has_snapshot_rules_and_no_placeholders(conn, settings):
    system, first = prompt.build(conn, settings)
    assert "Muskaan Dental Clinic" in system and "Muskaan Dental Clinic" in first
    assert "108" in system                        # emergency instruction
    assert "Dr. Vikram Saxena" in system           # doctors in the snapshot
    assert "Cleaning and scaling: ₹800" in system  # fees
    assert "feminine verb forms" in system
    assert "{" not in system.replace("{ ", "") and "{" not in first
    assert "automated assistant" in first


def test_male_voice_changes_forms_and_greeting(conn, settings):
    settings["voice"] = "male"
    system, first = prompt.build(conn, settings)
    assert "masculine verb forms" in system and "का automated assistant" in first


def test_payload_shape(conn, isolated, monkeypatch):
    isolated.write_text("PUBLIC_URL=https://demo.trycloudflare.com\n", encoding="utf-8")
    body = vapi.payload(conn, "sek")
    server = {"url": "https://demo.trycloudflare.com/vapi/webhook", "headers": {"x-catalyst-secret": "sek"}}
    assert body["server"] == server and body["serverMessages"] == ["end-of-call-report"]
    names = [t["function"]["name"] for t in body["model"]["tools"] if t["type"] == "function"]
    assert {"find_slots", "book", "find_booking", "escalate", "create_callback"} <= set(names)
    assert all(t["server"] == server for t in body["model"]["tools"] if t["type"] == "function")
    assert body["model"]["tools"][-1] == {"type": "endCall"}
    assert body["voice"] == {"provider": "azure", "voiceId": "hi-IN-SwaraNeural"}
    assert body["transcriber"]["model"] == "nova-3"


def test_sync_creates_then_updates_and_writes_env(conn, isolated, monkeypatch):
    isolated.write_text("PUBLIC_URL=https://demo.trycloudflare.com\nVAPI_PRIVATE_KEY=k\n", encoding="utf-8")
    seen = []

    def fake(method, url, json=None, timeout=None, headers=None):
        seen.append((method, url))
        return httpx.Response(201, json={"id": "asst-1"}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "request", fake)
    assert "created" in vapi.sync(conn)
    assert config.env("VAPI_ASSISTANT_ID") == "asst-1" and config.env("CATALYST_TOOL_SECRET")
    assert "updated" in vapi.sync(conn)
    assert seen == [("POST", "https://api.vapi.ai/assistant"), ("PATCH", "https://api.vapi.ai/assistant/asst-1")]
    assert "PUBLIC_URL=https://demo.trycloudflare.com" in isolated.read_text(encoding="utf-8")


def test_sync_reports_vapi_error_body(conn, isolated, monkeypatch):
    isolated.write_text("PUBLIC_URL=https://x.trycloudflare.com\nVAPI_PRIVATE_KEY=k\n", encoding="utf-8")
    monkeypatch.setattr(httpx, "request", lambda m, u, **k: httpx.Response(
        400, json={"message": ["voice.voiceId must be valid"]}, request=httpx.Request(m, u)))
    try:
        vapi.sync(conn)
    except vapi.VapiError as e:
        assert "400" in str(e) and "voiceId" in str(e)
    else:
        raise AssertionError("expected VapiError")

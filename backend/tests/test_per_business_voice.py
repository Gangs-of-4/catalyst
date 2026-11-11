"""Phase 2 M3: each business has its own webhook path, secret, prompt and assistant."""

import httpx
import pytest
from fastapi.testclient import TestClient

from src import seed
from src.agents import prompt
from src.api import sync
from src.core import db, tenancy
from src.core import settings as cs
from src.main import app
from src.providers.voice_orchestrator import vapi


@pytest.fixture
def client(isolated):
    with TestClient(app) as c:
        yield c


def make(template: str, name: str, **kw) -> tuple[str, str, str]:
    """(tenant id, public_id, secret) for a new business of `template`."""
    conn = db.connect_unchecked()
    try:
        s = {**cs_defaults(), "name": name}
        tid = tenancy.create(conn, template, s, **kw)
        t = tenancy.get(conn, tid)
        return tid, t["public_id"], t["tool_secret"]
    finally:
        conn.close()


def cs_defaults() -> dict:
    conn = db.connect()
    try:
        return dict(cs.load(conn.for_tenant(seed.ensure(conn, with_demo_data=False))))
    finally:
        conn.close()


def callback_call(public_id, secret, tc_id="tc-1"):
    body = {
        "message": {
            "type": "tool-calls",
            "call": {"id": "call-1", "type": "webCall"},
            "toolCallList": [
                {
                    "id": tc_id,
                    "type": "function",
                    "function": {
                        "name": "create_callback",
                        "arguments": {"name": "Ravi", "phone": "9876500001", "reason": "other"},
                    },
                }
            ],
        }
    }
    headers = {"x-catalyst-secret": secret} if secret else {}
    return body, headers


def inbox_count(tid):
    conn = db.connect_unchecked()
    try:
        return conn.execute("SELECT COUNT(*) FROM inbox WHERE tenant_id = ?", (tid,)).fetchone()[0]
    finally:
        conn.close()


@pytest.mark.parametrize("template", ["clinic", "wholesale"])
def test_webhook_routes_to_the_business_in_the_path(client, template):
    tid, pid, secret = make(template, f"Routing {template}")
    other, _, _ = make("clinic" if template == "wholesale" else "wholesale", "Bystander")
    body, headers = callback_call(pid, secret)
    r = client.post(f"/vapi/webhook/{pid}", json=body, headers=headers)
    assert r.status_code == 200 and r.json()["results"][0]["toolCallId"] == "tc-1"
    assert inbox_count(tid) == 1 and inbox_count(other) == 0


def test_wrong_or_missing_secret_is_401(client):
    tid, pid, secret = make("clinic", "Secrets")
    body, _ = callback_call(pid, secret)
    assert client.post(f"/vapi/webhook/{pid}", json=body).status_code == 401
    bad = client.post(f"/vapi/webhook/{pid}", json=body, headers={"x-catalyst-secret": "nope"})
    assert bad.status_code == 401
    assert inbox_count(tid) == 0


def test_another_business_secret_never_authorises(client):
    _, pid_a, _ = make("clinic", "Clinic A")
    tid_b, _, secret_b = make("wholesale", "Shop B")
    body, headers = callback_call(pid_a, secret_b)
    assert client.post(f"/vapi/webhook/{pid_a}", json=body, headers=headers).status_code == 401
    assert inbox_count(tid_b) == 0


def test_unknown_public_id_is_404(client):
    body, headers = callback_call("nope", "whatever")
    assert client.post("/vapi/webhook/nope", json=body, headers=headers).status_code == 404


def test_same_tool_call_id_in_two_businesses_does_not_collide(client):
    _, pa, sa = make("clinic", "Clinic A")
    _, pb, sb = make("wholesale", "Shop B")
    for pid, secret in ((pa, sa), (pb, sb)):
        body, headers = callback_call(pid, secret, tc_id="same-id")
        assert client.post(f"/vapi/webhook/{pid}", json=body, headers=headers).status_code == 200
    assert inbox_count(tenancy_id(pa)) == 1 and inbox_count(tenancy_id(pb)) == 1


def tenancy_id(public_id):
    conn = db.connect_unchecked()
    try:
        return tenancy.by_public_id(conn, public_id)["id"]
    finally:
        conn.close()


def test_prompt_uses_the_businesses_template(conn):
    system, _ = prompt.build(conn, cs.load(conn))
    assert "Muskaan Dental Clinic" in system


def test_template_without_prompt_raises_no_prompt(isolated):
    tid, _, _ = make("wholesale", "No prompt yet")
    conn = db.connect().for_tenant(tid)
    try:
        with pytest.raises(prompt.NoPrompt):
            prompt.build(conn, cs.load(conn))
    finally:
        conn.close()


def test_assistant_tools_come_from_the_template(conn):
    names = {fn["name"] for fn in vapi.template_tools(conn)}
    assert {"find_slots", "book", "escalate", "create_callback"} <= names
    assert "get_catalog" not in names


def configure(isolated):
    isolated.write_text(
        "PUBLIC_URL=https://api.example.com\nVAPI_PRIVATE_KEY=k\n", encoding="utf-8"
    )


def test_settings_save_patches_only_this_businesses_assistant(isolated, monkeypatch):
    configure(isolated)
    a, _, _ = make("clinic", "Clinic A")
    b, _, _ = make("clinic", "Clinic B")
    conn = db.connect_unchecked()
    try:
        tenancy.set_assistant(conn.for_tenant(a), "asst-A")
        tenancy.set_assistant(conn.for_tenant(b), "asst-B")
    finally:
        conn.close()
    seen = []

    def fake(method, url, json=None, timeout=None, headers=None):
        seen.append((method, url, json))
        return httpx.Response(200, json={"id": "x"}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "request", fake)
    assert "updated" in sync.sync_agent(a)
    assert [(m, u) for m, u, _ in seen] == [("PATCH", "https://api.vapi.ai/assistant/asst-A")]
    assert "Clinic A" in seen[0][2]["model"]["messages"][0]["content"]
    assert "Clinic B" not in str(seen[0][2])


def test_settings_save_reports_not_configured_without_vapi(isolated, monkeypatch):
    a, _, _ = make("clinic", "Clinic A")
    calls = []
    monkeypatch.setattr(httpx, "request", lambda *x, **k: calls.append(x))
    assert "isn't set up" in sync.sync_agent(a)
    assert sync.sync_tenant_agent(a) == "not_configured" and calls == []


def test_vapi_failure_on_settings_save_is_reported_not_raised(isolated, monkeypatch):
    configure(isolated)
    a, _, _ = make("clinic", "Clinic A")
    conn = db.connect_unchecked()
    try:
        tenancy.set_assistant(conn.for_tenant(a), "asst-A")
    finally:
        conn.close()
    monkeypatch.setattr(
        httpx,
        "request",
        lambda m, u, **k: httpx.Response(500, json={}, request=httpx.Request(m, u)),
    )
    assert "failed" in sync.sync_agent(a)

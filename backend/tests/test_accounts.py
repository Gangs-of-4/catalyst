"""M2: signup, login, sessions and the per-business assistant (Vapi mocked)."""

from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from src import accounts
from src.api import onboarding, sync
from src.core import config
from src.main import app

H = {"X-Requested-With": "catalyst"}
CLINIC = {
    "user": {"name": "Asha Rao", "email": "Owner@Example.com", "password": "correct horse"},
    "business": {
        "template": "clinic",
        "name": "Test Dental",
        "city": "Pune",
        "address": "12 Test Road",
        "hours": [["10:00", "14:00"]],
        "owner_whatsapp": "98765 00001",
        "consent": True,
    },
    "details": {
        "doctors": [{"name": "Dr. Test One"}],
        "services": [{"name": "Check", "fee": "₹100"}],
    },
}
WHOLESALE = {
    "user": {"name": "Ravi", "email": "ravi@example.com", "password": "another pass"},
    "business": {
        "template": "wholesale",
        "name": "Test Traders",
        "address": "Market Road",
        "hours": [["09:30", "19:30"]],
        "owner_whatsapp": "98765 00002",
        "consent": True,
    },
    "details": {"min_order": "₹2000", "delivery_area": "City"},
}


def copy(base: dict, **changes) -> dict:
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
    for path, value in changes.items():
        head, _, tail = path.partition(".")
        if tail:
            out[head][tail] = value
        else:
            out[head] = value
    return out


@pytest.fixture
def client(isolated):
    with TestClient(app) as c:
        yield c


def post(client, path, body, headers=H):
    return client.post(path, json=body, headers=headers)


def test_signup_creates_business_user_and_session(client, raw):
    r = post(client, "/api/signup", CLINIC)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["template"] == "clinic" and body["agent"] == "not_configured"
    assert body["public_id"] and body["public_id"] != "demo-clinic"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie
    me = client.get("/api/me").json()
    assert me["user"] == {"name": "Asha Rao", "email": "owner@example.com"}
    assert me["business"]["name"] == "Test Dental" and me["business"]["template"] == "clinic"
    t = raw.execute("SELECT * FROM tenants WHERE public_id = ?", (body["public_id"],)).fetchone()
    assert t["owner_whatsapp"] == "+919876500001" and t["tool_secret"] and not t["is_demo"]
    u = raw.execute("SELECT * FROM users").fetchone()
    assert u["email"] == "owner@example.com" and u["tenant_id"] == t["id"]
    assert "correct horse" not in u["password_hash"] and u["password_hash"].startswith("scrypt$")


def test_signup_settings_come_from_the_template_and_the_owner(client, raw):
    pid = post(client, "/api/signup", CLINIC).json()["public_id"]
    import json

    s = json.loads(
        raw.execute("SELECT settings FROM tenants WHERE public_id = ?", (pid,)).fetchone()[0]
    )
    assert s["doctors"] == [{"id": "dr-test-one", "name": "Dr. Test One"}]
    assert s["slot_min"] == 15 and s["sessions"] == [["10:00", "14:00"]]
    assert s["whatsapp_numbers"] == ["+919876500001"]
    assert (
        s["red_flags"] and "108" in s["emergency_instruction"]
    )  # template defaults, not demo data
    assert "Muskaan" not in json.dumps(s)


def test_wholesale_signup_uses_orders_section(client, raw):
    r = post(client, "/api/signup", WHOLESALE)
    assert r.status_code == 200, r.text
    assert (
        r.json()["agent"] == "not_configured"
    )  # no wholesale prompt until M4: honest, not a clinic prompt
    me = client.get("/api/me").json()
    assert me["business"]["labels"]["booking"] == "Order"
    t = raw.execute("SELECT settings FROM tenants WHERE template = 'wholesale'").fetchone()
    import json

    s = json.loads(t[0])
    assert s["min_order"] == "₹2000" and "doctors" not in s


def test_login_wrong_password_and_unknown_email_look_the_same(client):
    post(client, "/api/signup", CLINIC)
    client.cookies.clear()
    wrong = post(client, "/api/login", {"email": "owner@example.com", "password": "nope nope"})
    unknown = post(client, "/api/login", {"email": "nobody@example.com", "password": "nope nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() and wrong.json()["code"] == "UNAUTHENTICATED"
    assert client.get("/api/me").status_code == 401


def test_login_logout_roundtrip_is_case_insensitive(client):
    post(client, "/api/signup", CLINIC)
    client.cookies.clear()
    r = post(client, "/api/login", {"email": " OWNER@example.COM ", "password": "correct horse"})
    assert r.status_code == 200 and client.get("/api/me").status_code == 200
    assert post(client, "/api/logout", {}).status_code == 200
    assert client.get("/api/me").status_code == 401


def test_logout_kills_the_session_even_if_the_cookie_is_replayed(client):
    post(client, "/api/signup", CLINIC)
    stolen = client.cookies.get(accounts.COOKIE)
    post(client, "/api/logout", {})
    client.cookies.set(accounts.COOKIE, stolen)
    assert client.get("/api/me").status_code == 401


def test_duplicate_email_and_whatsapp(client):
    post(client, "/api/signup", CLINIC)
    client.cookies.clear()
    dup_email = post(client, "/api/signup", copy(WHOLESALE, user=CLINIC["user"]))
    assert dup_email.status_code == 409 and dup_email.json()["code"] == "EMAIL_TAKEN"
    biz = {**WHOLESALE["business"], "owner_whatsapp": CLINIC["business"]["owner_whatsapp"]}
    dup_wa = post(client, "/api/signup", copy(WHOLESALE, business=biz))
    assert dup_wa.status_code == 409 and dup_wa.json()["code"] == "WHATSAPP_TAKEN"
    assert client.get("/api/me").status_code == 401  # a refused signup logs nobody in


def test_failed_signup_leaves_no_half_made_business(client, raw):
    post(client, "/api/signup", CLINIC)
    client.cookies.clear()
    post(client, "/api/signup", copy(WHOLESALE, user=CLINIC["user"]))
    assert raw.execute("SELECT COUNT(*) FROM tenants WHERE is_demo = 0").fetchone()[0] == 1


def test_missing_fields_get_plain_422_with_field_names(client):
    bad = copy(CLINIC, user={"name": "A", "email": "not-an-email", "password": "short"})
    del bad["business"]["address"]
    bad["business"] = {**bad["business"], "consent": False}
    r = post(client, "/api/signup", bad)
    assert r.status_code == 422
    j = r.json()
    assert j["code"] == "VALIDATION"
    assert set(j["fields"]) >= {
        "user.name",
        "user.email",
        "user.password",
        "business.address",
        "business.consent",
    }
    assert j["fields"]["business.address"] == "Please fill in address."
    assert (
        "name@example.com" in j["fields"]["user.email"]
        and "8 characters" in j["fields"]["user.password"]
    )
    assert "Traceback" not in r.text and "pydantic" not in r.text.lower()


def test_template_section_errors_are_plain_too(client):
    r = post(client, "/api/signup", copy(CLINIC, details={"doctors": []}))
    assert r.status_code == 422
    assert "details.doctors" in r.json()["fields"]
    r = post(
        client, "/api/signup", copy(CLINIC, business={**CLINIC["business"], "template": "salon"})
    )
    assert r.status_code == 422 and "business.template" in r.json()["fields"]


def test_instructions_over_500_chars_refused(client):
    r = post(client, "/api/signup", copy(CLINIC, instructions="x" * 501))
    assert r.status_code == 422 and "500" in r.json()["detail"]


def test_writes_need_the_csrf_header(client):
    assert client.post("/api/signup", json=CLINIC).status_code == 403
    assert client.post("/api/login", json={"email": "a@b.co", "password": "x"}).status_code == 403
    r = client.post("/api/logout")
    assert r.status_code == 403 and r.json()["code"] == "FORBIDDEN"
    assert client.get("/api/templates").status_code == 200  # reads don't need it


def test_five_wrong_passwords_lock_the_account(client, monkeypatch):
    post(client, "/api/signup", CLINIC)
    client.cookies.clear()
    bad = {"email": "owner@example.com", "password": "wrong wrong"}
    for _ in range(4):
        assert post(client, "/api/login", bad).status_code == 401
    r = post(client, "/api/login", bad)
    assert r.status_code == 429 and r.json()["code"] == "LOCKED"
    # even the right password is refused while locked
    assert post(client, "/api/login", {**bad, "password": "correct horse"}).status_code == 429
    later = config.now() + timedelta(minutes=16)
    monkeypatch.setattr(config, "now", lambda: later)
    assert post(client, "/api/login", {**bad, "password": "correct horse"}).status_code == 200


def test_a_good_login_resets_the_failure_count(client):
    post(client, "/api/signup", CLINIC)
    client.cookies.clear()
    bad = {"email": "owner@example.com", "password": "wrong wrong"}
    for _ in range(4):
        post(client, "/api/login", bad)
    assert post(client, "/api/login", {**bad, "password": "correct horse"}).status_code == 200
    for _ in range(4):
        assert post(client, "/api/login", bad).status_code == 401


def test_expired_and_forged_cookies_are_refused(client, monkeypatch):
    post(client, "/api/signup", CLINIC)
    good = client.cookies.get(accounts.COOKIE)
    token, _, sig = good.partition(".")
    for forged in (token + ".deadbeef", "x." + sig, token, "", "garbage"):
        client.cookies.set(accounts.COOKIE, forged)
        assert client.get("/api/me").status_code == 401
    client.cookies.set(accounts.COOKIE, good)
    assert client.get("/api/me").status_code == 200
    later = config.now() + timedelta(days=31)
    monkeypatch.setattr(config, "now", lambda: later)
    assert client.get("/api/me").status_code == 401


def test_session_table_stores_only_a_hash(client, raw):
    post(client, "/api/signup", CLINIC)
    token = client.cookies.get(accounts.COOKIE).partition(".")[0]
    rows = raw.execute("SELECT token_hash FROM sessions").fetchall()
    assert len(rows) == 1 and token not in rows[0][0] and len(rows[0][0]) == 64


def test_cookie_is_secure_off_localhost(isolated):
    with TestClient(app, base_url="https://app.example.com") as c:
        r = post(c, "/api/signup", CLINIC)
        assert "secure" in r.headers["set-cookie"].lower()


def test_templates_endpoint_lists_both_with_defaults(client):
    j = client.get("/api/templates").json()["templates"]
    by = {t["template"]: t for t in j}
    assert {"clinic", "wholesale"} <= set(by)
    assert by["clinic"]["label"] == "Clinic" and by["clinic"]["defaults"]["slot_min"] == 15
    assert by["clinic"]["has_voice"] and not by["wholesale"]["has_voice"]
    assert by["wholesale"]["modules"] == ["orders"]


def test_template_without_a_prompt_gets_no_assistant(client, isolated, monkeypatch):
    """Wholesale has no agent-prompt.md until M4, so signup must not call Vapi for it."""
    isolated.write_text(
        "PUBLIC_URL=https://api.example.com\nVAPI_PRIVATE_KEY=k\n", encoding="utf-8"
    )
    calls = []
    monkeypatch.setattr(httpx, "request", lambda *a, **k: calls.append(a))
    r = post(client, "/api/signup", WHOLESALE)
    assert r.status_code == 200 and r.json()["agent"] == "not_configured" and calls == []


def test_assistant_created_for_this_business_only(client, isolated, raw, monkeypatch):
    """Vapi is mocked: the assistant gets this business's own webhook path, secret and id."""
    monkeypatch.setattr(sync, "PER_BUSINESS_WEBHOOK_READY", True)
    isolated.write_text(
        "PUBLIC_URL=https://api.example.com\nVAPI_PRIVATE_KEY=k\n", encoding="utf-8"
    )
    seen = []

    def fake(method, url, json=None, timeout=None, headers=None):
        seen.append((method, url, json))
        return httpx.Response(
            201, json={"id": f"asst-{len(seen)}"}, request=httpx.Request(method, url)
        )

    monkeypatch.setattr(httpx, "request", fake)
    r = post(client, "/api/signup", CLINIC)
    assert r.json()["agent"] == "updated"
    method, url, body = seen[0]
    assert (method, url) == ("POST", "https://api.vapi.ai/assistant") and len(seen) == 1
    pid = r.json()["public_id"]
    t = raw.execute("SELECT * FROM tenants WHERE public_id = ?", (pid,)).fetchone()
    assert t["vapi_assistant_id"] == "asst-1"
    assert body["server"] == {
        "url": f"https://api.example.com/vapi/webhook/{pid}",
        "headers": {"x-catalyst-secret": t["tool_secret"]},
    }
    assert body["maxDurationSeconds"] == 180
    assert "Test Dental" in body["model"]["messages"][0]["content"]
    assert "Muskaan" not in str(body)
    demo = raw.execute("SELECT vapi_assistant_id FROM tenants WHERE is_demo = 1").fetchone()
    assert demo[0] is None  # the demo clinic's assistant was not touched


def test_vapi_failure_does_not_fail_signup(client, isolated, monkeypatch):
    monkeypatch.setattr(sync, "PER_BUSINESS_WEBHOOK_READY", True)
    isolated.write_text(
        "PUBLIC_URL=https://api.example.com\nVAPI_PRIVATE_KEY=k\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        httpx,
        "request",
        lambda m, u, **k: httpx.Response(400, json={"message": "bad"}, request=httpx.Request(m, u)),
    )
    r = post(client, "/api/signup", CLINIC)
    assert r.status_code == 200 and r.json()["agent"] == "failed"
    assert client.get("/api/me").status_code == 200


def test_two_businesses_are_isolated_through_me(client, isolated):
    post(client, "/api/signup", CLINIC)
    a = client.cookies.get(accounts.COOKIE)
    client.cookies.clear()
    post(client, "/api/signup", WHOLESALE)
    assert client.get("/api/me").json()["business"]["name"] == "Test Traders"
    client.cookies.set(accounts.COOKIE, a)
    assert client.get("/api/me").json()["business"]["name"] == "Test Dental"


def test_password_hash_roundtrip():
    h = accounts.service.hash_password("s3cret-pass")
    assert accounts.service.verify_password("s3cret-pass", h)
    assert not accounts.service.verify_password("s3cret-pasx", h)
    assert not accounts.service.verify_password("x", "not-a-hash")
    assert accounts.service.hash_password("s3cret-pass") != h  # per-user salt


def test_unexpected_agent_error_does_not_fail_signup(client, isolated, monkeypatch):
    """Not only VapiError: any error while building the assistant leaves a usable account."""
    monkeypatch.setattr(sync, "PER_BUSINESS_WEBHOOK_READY", True)
    isolated.write_text(
        "PUBLIC_URL=https://api.example.com\nVAPI_PRIVATE_KEY=k\n", encoding="utf-8"
    )

    def boom(conn):
        raise KeyError("emergency_instruction")

    monkeypatch.setattr(sync.vapi, "sync_tenant", boom)
    r = post(client, "/api/signup", CLINIC)
    assert r.status_code == 200 and r.json()["agent"] == "failed"
    assert client.get("/api/me").status_code == 200


def test_signup_failing_after_the_business_is_made_can_be_retried(isolated, raw, monkeypatch):
    real = accounts.start_session

    def broken(*a, **k):
        raise RuntimeError("db went away")

    with TestClient(app, raise_server_exceptions=False) as client:
        monkeypatch.setattr(accounts, "start_session", broken)
        assert post(client, "/api/signup", CLINIC).status_code == 500
        assert raw.execute("SELECT COUNT(*) FROM tenants WHERE is_demo = 0").fetchone()[0] == 0
        assert raw.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        monkeypatch.setattr(accounts, "start_session", real)
        # the retry works, instead of being refused as EMAIL_TAKEN or WHATSAPP_TAKEN
        assert post(client, "/api/signup", CLINIC).status_code == 200


def test_each_module_validates_its_own_details():
    """A template with two modules checks both parts of `details`, and 422s rather than crashing."""
    t = {**onboarding.loader.template_defaults("clinic"), "modules": ["bookings", "orders"]}
    body = onboarding.SignupIn.model_validate(
        copy(CLINIC, details={**CLINIC["details"], "min_order": "x" * 61})
    )
    with pytest.raises(onboarding.ApiError) as e:
        onboarding.build_settings(t, body)
    assert e.value.status == 422 and "details.min_order" in e.value.fields
    ok = onboarding.SignupIn.model_validate(
        copy(CLINIC, details={**CLINIC["details"], "min_order": "₹500"})
    )
    s = onboarding.build_settings(t, ok)
    assert s["min_order"] == "₹500" and s["doctors"][0]["name"] == "Dr. Test One"

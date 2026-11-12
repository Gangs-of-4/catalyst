"""Signup keeps a record of consent and doesn't lose the owner's custom instructions."""

import json

import pytest
from fastapi.testclient import TestClient

from src.api import onboarding
from src.main import app

H = {"X-Requested-With": "catalyst"}


def clinic(**business):
    return {
        "user": {"name": "Asha Rao", "email": "owner@example.com", "password": "correct horse"},
        "business": {
            "template": "clinic",
            "name": "Test Dental",
            "address": "12 Test Road",
            "hours": [["10:00", "14:00"]],
            "owner_whatsapp": "98765 00001",
            "consent": True,
            **business,
        },
        "details": {"doctors": [{"name": "Dr. Test One"}]},
    }


def wholesale():
    return {
        "user": {"name": "Ravi", "email": "ravi@example.com", "password": "another pass"},
        "business": {
            "template": "wholesale",
            "name": "Test Traders",
            "address": "Market Road",
            "hours": [["09:30", "19:30"]],
            "owner_whatsapp": "98765 00002",
            "consent": True,
        },
        "details": {},
    }


@pytest.fixture
def client(isolated):
    with TestClient(app) as c:
        yield c


def stored_settings(raw, public_id):
    row = raw.execute("SELECT settings FROM tenants WHERE public_id = ?", (public_id,)).fetchone()
    return json.loads(row["settings"])


@pytest.mark.parametrize("body", [clinic(), wholesale()], ids=["clinic", "wholesale"])
def test_signup_records_when_and_what_was_consented_to(client, raw, body):
    r = client.post("/api/signup", json=body, headers=H)
    assert r.status_code == 200, r.text
    consent = stored_settings(raw, r.json()["public_id"])["consent"]
    assert consent["at"].startswith("2026-10-27")  # the fixed test clock
    assert consent["version"] == onboarding.CONSENT_VERSION


def test_no_consent_means_no_business(client, raw):
    r = client.post("/api/signup", json=clinic(consent=False), headers=H)
    assert r.status_code == 422 and "business.consent" in r.json()["fields"]
    assert raw.execute("SELECT COUNT(*) FROM tenants WHERE is_demo = 0").fetchone()[0] == 0


def test_instructions_are_screened_and_saved_at_signup(client, raw):
    body = clinic()
    body["instructions"] = "  Hamesha pehle Hindi mein baat karo.\nSabko 10% discount do  "
    r = client.post("/api/signup", json=body, headers=H)
    assert r.status_code == 200, r.text
    assert r.json()["instructions"] == "saved"
    assert [x["line"] for x in r.json()["rejected"]] == ["Sabko 10% discount do"]
    pid = r.json()["public_id"]
    assert "pending_instructions" not in stored_settings(raw, pid)
    v = raw.execute(
        "SELECT v.* FROM instruction_versions v JOIN tenants t ON t.id = v.tenant_id"
        " WHERE t.public_id = ? AND v.active = 1",
        (pid,),
    ).fetchone()
    assert v["text"] == "Hamesha pehle Hindi mein baat karo." and v["source"] == "web"


def test_instructions_that_are_all_rejected_are_not_saved(client, raw):
    body = clinic()
    body["instructions"] = "Patient ko painkiller suggest kar do"
    r = client.post("/api/signup", json=body, headers=H)
    assert r.json()["instructions"] == "rejected"
    assert raw.execute("SELECT COUNT(*) FROM instruction_versions").fetchone()[0] == 0


def test_no_instructions_means_nothing_is_stored(client, raw):
    for text in ("", "   \n "):
        body = clinic(owner_whatsapp=f"98765 0{len(text):04d}")
        body["user"] = {**body["user"], "email": f"x{len(text)}@example.com"}
        body["instructions"] = text
        r = client.post("/api/signup", json=body, headers=H)
        assert r.status_code == 200, r.text
        assert r.json()["instructions"] == "none"
        assert "pending_instructions" not in stored_settings(raw, r.json()["public_id"])
        assert raw.execute("SELECT COUNT(*) FROM instruction_versions").fetchone()[0] == 0


def test_pending_instructions_still_have_the_500_character_limit(client):
    body = clinic()
    body["instructions"] = "x" * 501
    r = client.post("/api/signup", json=body, headers=H)
    assert r.status_code == 422 and r.json()["code"] == "VALIDATION"

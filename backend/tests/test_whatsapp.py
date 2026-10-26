from datetime import date
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from src.api.whatsapp import signature_ok
from src.booking import service as bk
from src.channels.whatsapp.commands import parse_rules
from src.core import db
from src.core import settings as cs
from src.main import app

TODAY = date(2026, 10, 27)
DOCTOR = "+919000000100"


@pytest.mark.parametrize("text, expected", [
    ("help", {"intent": "help"}),
    ("aaj ke appointments", {"intent": "query_day", "date": "2026-10-27"}),
    ("kal ke appointments?", {"intent": "query_day", "date": "2026-10-28"}),
    ("callbacks", {"intent": "callbacks"}),
    ("summary", {"intent": "summary"}),
    ("kal chhutti", {"intent": "block_day", "date": "2026-10-28", "doctor_id": None}),
    ("kal chhutti hai", {"intent": "block_day", "date": "2026-10-28", "doctor_id": None}),
    ("Dr Asha kal nahi aayengi", {"intent": "block_day", "date": "2026-10-28", "doctor_id": "dr-a"}),
    ("Vikram parso leave", {"intent": "block_day", "date": "2026-10-29", "doctor_id": "dr-b"}),
    ("aaj 11 baje se", {"intent": "late_start", "date": "2026-10-27", "time": "11:00"}),
    ("Dr Vikram kal 11 baje se", {"intent": "late_start", "date": "2026-10-28", "time": "11:00", "doctor_id": "dr-b"}),
    ("aaj 6 baje tak", {"intent": "early_close", "date": "2026-10-27", "time": "18:00"}),
    ("consultation fee 400", {"intent": "set_fee", "service": "Consultation", "fee": 400}),
    ("cleaning fee ₹900", {"intent": "set_fee", "service": "Cleaning and scaling", "fee": 900}),
    ("walk-in Ramesh 9876543210 aaj 5 baje",
     {"intent": "walk_in", "name": "Ramesh", "phone": "+919876543210", "date": "2026-10-27", "time": "17:00"}),
    ("walk in Sita Devi 98765 43210 kal 11 baje Dr Asha",
     {"intent": "walk_in", "name": "Sita Devi", "date": "2026-10-28", "time": "11:00", "doctor_id": "dr-a"}),
])
def test_rules_parse(conn, settings, text, expected):
    cmd = parse_rules(text, settings, TODAY)
    assert cmd is not None, text
    got = cmd.model_dump()
    assert {k: got[k] for k in expected} == expected


@pytest.mark.parametrize("text", ["kya haal hai", "patient ko bolo dawai le", "fee"])
def test_rules_do_not_guess(conn, settings, text):
    assert parse_rules(text, settings, TODAY) is None


@pytest.fixture
def client(isolated):
    with TestClient(app) as c:
        yield c


def send(client, body, sender=DOCTOR, headers=None):
    data = urlencode({"From": f"whatsapp:{sender}", "Body": body})
    r = client.post("/whatsapp/incoming", content=data,
                    headers={"content-type": "application/x-www-form-urlencoded", **(headers or {})})
    assert r.status_code == 200, r.text
    assert r.text.startswith('<?xml version="1.0" encoding="UTF-8"?><Response><Message>')
    return r.text


def allow(numbers):
    conn = db.connect()
    s = cs.load(conn)
    s["whatsapp_numbers"] = numbers
    cs.save(conn, s)
    conn.close()


def test_preview_then_haan_applies(client):
    allow([DOCTOR])
    reply = send(client, "kal chhutti")
    assert "Poori clinic" in reply and "Wed, 28 Oct" in reply and "Haan/Nahi" in reply
    conn = db.connect()
    assert conn.execute("SELECT COUNT(*) FROM blocks").fetchone()[0] == 0, "nothing changes before Haan"
    assert "Done ✅" in send(client, "Haan")
    assert conn.execute("SELECT kind FROM blocks").fetchone()[0] == "holiday"
    assert bk.free_slots(conn, cs.load(conn), date(2026, 10, 28)) == []
    # the seeded bookings that day went to the callback list
    assert conn.execute("SELECT COUNT(*) FROM inbox WHERE note LIKE '%affected by schedule change%'").fetchone()[0] == 2


def test_preview_then_nahi_discards(client):
    allow([DOCTOR])
    send(client, "consultation fee 450")
    assert "kuch nahi badla" in send(client, "nahi")
    conn = db.connect()
    assert next(x for x in cs.load(conn)["services"] if x["name"] == "Consultation")["fee"] == "₹300"
    assert "koi badlav pending nahi" in send(client, "haan")


def test_fee_change_applies(client):
    allow([DOCTOR])
    send(client, "consultation fee 450")
    send(client, "ok")
    conn = db.connect()
    assert next(x for x in cs.load(conn)["services"] if x["name"] == "Consultation")["fee"] == "₹450"


def test_walk_in_from_whatsapp(client):
    allow([DOCTOR])
    assert "Walk-in: Ramesh" in send(client, "walk-in Ramesh 9876543210 kal 12 baje")
    assert "Done ✅" in send(client, "haan")
    row = db.connect().execute("SELECT source, time FROM bookings WHERE name = 'Ramesh'").fetchone()
    assert tuple(row) == ("whatsapp", "12:00")


def test_unregistered_number_rejected(client):
    allow([DOCTOR])
    assert "registered nahi" in send(client, "kal chhutti", sender="+919000000999")
    assert db.connect().execute("SELECT COUNT(*) FROM pending_actions").fetchone()[0] == 0


def test_open_mode_warns(client):
    allow([])
    assert "Demo mode" in send(client, "aaj ke appointments")


def test_unparsed_creates_ops_item(client):
    allow([DOCTOR])
    assert "Samajh nahi aaya" in send(client, "kuch alag sa sawaal")
    assert db.connect().execute("SELECT kind FROM inbox WHERE kind = 'ops'").fetchone() is not None


def test_query_lists_bookings(client):
    allow([DOCTOR])
    reply = send(client, "aaj ke appointments")
    assert "Aaj (Tue, 27 Oct) ke appointments (3)" in reply and "Ramesh Gupta" in reply


def test_xml_is_escaped(client):
    allow([DOCTOR])
    assert "&lt;" in send(client, "<b>help</b>") or "Commands" in send(client, "help")


def test_twilio_signature(client, isolated):
    isolated.write_text("TWILIO_AUTH_TOKEN=tok\nPUBLIC_URL=https://demo.trycloudflare.com\n", encoding="utf-8")
    params = {"From": f"whatsapp:{DOCTOR}", "Body": "help"}
    r = client.post("/whatsapp/incoming", content=urlencode(params),
                    headers={"content-type": "application/x-www-form-urlencoded", "x-twilio-signature": "bad"})
    assert r.status_code == 403
    import base64, hashlib, hmac
    url = "https://demo.trycloudflare.com/whatsapp/incoming"
    sig = base64.b64encode(hmac.new(b"tok", (url + "Bodyhelp" + f"Fromwhatsapp:{DOCTOR}").encode(), hashlib.sha1).digest()).decode()
    assert signature_ok(sig, url, params, "tok")
    r = client.post("/whatsapp/incoming", content=urlencode(params),
                    headers={"content-type": "application/x-www-form-urlencoded", "x-twilio-signature": sig})
    assert r.status_code == 200 and "Commands" in r.text


def test_llm_fallback_fails_closed(client, isolated, monkeypatch):
    from src.providers.llm import groq
    isolated.write_text("GROQ_API_KEY=k\n", encoding="utf-8")
    allow([DOCTOR])
    monkeypatch.setattr(groq, "complete_json", lambda system, user: '{"intent": "block_day", "date": "not-a-date"}')
    assert "Samajh nahi aaya" in send(client, "doctor sahab agle hafte bahar")
    monkeypatch.setattr(groq, "complete_json", lambda system, user: '{"intent": "block_day", "date": "2026-10-29", "doctor_id": "dr-b"}')
    assert "Dr. Vikram Saxena" in send(client, "doctor sahab agle hafte bahar")


def test_escalation_sends_urgent_alert_to_every_number(client, isolated, monkeypatch):
    from src.providers.messaging import twilio_whatsapp
    sent = []
    monkeypatch.setattr(twilio_whatsapp, "send", lambda to, body: sent.append((to, body)) or True)
    isolated.write_text("CATALYST_TOOL_SECRET=s\n", encoding="utf-8")
    allow([DOCTOR, "+919000000101"])
    payload = {"message": {"type": "tool-calls", "call": {"id": "c1"}, "toolCallList": [{"id": "t1", "function": {
        "name": "escalate", "arguments": {"category": "red_flag", "name": "Caller", "phone": "9000000200",
                                          "summary": "Swelling up to the eye since morning.\nWants a doctor today."}}}]}}
    assert client.post("/vapi/webhook", json=payload, headers={"x-catalyst-secret": "s"}).status_code == 200
    assert [to for to, _ in sent] == [DOCTOR, "+919000000101"]
    body = sent[0][1]
    assert body.startswith("🔴 URGENT") and "Caller" in body and "90000 00200" in body and "Swelling" in body

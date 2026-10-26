import json

import pytest
from fastapi.testclient import TestClient

from src.core import db
from src.main import app

SECRET = "test-secret"


@pytest.fixture
def client(isolated):
    isolated.write_text(f"CATALYST_TOOL_SECRET={SECRET}\n", encoding="utf-8")
    with TestClient(app) as c:
        # start from an empty schedule so results are predictable
        conn = db.connect()
        with conn:
            conn.execute("DELETE FROM bookings")
            conn.execute("DELETE FROM inbox")
        conn.close()
        yield c


def tool_calls(name, args, call_id="call-1", tc_id="tc-1", legacy=False, customer=None):
    call = {"id": call_id, "type": "webCall"}
    if customer:
        call["customer"] = {"number": customer}
    item = {"id": tc_id, "type": "function", "function": {"name": name, "arguments": args}}
    msg = {"type": "tool-calls", "call": call}
    if legacy:
        msg["toolWithToolCallList"] = [{"type": "function", "function": {"name": name}, "toolCall": item}]
    else:
        msg["toolCallList"] = [item]
    return {"message": msg}


def post(client, payload, secret=SECRET):
    headers = {"x-catalyst-secret": secret} if secret else {}
    return client.post("/vapi/webhook", json=payload, headers=headers)


def result(resp):
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"results"}
    (r,) = body["results"]
    assert set(r) == {"name", "toolCallId", "result"}
    return r


def test_missing_or_wrong_secret_is_401(client):
    assert post(client, tool_calls("find_slots", {"date": "kal"}), secret=None).status_code == 401
    assert post(client, tool_calls("find_slots", {"date": "kal"}), secret="nope").status_code == 401


def test_unset_secret_rejects_everything(client, isolated):
    isolated.write_text("", encoding="utf-8")
    assert post(client, tool_calls("find_slots", {"date": "kal"}), secret="anything").status_code == 401


def test_find_slots_current_shape(client):
    r = result(post(client, tool_calls("find_slots", {"date": "kal", "time": "shaam 5 baje"})))
    assert r["name"] == "find_slots" and r["toolCallId"] == "tc-1"
    assert "Wednesday, 28 October 2026" in r["result"]
    assert "5 PM with Dr. Asha Verma" in r["result"]


def test_legacy_shape_and_string_arguments(client):
    args = json.dumps({"question": "Sunday ko clinic khula hai?"})
    r = result(post(client, tool_calls("get_clinic_info", args, legacy=True)))
    assert r["name"] == "get_clinic_info"
    assert "Closed on Sunday" in r["result"]


def test_unknown_question_says_not_found(client):
    r = result(post(client, tool_calls("get_clinic_info", {"question": "Do you sell insurance?"})))
    assert r["result"].startswith("NOT FOUND")


def test_book_then_double_book_then_cancel(client):
    args = {"name": "Caller One", "phone": "98765 43210", "date": "kal", "time": "5 baje", "doctor": "Dr Asha"}
    r = result(post(client, tool_calls("book", args, tc_id="b1")))
    assert r["result"].startswith("BOOKED") and "Wednesday, 28 October 2026, 5 PM" in r["result"]
    r2 = result(post(client, tool_calls("book", {**args, "name": "Caller Two"}, call_id="call-2", tc_id="b2")))
    assert r2["result"].startswith("NOT BOOKED") and "alternatives" in r2["result"]
    found = result(post(client, tool_calls("find_booking", {"phone": "9876543210"}, tc_id="f1")))
    assert "booking 1" in found["result"]
    c = result(post(client, tool_calls("cancel", {"phone": "+91 98765 43210"}, tc_id="c1")))
    assert c["result"].startswith("CANCELLED")


def test_retried_tool_call_is_idempotent(client):
    args = {"name": "A", "phone": "9876543210", "date": "kal", "time": "11", "doctor": "Vikram"}
    first = result(post(client, tool_calls("book", args, tc_id="same")))
    again = result(post(client, tool_calls("book", args, tc_id="same")))
    assert first["result"] == again["result"] and first["result"].startswith("BOOKED")


def test_caller_id_is_default_phone(client):
    args = {"name": "A", "date": "kal", "time": "11", "doctor": "dr-b"}
    r = result(post(client, tool_calls("book", args, customer="+919876500000")))
    assert "phone ending 0000" in r["result"]


def test_reschedule(client):
    post(client, tool_calls("book", {"name": "A", "phone": "9876543210", "date": "kal", "time": "11",
                                     "doctor": "Asha"}, tc_id="b"))
    r = result(post(client, tool_calls("reschedule", {"phone": "9876543210", "new_date": "parso",
                                                      "new_time": "saade 5"}, tc_id="r")))
    assert r["result"].startswith("MOVED") and "Thursday, 29 October 2026, 5:30 PM with Dr. Asha Verma" in r["result"]


def test_escalate_creates_urgent_inbox_item(client):
    r = result(post(client, tool_calls("escalate", {"category": "red_flag", "summary": "Swelling up to the eye",
                                                    "name": "A", "phone": "9876543210"})))
    assert r["result"].startswith("ESCALATED") and "108" in r["result"]
    conn = db.connect()
    row = conn.execute("SELECT kind, urgent FROM inbox").fetchone()
    assert tuple(row) == ("escalation", 1)
    assert conn.execute("SELECT escalated FROM calls WHERE id = 'call-1'").fetchone()[0] == 1


def test_end_of_call_report_sets_outcome(client):
    post(client, tool_calls("book", {"name": "A", "phone": "9876543210", "date": "kal", "time": "11",
                                     "doctor": "Asha"}, call_id="call-9"))
    report = {"message": {
        "type": "end-of-call-report",
        "call": {"id": "call-9", "type": "webCall"},
        "artifact": {"transcript": "AI: Namaste\nUser: kal 11 baje\nAI: Booked.", "recordingUrl": "https://x/rec.wav"},
        "analysis": {"summary": "Caller booked for tomorrow 11 AM."},
        "startedAt": "2026-10-27T09:00:00Z", "endedAt": "2026-10-27T09:02:00Z",
    }}
    assert post(client, report).status_code == 200
    row = db.connect().execute("SELECT outcome, summary, safety_review FROM calls WHERE id = 'call-9'").fetchone()
    assert tuple(row) == ("booked", "Caller booked for tomorrow 11 AM.", 0)


def test_end_of_call_without_tools_is_answered_or_hung_up(client):
    def report(cid, transcript):
        return {"message": {"type": "end-of-call-report", "call": {"id": cid}, "artifact": {"transcript": transcript}}}
    post(client, report("c-a", "AI: Namaste\nUser: timing kya hai?\nAI: 10 se 2."))
    post(client, report("c-h", "AI: Namaste"))
    conn = db.connect()
    assert conn.execute("SELECT outcome FROM calls WHERE id = 'c-a'").fetchone()[0] == "answered"
    assert conn.execute("SELECT outcome FROM calls WHERE id = 'c-h'").fetchone()[0] == "hung_up"


def test_end_of_call_flags_unsafe_assistant_line(client):
    msg = {"message": {"type": "end-of-call-report", "call": {"id": "c-s"}, "artifact": {
        "messages": [{"role": "assistant", "message": "Aap ek painkiller le lijiye."},
                     {"role": "user", "message": "theek hai"}]}}}
    post(client, msg)
    row = db.connect().execute("SELECT safety_review, safety_hits FROM calls WHERE id = 'c-s'").fetchone()
    assert row[0] == 1 and "painkiller" in row[1]


def test_other_message_types_are_ok(client):
    assert post(client, {"message": {"type": "status-update", "status": "in-progress"}}).json() == {"ok": True}

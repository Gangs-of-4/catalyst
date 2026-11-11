"""Phase 2 M4b: the wholesale agent's tools, prompt and post-call safety check."""

import re

import pytest
from conftest import APP_HEADERS
from fastapi.testclient import TestClient

from src.agents import prompt
from src.core import db, tenancy
from src.core import settings as cs
from src.main import app
from src.providers.voice_orchestrator import vapi
from src.safety import post_call
from src.verticals import loader

PRODUCTS = (
    ("Paracetamol 500 mg tablets", "Strip of 10", "18", True),
    ("Paracetamol 650 mg tablets", "Strip of 15", "30.50", True),
    ("Hand sanitiser", "500 ml bottle", "120", False),
    ("Surgical gloves", "Box of 100", "450", True),
)


@pytest.fixture
def shop(isolated):
    """(client, public_id, secret, tenant id) for a wholesaler with a catalogue."""
    with TestClient(app, headers=APP_HEADERS) as c:
        body = {
            "user": {"name": "Owner", "email": "w@example.com", "password": "another pass"},
            "business": {
                "template": "wholesale",
                "name": "Test Traders",
                "address": "Market Road",
                "hours": [["09:30", "19:30"]],
                "owner_whatsapp": "90000 00031",
                "consent": True,
            },
            "details": {"min_order": "₹2,000", "delivery_area": "Within 10 km"},
        }
        pid = c.post("/api/signup", json=body).json()["public_id"]
        for name, pack, rate, stock in PRODUCTS:
            c.post(
                "/api/catalog",
                json={"name": name, "pack_size": pack, "rate": rate, "in_stock": stock},
            )
        conn = db.connect_unchecked()
        try:
            t = tenancy.by_public_id(conn, pid)
        finally:
            conn.close()
        yield c, pid, t["tool_secret"], t["id"]


def tool(shop, name, args, tc_id=None, call_id="call-1"):
    c, pid, secret, _ = shop
    tool.n = getattr(tool, "n", 0) + 1
    body = {
        "message": {
            "type": "tool-calls",
            "call": {"id": call_id, "type": "webCall"},
            "toolCallList": [
                {
                    "id": tc_id or f"tc-{tool.n}",
                    "type": "function",
                    "function": {"name": name, "arguments": args},
                }
            ],
        }
    }
    r = c.post(f"/vapi/webhook/{pid}", json=body, headers={"x-catalyst-secret": secret})
    assert r.status_code == 200, r.text
    return r.json()["results"][0]["result"]


def rows(shop, sql):
    conn = db.connect().for_tenant(shop[3])
    try:
        return conn.execute(sql, (shop[3],)).fetchall()
    finally:
        conn.close()


CATALOGUE_RATES = {"₹18", "₹30.50", "₹120", "₹450"}


def rupees(text):
    return set(re.findall(r"₹\d+(?:,\d+)*(?:\.\d\d)?", text))


# Rates and stock come only from the catalogue


def test_catalogue_lists_names_rates_and_stock(shop):
    text = tool(shop, "get_catalog", {})
    for name, *_ in PRODUCTS:
        assert name in text
    assert "Hand sanitiser, 500 ml bottle, ₹120, OUT OF STOCK" in text
    assert rupees(text) <= CATALOGUE_RATES


def test_catalogue_search_and_no_guessing(shop):
    text = tool(shop, "get_catalog", {"query": "gloves"})
    assert "Surgical gloves" in text and "Paracetamol" not in text
    text = tool(shop, "get_catalog", {"query": "cough syrup"})
    assert "Nothing in the catalogue" in text and "Never suggest a different product" in text
    assert rupees(text) == set()


def test_check_stock_one_product_or_ask_which(shop):
    assert tool(shop, "check_stock", {"product": "surgical gloves"}) == (
        "Surgical gloves, Box of 100, ₹450, in stock."
    )
    text = tool(shop, "check_stock", {"product": "paracetamol"})
    assert text.startswith("UNKNOWN_PRODUCT") and "Ask the caller which one" in text
    assert "500 mg" in text and "650 mg" in text
    text = tool(shop, "check_stock", {"product": "cough syrup"})
    assert text.startswith("UNKNOWN_PRODUCT") and "Never suggest a different product" in text
    text = tool(shop, "check_stock", {"product": "hand sanitiser"})
    assert "out of stock" in text and "Never suggest a different product" in text


# Orders by phone


def test_create_order_saves_at_catalogue_rates(shop):
    text = tool(
        shop,
        "create_order",
        {
            "shop_name": "Test Medical",
            "contact_name": "Caller One",
            "phone": "9000000041",
            "items": [
                {"product": "paracetamol 500", "qty": 10},
                {"product": "Surgical gloves", "qty": "2"},
            ],
            "notes": "Deliver before 5",
        },
    )
    assert text.startswith("ORDER SAVED, order number 1:")
    assert "Paracetamol 500 mg tablets (Strip of 10) × 10 × ₹18 = ₹180" in text
    assert "Surgical gloves (Box of 100) × 2 × ₹450 = ₹900" in text and "Total ₹1,080" in text
    assert rupees(text) <= CATALOGUE_RATES | {"₹180", "₹900", "₹1,080"}
    (o,) = rows(shop, "SELECT * FROM orders WHERE tenant_id = ?")
    assert (o["source"], o["call_id"], o["phone"]) == ("phone", "call-1", "+919000000041")
    (call,) = rows(shop, "SELECT * FROM calls WHERE tenant_id = ?")
    assert call["booked"] == 1  # an order counts as a booking-style outcome


def test_create_order_retry_with_the_same_tool_call_saves_once(shop):
    args = {
        "shop_name": "Test Medical",
        "phone": "9000000041",
        "items": [{"product": "gloves", "qty": 1}],
    }
    first = tool(shop, "create_order", args, tc_id="tc-same")
    again = tool(shop, "create_order", args, tc_id="tc-same")
    assert first == again and len(rows(shop, "SELECT id FROM orders WHERE tenant_id = ?")) == 1


@pytest.mark.parametrize(
    "items, expected",
    [
        ([{"product": "paracetamol", "qty": 1}], "Ask which product"),
        ([{"product": "cough syrup", "qty": 1}], "isn't in the catalogue"),
        ([{"product": "hand sanitiser", "qty": 1}], "out of stock"),
        ([{"product": "gloves", "qty": 0}], "whole number from 1 to 9999"),
        ([{"product": "gloves", "qty": "das"}], "whole number from 1 to 9999"),
        ([], "Add at least one item"),
    ],
)
def test_create_order_refusals_save_nothing(shop, items, expected):
    text = tool(
        shop, "create_order", {"shop_name": "Test Medical", "phone": "9000000041", "items": items}
    )
    assert text.startswith("NOT SAVED") and expected in text
    assert rows(shop, "SELECT id FROM orders WHERE tenant_id = ?") == []


def test_create_order_needs_a_phone_number(shop):
    text = tool(
        shop,
        "create_order",
        {"shop_name": "Test Medical", "items": [{"product": "gloves", "qty": 1}]},
    )
    assert text.startswith("NOT SAVED") and "10-digit" in text


def test_duplicate_order_points_to_the_earlier_one(shop):
    args = {
        "shop_name": "Test Medical",
        "phone": "9000000041",
        "items": [{"product": "gloves", "qty": 1}],
    }
    tool(shop, "create_order", args)
    text = tool(shop, "create_order", args)
    assert text.startswith("NOT SAVED") and "already placed order 1 today" in text


def test_order_status_by_number_and_phone(shop):
    args = {
        "shop_name": "Test Medical",
        "phone": "9000000041",
        "items": [{"product": "gloves", "qty": 3}],
    }
    tool(shop, "create_order", args)
    shop[0].post("/api/orders/1/status", json={"status": "confirmed"})
    text = tool(shop, "order_status", {"order_number": 1})
    assert "order 1 placed" in text and "confirmed, being packed" in text and "₹1,350" in text
    assert "order 1" in tool(shop, "order_status", {"phone": "90000 00041"})
    assert tool(shop, "order_status", {"order_number": 99}).startswith("NOT_FOUND")


# Facts, escalation, tool list


def test_business_info_answers_minimum_order_and_delivery(shop):
    text = tool(
        shop, "get_business_info", {"question": "minimum order kitna hai, delivery kahan tak?"}
    )
    assert "Minimum order: ₹2,000" in text and "Delivery area: Within 10 km" in text
    assert text.startswith("Distributor-approved answer")
    text = tool(shop, "get_business_info", {"question": "GST number batao"})
    assert text.startswith("NOT FOUND in the distributor-approved answers")


def test_escalate_works_without_clinic_settings(shop):
    text = tool(shop, "escalate", {"category": "caller_request", "summary": "Wants the owner now"})
    assert text.startswith("ESCALATED: the owner has been alerted") and "TOOL ERROR" not in text
    text = tool(shop, "escalate", {"category": "grey_zone", "summary": "Someone is unwell"})
    assert "emergency instruction" not in text and "TOOL ERROR" not in text


def test_clinic_tools_are_refused_for_a_wholesaler(shop):
    assert tool(shop, "find_slots", {"date": "kal"}).startswith("Unknown tool find_slots")


def test_every_wholesale_tool_has_a_schema():
    assert {fn["name"] for fn in vapi.template_tools("wholesale")} == loader.tool_names("wholesale")


# Prompt


def test_wholesale_prompt_has_the_rules_and_only_approved_facts(shop):
    conn = db.connect().for_tenant(shop[3])
    try:
        system, first = prompt.build(conn, cs.load(conn))
    finally:
        conn.close()
    assert "Test Traders" in system and "Test Traders" in first
    assert "Never state a rate" in system and "Never offer a different product" in system
    assert "Read the whole order back before saving" in system
    assert "Minimum order: ₹2,000" in system and "Delivery area: Within 10 km" in system
    assert not rupees(system) & CATALOGUE_RATES  # rates change: the agent reads them from tools
    assert "₹" not in system.split("## Business facts")[0]  # no example rate it could repeat
    assert not re.search(r"\{(tenant_name|business_snapshot|voice_forms)\}", system + first)


# Post-call safety check


CATALOGUE = [x for name, pack, *_ in PRODUCTS for x in (name, pack)]


@pytest.mark.parametrize(
    "line",
    [
        "Paracetamol 500 mg tablets, Strip of 10, ₹18 का है।",
        "तो 10 strip Paracetamol 650 mg tablets — सही है?",
        "मैं दवाई के बारे में सलाह नहीं दे सकती, यह doctor या pharmacist ही बता पाएँगे।",
        "Hand sanitiser abhi stock mein nahi hai, baaki order le loon?",
    ],
)
def test_selling_the_catalogue_is_not_a_flag(line):
    assert post_call.scan([line], CATALOGUE, selling=True) == []


@pytest.mark.parametrize(
    "line",
    [
        "Bachche ko din mein do baar ek goli de dijiye, 5 ml syrup bhi.",
        "Iski jagah Paracetamol 650 mg tablets de sakte hain, same hi hai.",
        "Dolo bhi chalegi, ghabraane ki koi baat nahi.",
        "Ye tablet khaane ke baad le lijiye.",
    ],
)
def test_advice_and_substitutes_are_flagged_when_selling(line):
    assert post_call.scan([line], CATALOGUE, selling=True)


def test_clinic_mode_is_unchanged():
    assert post_call.scan(
        ["Paracetamol 500 mg tablets, Strip of 10, ₹18"]
    )  # a clinic never says it
    assert post_call.scan(["Doctor A ki jagah Doctor B se appointment mil jayega"]) == []


def test_end_of_call_review_uses_the_catalogue(shop):
    c, pid, secret, _ = shop

    def report(call_id, said):
        message = {
            "type": "end-of-call-report",
            "call": {"id": call_id},
            "artifact": {
                "messages": [{"role": "user", "message": "Order"}]
                + [{"role": "assistant", "message": m} for m in said]
            },
        }
        c.post(
            f"/vapi/webhook/{pid}", json={"message": message}, headers={"x-catalyst-secret": secret}
        )

    report("call-ok", ["Paracetamol 500 mg tablets, Strip of 10, ₹18 का है।"])
    report("call-bad", ["Iski jagah Paracetamol 650 mg tablets de do, same hi hai."])
    review = {
        r["id"]: r["safety_review"] for r in rows(shop, "SELECT * FROM calls WHERE tenant_id = ?")
    }
    assert review == {"call-ok": 0, "call-bad": 1}

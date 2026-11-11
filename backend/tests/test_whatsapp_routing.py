"""Phase 2 M6: one WhatsApp number for every business, routed by sender; wholesale commands."""

from urllib.parse import urlencode

import pytest
from conftest import APP_HEADERS
from fastapi.testclient import TestClient

from src.core import db, tenancy
from src.core import settings as cs
from src.main import app

CLINIC_OWNER = "+919000000201"
SHOP_OWNER = "+919000000202"
SECOND_DOCTOR = "+919000000203"


def signup(c, template, n, owner):
    body = {
        "user": {"name": "Owner", "email": f"r{n}@example.com", "password": "another pass"},
        "business": {
            "template": template,
            "name": f"Business {n}",
            "address": "1 Test Road",
            "hours": [["09:00", "19:00"]],
            "owner_whatsapp": owner[3:],
            "consent": True,
        },
        "details": {"doctors": [{"name": "Dr. Test"}]} if template == "clinic" else {},
    }
    r = c.post("/api/signup", json=body)
    assert r.status_code == 200, r.text
    return r.json()["public_id"]


@pytest.fixture
def two(isolated):
    """A clinic and a wholesaler, each with its owner's number; the wholesaler has a catalogue
    and one order. Yields the clinic's client, the shop's client and a client for WhatsApp."""
    with (
        TestClient(app, headers=APP_HEADERS) as clinic,
        TestClient(app, headers=APP_HEADERS) as shop,
        TestClient(app) as wa,
    ):
        signup(clinic, "clinic", 1, CLINIC_OWNER)
        signup(shop, "wholesale", 2, SHOP_OWNER)
        for name, pack, rate, stock in (
            ("Paracetamol 500 mg tablets", "Strip of 10", "18", True),
            ("Paracetamol 650 mg tablets", "Strip of 15", "30", True),
            ("Surgical gloves", "Box of 100", "450", False),
        ):
            shop.post(
                "/api/catalog",
                json={"name": name, "pack_size": pack, "rate": rate, "in_stock": stock},
            )
        pid = catalogue(shop)["Paracetamol 500 mg tablets"]["id"]
        shop.post(
            "/api/orders",
            json={"shop_name": "Test Medical", "items": [{"product_id": pid, "qty": 4}]},
        )
        yield clinic, shop, wa


def send(wa, body, sender):
    r = wa.post(
        "/whatsapp/incoming",
        content=urlencode({"From": f"whatsapp:{sender}", "Body": body}),
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200, r.text
    return r.text


def catalogue(shop):
    found = shop.get("/api/catalog", params={"all": "true"}).json()["products"]
    return {p["name"]: p for p in found}


def add_number(client, number):
    conn = db.connect()
    try:
        me = client.get("/api/me").json()["business"]["public_id"]
        scoped = conn.for_tenant(tenancy.by_public_id(conn, me)["id"])
        s = cs.load(scoped)
        s["whatsapp_numbers"] = [*s["whatsapp_numbers"], number]
        cs.save(scoped, s)
    finally:
        conn.close()


# Routing


def test_each_owner_reaches_their_own_business(two):
    _, _, wa = two
    assert "Dr. Test" in send(wa, "aaj ke appointments", CLINIC_OWNER)
    reply = send(wa, "aaj ke orders", SHOP_OWNER)
    assert "Test Medical" in reply and "₹72" in reply
    assert "Test Medical" not in send(wa, "callbacks", CLINIC_OWNER)


def test_unknown_number_changes_nothing_and_points_to_signup(two, isolated):
    _, shop, wa = two
    isolated.write_text("PUBLIC_APP_URL=https://app.example.com/\n", encoding="utf-8")
    reply = send(wa, "rate Surgical gloves 1", "+919000000299")
    assert "juda nahi hai" in reply and "https://app.example.com/signup" in reply
    assert catalogue(shop)["Surgical gloves"]["rate"] == "₹450"


def test_a_listed_second_number_reaches_that_business(two):
    clinic, _, wa = two
    add_number(clinic, SECOND_DOCTOR)
    assert "Dr. Test" in send(wa, "aaj ke appointments", SECOND_DOCTOR)


def test_one_business_cannot_claim_anothers_number(two):
    """Numbers are unique across businesses: the shop can't lock the clinic's doctor out."""
    clinic, shop, wa = two
    add_number(clinic, SECOND_DOCTOR)
    s = shop.get("/api/settings").json()["settings"]
    body = {k: s[k] for k in ("name", "address", "sessions")}
    for taken in ("90000 00203", CLINIC_OWNER):  # a listed number, and an owner's number
        r = shop.put("/api/settings", json={**body, "whatsapp_numbers": [SHOP_OWNER, taken]})
        assert r.status_code == 409 and r.json()["code"] == "WHATSAPP_TAKEN"
    assert shop.get("/api/settings").json()["settings"]["whatsapp_numbers"] == [SHOP_OWNER]
    assert "Dr. Test" in send(wa, "aaj ke appointments", SECOND_DOCTOR)


def test_a_listed_number_need_not_be_stored_normalised(two):
    """Settings saved before (or outside) /setup may hold "90000 00203"; it still matches."""
    clinic, _, wa = two
    add_number(clinic, "90000 00203")
    assert "Dr. Test" in send(wa, "aaj ke appointments", SECOND_DOCTOR)


def test_old_databases_are_indexed_at_startup(two, raw):
    clinic, _, wa = two
    add_number(clinic, SECOND_DOCTOR)
    with raw:
        raw.execute("DELETE FROM tenant_whatsapp_numbers")  # as before the index existed
    assert "juda nahi hai" in send(wa, "help", SECOND_DOCTOR)
    with TestClient(app) as restarted:  # startup rebuilds the index from settings
        assert "Dr. Test" in send(restarted, "aaj ke appointments", SECOND_DOCTOR)


def test_signup_cannot_take_a_number_another_business_lists(two):
    clinic, _, _ = two
    add_number(clinic, SECOND_DOCTOR)
    with TestClient(app, headers=APP_HEADERS) as c:
        body = {
            "user": {"name": "Owner", "email": "late@example.com", "password": "another pass"},
            "business": {
                "template": "wholesale",
                "name": "Late Shop",
                "address": "1 Test Road",
                "hours": [["09:00", "19:00"]],
                "owner_whatsapp": SECOND_DOCTOR[3:],
                "consent": True,
            },
            "details": {},
        }
        r = c.post("/api/signup", json=body)
        assert r.status_code == 409 and r.json()["code"] == "WHATSAPP_TAKEN"


def test_commands_follow_the_template(two):
    _, _, wa = two
    assert "aaj ke orders" in send(wa, "help", SHOP_OWNER)
    assert "appointments" in send(wa, "help", CLINIC_OWNER)
    assert "Samajh nahi aaya" in send(wa, "kal chhutti", SHOP_OWNER)  # no schedule there
    assert "Samajh nahi aaya" in send(wa, "aaj ke orders", CLINIC_OWNER)  # no orders there


# Wholesale commands


def test_rate_change_previews_then_applies(two):
    _, shop, wa = two
    reply = send(wa, "rate Paracetamol 500 mg tablets 20", SHOP_OWNER)
    assert "Paracetamol 500 mg tablets (Strip of 10): ₹18 → ₹20" in reply and "Haan/Nahi" in reply
    assert catalogue(shop)["Paracetamol 500 mg tablets"]["rate"] == "₹18"  # not yet
    assert "Ho gaya — live hai." in send(wa, "haan", SHOP_OWNER)
    assert catalogue(shop)["Paracetamol 500 mg tablets"]["rate"] == "₹20"


def test_nahi_changes_nothing(two):
    _, shop, wa = two
    send(wa, "rate Paracetamol 500 mg tablets 99", SHOP_OWNER)
    assert "kuch nahi badla" in send(wa, "nahi", SHOP_OWNER)
    assert catalogue(shop)["Paracetamol 500 mg tablets"]["rate"] == "₹18"


def test_a_partial_product_name_is_never_guessed(two):
    _, _, wa = two
    reply = send(wa, "rate Paracetamol 500 42", SHOP_OWNER)
    assert "ek exact product nahi hai" in reply and "Paracetamol 500 mg tablets" in reply
    assert "Abhi koi badlav pending nahi" in send(wa, "haan", SHOP_OWNER)
    reply = send(wa, "stock khatam paracetamol", SHOP_OWNER)
    assert "500 mg" in reply and "650 mg" in reply and "Poora naam" in reply
    assert "nahi mila" in send(wa, "stock khatam cough syrup", SHOP_OWNER)


@pytest.mark.parametrize(
    "text",
    ["stock khatam Paracetamol 650 mg tablets", "Paracetamol 650 mg tablets khatam ho gaya"],
)
def test_stock_out(two, text):
    _, shop, wa = two
    assert "out of stock kar dein" in send(wa, text, SHOP_OWNER)
    send(wa, "ha", SHOP_OWNER)
    assert catalogue(shop)["Paracetamol 650 mg tablets"]["in_stock"] is False


def test_stock_in_and_already_in_stock(two):
    _, shop, wa = two
    assert "in stock kar dein" in send(wa, "stock aa gaya Surgical gloves", SHOP_OWNER)
    send(wa, "yes", SHOP_OWNER)
    assert catalogue(shop)["Surgical gloves"]["in_stock"] is True
    assert "pehle se in stock" in send(wa, "Surgical gloves aa gaya", SHOP_OWNER)


def test_order_status_by_whatsapp(two):
    _, shop, wa = two
    reply = send(wa, "order 1 dispatch", SHOP_OWNER)
    assert "naya hai; dispatched nahi ho sakta" in reply  # new → dispatched skips a step
    assert "Abhi koi badlav pending nahi" in send(wa, "haan", SHOP_OWNER)
    reply = send(wa, "order 1 confirm", SHOP_OWNER)
    assert "Order 1 (Test Medical) ko confirmed mark karein?" in reply
    send(wa, "haan", SHOP_OWNER)
    send(wa, "order 1 ko dispatch karo", SHOP_OWNER)
    send(wa, "ok", SHOP_OWNER)
    assert shop.get("/api/orders").json()["orders"][0]["status"] == "dispatched"
    assert "Order 7 nahi mila" in send(wa, "order 7 dispatch", SHOP_OWNER)


def test_wholesale_summary_counts(two):
    _, _, wa = two
    reply = send(wa, "summary", SHOP_OWNER)
    assert "Aaj: 1 orders, ₹72, 1 dispatch baaki" in reply and "Is hafte: 1 orders" in reply


def test_agent_ko_bolo_works_on_both_templates(two):
    clinic, shop, wa = two
    assert "Sahi hai? Haan/Nahi" in send(wa, "agent ko bolo Sunday ko band rehta hai", SHOP_OWNER)
    assert "Sahi hai? Haan/Nahi" in send(wa, "agent ko bolo hindi mein baat karo", CLINIC_OWNER)
    send(wa, "haan", SHOP_OWNER)
    assert shop.get("/api/instructions").json()["text"] == "Sunday ko band rehta hai"
    assert clinic.get("/api/instructions").json()["text"] == ""  # not confirmed yet


def test_one_owner_cannot_touch_another_business(two):
    _, shop, wa = two
    send(wa, "rate Paracetamol 500 mg tablets 1", CLINIC_OWNER)
    send(wa, "haan", CLINIC_OWNER)
    assert catalogue(shop)["Paracetamol 500 mg tablets"]["rate"] == "₹18"


# Review fixes (#35)


@pytest.mark.parametrize("name", ["Potato", "Kabab", "Cars"])
def test_rate_keeps_names_that_end_like_a_currency_word(two, name):
    """'rate potato 40' used to read the product as 'pota' (the 'to' was taken as a separator)."""
    _, shop, wa = two
    shop.post("/api/catalog", json={"name": name, "rate": "10"})
    reply = send(wa, f"rate {name.lower()} 40", SHOP_OWNER)
    assert f"{name}: ₹10 → ₹40" in reply
    send(wa, "haan", SHOP_OWNER)
    assert catalogue(shop)[name]["rate"] == "₹40"


@pytest.mark.parametrize("text", ["payment aaya", "driver aa gaya", "aaj ka kaam khatam"])
def test_everyday_messages_are_not_stock_commands(two, raw, text):
    _, _, wa = two
    assert "Samajh nahi aaya" in send(wa, text, SHOP_OWNER)
    note = raw.execute("SELECT note FROM inbox WHERE kind = 'ops' ORDER BY id DESC").fetchone()
    assert note["note"] == f"WhatsApp: {text}"


def test_a_disabled_command_is_refused_even_after_haan(two, monkeypatch):
    from src.verticals import loader

    _, shop, wa = two
    send(wa, "rate Paracetamol 500 mg tablets 20", SHOP_OWNER)
    real = loader.whatsapp_commands
    monkeypatch.setattr(
        loader,
        "whatsapp_commands",
        lambda t: real(t) - {"set_rate"} if t == "wholesale" else real(t),
    )
    assert "nahi hai" in send(wa, "haan", SHOP_OWNER)
    assert catalogue(shop)["Paracetamol 500 mg tablets"]["rate"] == "₹18"


def test_weekly_summary_counts_every_order(two, monkeypatch):
    from src.orders import service as orders

    _, _, wa = two
    monkeypatch.setattr(orders, "PAGE_SIZE", 1)  # a page cap must never cap the counts
    _, shop, _ = two
    pid = catalogue(shop)["Paracetamol 500 mg tablets"]["id"]
    shop.post("/api/orders", json={"shop_name": "Other", "items": [{"product_id": pid, "qty": 1}]})
    assert "Aaj: 2 orders, ₹90" in send(wa, "summary", SHOP_OWNER)


def test_every_enabled_command_is_one_the_code_handles():
    from src.channels.whatsapp import commands
    from src.verticals import loader

    assert set(commands.ALL_INTENTS) - {"help"} == loader.WHATSAPP_COMMANDS
    for template in ("clinic", "wholesale"):
        assert loader.whatsapp_commands(template) <= loader.WHATSAPP_COMMANDS


def test_an_unknown_command_in_vertical_yaml_fails_validation(tmp_path):
    import shutil

    from src.verticals import loader

    copy = tmp_path / "wholesale"
    shutil.copytree(loader.template_dir("wholesale"), copy)
    text = (copy / "vertical.yaml").read_text(encoding="utf-8")
    (copy / "vertical.yaml").write_text(
        text.replace("commands: [orders_today,", "commands: [order_dispatch, orders_today,"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unknown whatsapp commands"):
        loader.validate(copy)


def test_startup_gives_a_number_to_the_business_that_owns_it(two, raw):
    """An older business listing a number never takes it from the business whose owner number it
    is (the review of #36, point 4)."""
    clinic, shop, wa = two
    clinic_id = raw.execute(
        "SELECT id FROM tenants WHERE owner_whatsapp = ?", (CLINIC_OWNER,)
    ).fetchone()["id"]
    settings = raw.execute("SELECT settings FROM tenants WHERE id = ?", (clinic_id,)).fetchone()
    import json

    s = json.loads(settings["settings"])
    s["whatsapp_numbers"] = [*s["whatsapp_numbers"], SHOP_OWNER]  # data from before the 409
    with raw:
        raw.execute("UPDATE tenants SET settings = ? WHERE id = ?", (json.dumps(s), clinic_id))
    with TestClient(app) as restarted:
        reply = send(restarted, "aaj ke orders", SHOP_OWNER)
    assert "Test Medical" in reply  # still the shop's own business

"""Phase 2 M4a: wholesale catalogue, CSV import and the order lifecycle."""

import pytest
from conftest import APP_HEADERS
from fastapi.testclient import TestClient

from src.core import db
from src.main import app
from src.orders import catalog
from src.orders import service as orders


def signup(c, template="wholesale", n=1):
    body = {
        "user": {"name": "Owner", "email": f"w{n}@example.com", "password": "another pass"},
        "business": {
            "template": template,
            "name": f"Traders {n}",
            "address": "Market Road",
            "hours": [["09:30", "19:30"]],
            "owner_whatsapp": f"90000 0002{n}",
            "consent": True,
        },
        "details": {"doctors": [{"name": "Dr. Test"}]} if template == "clinic" else {},
    }
    r = c.post("/api/signup", json=body)
    assert r.status_code == 200, r.text
    return r.json()["public_id"]


@pytest.fixture
def shop(isolated):
    """A logged-in wholesale owner with three products."""
    with TestClient(app, headers=APP_HEADERS) as c:
        signup(c)
        for name, pack, rate, stock in (
            ("Paracetamol 500 mg tablets", "Strip of 10", "18", True),
            ("Paracetamol 650 mg tablets", "Strip of 15", "30.50", True),
            ("Hand sanitiser", "500 ml bottle", "120", False),
        ):
            r = c.post(
                "/api/catalog",
                json={"name": name, "pack_size": pack, "rate": rate, "in_stock": stock},
            )
            assert r.status_code == 200, r.text
        yield c


def products(c):
    return {p["name"]: p for p in c.get("/api/catalog").json()["products"]}


def order(c, *lines, **extra):
    body = {"shop_name": "Gupta Medical", "items": [{"product_id": p, "qty": q} for p, q in lines]}
    return c.post("/api/orders", json=body | extra)


# Money and names


@pytest.mark.parametrize(
    "text, paise",
    [("18", 1800), ("30.50", 3050), ("₹1,234.5", 123450), (" Rs. 99 ", 9900), (12.25, 1225)],
)
def test_rates_parse_to_paise(text, paise):
    assert catalog.parse_rate(text) == paise


@pytest.mark.parametrize("text", ["", "abc", "0", "-5", "12.345", "1,00,00,00,001"])
def test_bad_rates_are_refused_in_plain_words(text):
    with pytest.raises(ValueError, match="Rate must"):
        catalog.parse_rate(text)


@pytest.mark.parametrize(
    "paise, text",
    [(1800, "₹18"), (3050, "₹30.50"), (12345600, "₹1,23,456"), (100000000, "₹10,00,000")],
)
def test_rupees_use_indian_grouping(paise, text):
    assert catalog.format_inr(paise) == text


# Catalogue


def test_catalogue_add_list_and_edit(shop):
    p = products(shop)
    assert p["Paracetamol 650 mg tablets"]["rate"] == "₹30.50"
    assert p["Hand sanitiser"]["in_stock"] is False
    pid = p["Hand sanitiser"]["id"]
    r = shop.put(f"/api/catalog/{pid}", json={"in_stock": True, "rate": "125"})
    assert r.json()["in_stock"] is True and r.json()["rate_paise"] == 12500
    r = shop.post("/api/catalog", json={"name": "hand  SANITISER", "rate": "1"})
    assert r.status_code == 422 and "already in the catalogue" in r.json()["detail"]
    assert shop.put("/api/catalog/9999", json={"rate": "1"}).status_code == 404
    r = shop.post("/api/catalog", json={"name": "Glucose", "rate": "free"})
    assert r.status_code == 422 and r.json()["fields"]["rate"].startswith("Rate must")


def test_hidden_products_leave_the_catalogue_but_not_the_full_list(shop):
    pid = products(shop)["Hand sanitiser"]["id"]
    shop.put(f"/api/catalog/{pid}", json={"active": False})
    assert "Hand sanitiser" not in products(shop)
    everything = shop.get("/api/catalog", params={"all": "true"}).json()["products"]
    assert "Hand sanitiser" in {p["name"] for p in everything}


def scoped(c):
    me = c.get("/api/me").json()["business"]["public_id"]
    conn = db.connect()
    row = conn.execute("SELECT id FROM tenants WHERE public_id = ?", (me,)).fetchone()
    return conn.for_tenant(row["id"])


def test_spoken_names_find_one_product_or_ask(shop):
    conn = scoped(shop)
    try:
        assert catalog.find(conn, "paracetamol 650")["name"] == "Paracetamol 650 mg tablets"
        assert catalog.find(conn, "HAND sanitiser")["name"] == "Hand sanitiser"
        with pytest.raises(catalog.CatalogError) as ambiguous:
            catalog.find(conn, "paracetamol")
        assert {m["name"] for m in ambiguous.value.matches} == {
            "Paracetamol 500 mg tablets",
            "Paracetamol 650 mg tablets",
        }
        with pytest.raises(catalog.CatalogError) as misspelt:
            catalog.find(conn, "hand sanitizer")
        assert [m["name"] for m in misspelt.value.matches] == ["Hand sanitiser"]
        with pytest.raises(catalog.CatalogError) as unknown:
            catalog.find(conn, "cough syrup")
        assert unknown.value.code == "UNKNOWN_PRODUCT" and unknown.value.matches == []
    finally:
        conn.close()


# CSV import


def upload(c, text):
    return c.post(
        "/api/catalog/import", content=text.encode(), headers={"Content-Type": "text/csv"}
    )


def test_csv_import_keeps_good_rows_and_reports_bad_ones(shop):
    text = (
        "Name,Pack_size,Rate,In_stock\n"
        "Cotton roll,100 g,58,yes\n"  # row 2: added
        ",1 piece,10,yes\n"  # row 3: no name
        "Crepe bandage,1 roll,ninety,yes\n"  # row 4: bad rate
        "Hand sanitiser,500 ml bottle,130,yes\n"  # row 5: updates the existing product
        "Gloves,Box of 100,450,maybe\n"  # row 6: bad stock value
        "\n"  # blank lines are skipped
        "cotton ROLL,200 g,99,yes\n"  # row 8: same product as row 2
    )
    r = upload(shop, text).json()
    assert (r["added"], r["updated"]) == (1, 1)
    assert [(e["row"], e["message"].split()[0]) for e in r["errors"]] == [
        (3, "Product"),
        (4, "Rate"),
        (6, "In"),
        (8, "cotton"),
    ]
    p = products(shop)
    assert p["Cotton roll"]["rate"] == "₹58" and p["Hand sanitiser"]["rate_paise"] == 13000
    assert p["Hand sanitiser"]["in_stock"] is True


def test_csv_without_a_header_says_so(shop):
    r = upload(shop, "Cotton roll,100 g,58,yes\n").json()
    assert r["added"] == 0 and r["errors"][0]["row"] == 1


def test_csv_that_isnt_text_or_is_empty_is_refused(shop):
    r = shop.post(
        "/api/catalog/import", content=b"\xff\xfe\x00bad", headers={"Content-Type": "text/csv"}
    )
    assert r.status_code == 422 and "CSV" in r.json()["detail"]
    assert upload(shop, "  ").status_code == 422


def test_sample_catalogue_downloads_and_imports_cleanly(shop):
    r = shop.get("/api/templates/wholesale/sample-catalog.csv")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    result = upload(shop, r.text).json()
    assert result["errors"] == [] and result["added"] + result["updated"] >= 8
    assert shop.get("/api/templates/clinic/sample-catalog.csv").status_code == 404
    assert shop.get("/api/templates/nope/sample-catalog.csv").status_code == 404


# Orders


def test_order_uses_catalogue_rates_and_keeps_them(shop):
    p = products(shop)
    a, b = p["Paracetamol 500 mg tablets"]["id"], p["Paracetamol 650 mg tablets"]["id"]
    r = order(shop, (a, 10), (b, 3), phone="98765 00011", contact_name="Mr. Gupta")
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["number"] == 1 and o["status"] == "new" and o["source"] == "walk_in"
    assert o["phone"] == "+919876500011"
    assert [(x["name"], x["qty"], x["rate"], x["amount"]) for x in o["items"]] == [
        ("Paracetamol 500 mg tablets", 10, "₹18", "₹180"),
        ("Paracetamol 650 mg tablets", 3, "₹30.50", "₹91.50"),
    ]
    assert o["total"] == "₹271.50"
    shop.put(f"/api/catalog/{a}", json={"rate": "20", "name": "Paracetamol 500 tabs"})
    again = shop.get("/api/orders").json()["orders"][0]
    assert again["items"][0]["rate"] == "₹18" and again["items"][0]["name"].startswith(
        "Paracetamol 500 mg"
    )


def test_order_lifecycle(shop):
    pid = products(shop)["Paracetamol 500 mg tablets"]["id"]
    oid = order(shop, (pid, 1)).json()["id"]

    def move(status):
        return shop.post(f"/api/orders/{oid}/status", json={"status": status})

    assert move("delivered").json()["code"] == "INVALID_TRANSITION"
    assert move("confirmed").json()["next"] == ["dispatched", "cancelled"]
    assert move("dispatched").json()["next"] == ["delivered"]
    r = move("cancelled")
    assert r.status_code == 409 and r.json()["code"] == "INVALID_TRANSITION"
    assert move("delivered").json()["next"] == []
    assert move("cancelled").status_code == 409
    assert move("bogus").status_code == 422
    assert shop.post("/api/orders/9999/status", json={"status": "confirmed"}).status_code == 404


def test_new_and_confirmed_orders_can_be_cancelled_once(shop):
    pid = products(shop)["Paracetamol 500 mg tablets"]["id"]
    for first in ([], ["confirmed"]):
        oid = order(shop, (pid, len(first) + 1)).json()["id"]
        for status in first:
            shop.post(f"/api/orders/{oid}/status", json={"status": status})
        r = shop.post(f"/api/orders/{oid}/status", json={"status": "cancelled"})
        assert r.json()["status"] == "cancelled" and r.json()["next"] == []
        assert (
            shop.post(f"/api/orders/{oid}/status", json={"status": "confirmed"}).status_code == 409
        )


def test_out_of_stock_is_refused_without_a_substitute(shop):
    p = products(shop)
    r = order(shop, (p["Paracetamol 500 mg tablets"]["id"], 1), (p["Hand sanitiser"]["id"], 2))
    body = r.json()
    assert r.status_code == 409 and body["code"] == "OUT_OF_STOCK"
    assert "alternatives" not in body  # never another product
    assert shop.get("/api/orders").json()["orders"] == []


@pytest.mark.parametrize("qty", [0, -1, 10000])
def test_quantity_must_be_1_to_9999(shop, qty):
    pid = products(shop)["Paracetamol 500 mg tablets"]["id"]
    assert order(shop, (pid, qty)).status_code == 422


def test_same_product_twice_is_merged_and_capped(shop):
    pid = products(shop)["Paracetamol 500 mg tablets"]["id"]
    assert order(shop, (pid, 2), (pid, 3)).json()["items"][0]["qty"] == 5
    r = order(shop, (pid, 9000), (pid, 1000), shop_name="Other Shop")
    assert r.status_code == 422


def test_unknown_product_id_is_refused(shop):
    r = order(shop, (9999, 1))
    assert r.status_code == 422 and r.json()["code"] == "UNKNOWN_PRODUCT"


def test_duplicate_order_points_to_the_existing_one(shop):
    pid = products(shop)["Paracetamol 500 mg tablets"]["id"]
    first = order(shop, (pid, 4), phone="98765 00011").json()
    r = order(shop, (pid, 4), phone="98765 00011", shop_name="Different Name")
    body = r.json()
    assert r.status_code == 409 and body["code"] == "DUPLICATE_ORDER"
    assert body["alternatives"][0]["number"] == first["number"] and "order 1" in body["detail"]
    assert order(shop, (pid, 5), phone="98765 00011").status_code == 200  # different items
    forced = order(shop, (pid, 4), phone="98765 00011", allow_duplicate=True)
    assert forced.status_code == 200 and forced.json()["number"] == 3


def test_resend_with_the_same_key_never_duplicates(shop):
    pid = products(shop)["Paracetamol 500 mg tablets"]["id"]
    a = order(shop, (pid, 1), idempotency_key="page-123").json()
    b = order(shop, (pid, 1), idempotency_key="page-123").json()
    assert a["id"] == b["id"] and len(shop.get("/api/orders").json()["orders"]) == 1


def test_orders_filter_by_status_and_date(shop):
    pid = products(shop)["Paracetamol 500 mg tablets"]["id"]
    a = order(shop, (pid, 1)).json()["id"]
    order(shop, (pid, 2))
    shop.post(f"/api/orders/{a}/status", json={"status": "confirmed"})
    assert [
        o["id"] for o in shop.get("/api/orders", params={"status": "confirmed"}).json()["orders"]
    ] == [a]
    assert len(shop.get("/api/orders", params={"date": "2026-10-27"}).json()["orders"]) == 2
    assert shop.get("/api/orders", params={"date": "2026-10-28"}).json()["orders"] == []
    assert shop.get("/api/orders", params={"status": "lost"}).status_code == 422
    assert shop.get("/api/orders", params={"date": "tomorrow"}).status_code == 422


def test_spoken_product_names_resolve_in_the_service(shop):
    conn = scoped(shop)
    try:
        o = orders.create(
            conn, "Sharma Stores", [orders.Line(qty=2, product="paracetamol 650")], "phone"
        )
        assert o["items"][0]["name"] == "Paracetamol 650 mg tablets" and o["source"] == "phone"
        with pytest.raises(orders.OrderError) as e:
            orders.create(
                conn, "Sharma Stores", [orders.Line(qty=1, product="paracetamol")], "phone"
            )
        assert e.value.code == "UNKNOWN_PRODUCT" and len(e.value.matches) == 2
    finally:
        conn.close()


# Isolation and templates


def test_one_business_never_sees_or_touches_anothers_orders(shop):
    pid = products(shop)["Paracetamol 500 mg tablets"]["id"]
    oid = order(shop, (pid, 1)).json()["id"]
    with TestClient(app, headers=APP_HEADERS) as other:
        signup(other, n=2)
        assert other.get("/api/catalog").json()["products"] == []
        assert other.get("/api/orders").json()["orders"] == []
        assert (
            other.post(f"/api/orders/{oid}/status", json={"status": "confirmed"}).status_code == 404
        )
        assert other.put(f"/api/catalog/{pid}", json={"rate": "1"}).status_code == 404
        assert order(other, (pid, 1)).json()["code"] == "UNKNOWN_PRODUCT"
        other.post("/api/catalog", json={"name": "Cotton roll", "rate": "58"})
        mine = other.get("/api/catalog").json()["products"][0]["id"]
        assert order(other, (mine, 1)).json()["number"] == 1  # numbers count per business
    assert shop.get("/api/orders").json()["orders"][0]["status"] == "new"
    assert products(shop)["Paracetamol 500 mg tablets"]["rate"] == "₹18"


def test_a_clinic_has_no_catalogue_or_orders(isolated):
    with TestClient(app, headers=APP_HEADERS) as c:
        signup(c, "clinic", 3)
        for path in ("/api/catalog", "/api/orders"):
            r = c.get(path)
            assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"


def test_orders_need_a_login(isolated):
    with TestClient(app, headers=APP_HEADERS) as c:
        assert c.get("/api/orders").status_code == 401
        assert c.post("/api/catalog", json={"name": "x", "rate": "1"}).status_code == 401


def test_wholesale_settings_save(shop):
    s = shop.get("/api/settings").json()["settings"]
    body = {
        "name": s["name"],
        "address": s["address"],
        "sessions": s["sessions"],
        "min_order": "₹2,000",
        "delivery_area": "Within 10 km",
    }
    r = shop.put("/api/settings", json=body)
    assert r.status_code == 200 and r.json()["saved"] is True
    assert shop.get("/api/settings").json()["settings"]["delivery_area"] == "Within 10 km"
    r = shop.put("/api/settings", json={**body, "sessions": [["19:00", "09:00"]]})
    assert r.status_code == 422 and "start before end" in r.json()["detail"]


def test_public_board_shows_todays_orders_masked(shop):
    pid = products(shop)["Paracetamol 500 mg tablets"]["id"]
    order(shop, (pid, 3), phone="98765 00011", shop_name="Gupta Medical Store")
    public_id = shop.get("/api/me").json()["business"]["public_id"]
    shop.cookies.clear()
    board = shop.get(f"/api/try/{public_id}/board").json()
    assert board["kind"] == "orders"
    (o,) = board["orders"]
    assert o["shop"] == "Gupta S." and o["items"] == 1 and o["total"] == "₹54"
    assert o["number"] == "1" and o["status"] == "new"
    assert "98765" not in str(board) and "Medical" not in str(board)


# Review fixes (#32)


def test_a_hidden_product_is_never_swapped_for_a_visible_one(shop):
    """'Cotton roll' is hidden and 'Cotton roll large' is active: 'cotton roll' must not order
    the large one."""
    shop.post("/api/catalog", json={"name": "Cotton roll", "rate": "58"})
    shop.post("/api/catalog", json={"name": "Cotton roll large", "rate": "95"})
    shop.put(f"/api/catalog/{products(shop)['Cotton roll']['id']}", json={"active": False})
    conn = scoped(shop)
    try:
        with pytest.raises(catalog.CatalogError) as e:
            catalog.find(conn, "cotton roll")
        assert "isn't available right now" in str(e.value) and e.value.matches == []
        with pytest.raises(orders.OrderError) as e:
            orders.create(conn, "Test Shop", [orders.Line(qty=1, product="Cotton Roll")], "phone")
        assert e.value.code == "UNKNOWN_PRODUCT"
        assert catalog.find(conn, "cotton roll large")["name"] == "Cotton roll large"
    finally:
        conn.close()


def test_only_whole_words_stand_in_for_a_name(shop):
    conn = scoped(shop)
    try:
        assert catalog.find(conn, "sanitiser")["name"] == "Hand sanitiser"  # a whole word
        with pytest.raises(catalog.CatalogError) as e:  # run-together words: confirm, never assume
            catalog.find(conn, "paracetamol650")
        assert [m["name"] for m in e.value.matches] == ["Paracetamol 650 mg tablets"]
    finally:
        conn.close()


def test_unreadable_csv_saves_nothing_and_says_so(shop):
    huge = '"' + "x" * 140_000 + '"'  # bigger than the csv module's field limit
    text = f"name,pack_size,rate,in_stock\nCotton roll,100 g,58,yes\n{huge},1,10,yes\n"
    r = upload(shop, text)
    assert r.status_code == 200
    body = r.json()
    assert (body["added"], body["updated"]) == (0, 0) and "Nothing was imported" in body["errors"][
        0
    ]["message"]
    assert "Cotton roll" not in products(shop)


def test_nul_characters_from_excel_are_ignored(shop):
    r = upload(shop, "name,pack_size,rate,in_stock\nCotton\x00 roll,100 g,58,yes\n").json()
    assert r["added"] == 1 and r["errors"] == []


def test_names_in_any_indian_script(shop):
    text = "name,pack_size,rate,in_stock\nஅரிசி,1 kg,60,yes\nAtta ஆட்டா,5 kg,250,yes\nAtta ಹಿಟ್ಟು,5 kg,255,yes\n"
    r = upload(shop, text).json()
    assert r["added"] == 3 and r["errors"] == []
    assert catalog.name_key("Atta ஆட்டா") != catalog.name_key("Atta ಹಿಟ್ಟು")
    assert catalog.name_key("  PARACETAMOL-500 ") == "paracetamol 500"
    assert catalog.name_key("आटा (5 किलो)") == "आटा 5 किलो"


def test_too_big_upload_is_refused_before_it_is_read(shop):
    r = shop.post(
        "/api/catalog/import",
        content=b"a" * (1_000_001),
        headers={"Content-Type": "text/csv"},
    )
    assert r.status_code == 422 and "too big" in r.json()["detail"]


def test_order_list_pages(shop):
    pid = products(shop)["Paracetamol 500 mg tablets"]["id"]
    ids = [order(shop, (pid, n)).json()["id"] for n in (1, 2, 3)]
    first = shop.get("/api/orders", params={"limit": 2}).json()
    assert [o["id"] for o in first["orders"]] == ids[:0:-1] and first["next_before_id"] == ids[1]
    rest = shop.get("/api/orders", params={"limit": 2, "before_id": first["next_before_id"]}).json()
    assert [o["id"] for o in rest["orders"]] == ids[:1] and rest["next_before_id"] is None

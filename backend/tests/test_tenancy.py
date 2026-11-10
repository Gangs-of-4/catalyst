"""Business A can never read or change business B's data (contracts.md §3.1, ADR-0039)."""

from datetime import date

import pytest

from src import inbox
from src.agents import calls
from src.booking import service as bk
from src.channels.whatsapp import commands
from src.core import db, tenancy
from src.core import settings as cs

TOMORROW = date(2026, 10, 28)  # Wednesday, open


@pytest.fixture
def two(conn):
    """(A, B): the demo clinic and a second clinic with the same doctors and hours."""
    s = cs.load(conn)
    b_id = tenancy.create(conn, "clinic", {**s, "name": "Second Clinic"}, public_id="second")
    return conn, conn.for_tenant(b_id)


def test_bookings_are_invisible_and_untouchable_across_businesses(two):
    a, b = two
    sa, sb = cs.load(a), cs.load(b)
    booking_id = bk.book(a, sa, "dr-a", TOMORROW, "17:00", "Caller A", "+919000000001", "phone")

    assert bk.get(b, booking_id) is None
    assert bk.upcoming_for_phone(b, "+919000000001") == []
    grid = bk.day_grid(b, sb, TOMORROW)
    assert all(not sl["bookings"] for col in grid["columns"] for sl in col["slots"])
    with pytest.raises(bk.BookingError) as e:
        bk.set_status(b, booking_id, "cancelled")
    assert e.value.code == "NOT_FOUND"
    with pytest.raises(bk.BookingError):
        bk.cancel(b, booking_id)
    assert bk.get(a, booking_id)["status"] == "booked"


def test_slot_lock_is_per_business(two):
    a, b = two
    bk.book(a, cs.load(a), "dr-a", TOMORROW, "17:00", "Caller A", None, "phone")
    # The same doctor id and slot in another business is a different resource.
    bk.book(b, cs.load(b), "dr-a", TOMORROW, "17:00", "Caller B", None, "walk_in")
    with pytest.raises(bk.BookingError) as e:
        bk.book(b, cs.load(b), "dr-a", TOMORROW, "17:00", "Caller C", None, "walk_in")
    assert e.value.code == "SLOT_TAKEN"


def test_blocks_only_affect_their_business(two):
    a, b = two
    block_id = bk.add_block(a, TOMORROW, "holiday", "test")
    assert bk.free_slots(a, cs.load(a), TOMORROW) == []
    assert bk.free_slots(b, cs.load(b), TOMORROW)
    assert bk.list_blocks(b, TOMORROW) == []
    assert bk.remove_block(b, block_id) is False
    assert len(bk.list_blocks(a, TOMORROW)) == 1


def test_inbox_items_stay_in_their_business(two):
    a, b = two
    item = inbox.create(a, "callback", name="Caller A", phone="+919000000001")
    assert inbox.open_items(b) == []
    assert inbox.mark_done(b, item) is False
    assert [i["id"] for i in inbox.open_items(a)] == [item]


def test_calls_with_the_same_id_are_separate_per_business(two):
    a, b = two
    calls.flag(a, "call-1", "booked")
    calls.touch(b, "call-1")
    row_a = a.execute("SELECT * FROM calls WHERE tenant_id = ? AND id = 'call-1'", (a.tid,))
    row_b = b.execute("SELECT * FROM calls WHERE tenant_id = ? AND id = 'call-1'", (b.tid,))
    assert row_a.fetchone()["booked"] == 1
    assert row_b.fetchone()["booked"] == 0


def test_settings_are_per_business(two):
    a, b = two
    sb = cs.load(b)
    sb["name"] = "Renamed B"
    cs.save(b, sb)
    assert cs.load(a)["name"] != "Renamed B"
    assert tenancy.get(a, b.tid)["name"] == "Renamed B"


def test_pending_whatsapp_actions_are_per_business(two):
    a, b = two
    commands.save_pending(a, "+919000000009", commands.Command(intent="help"))
    assert commands.has_pending(a, "+919000000009")
    assert not commands.has_pending(b, "+919000000009")


def test_query_on_tenant_table_without_tenant_filter_is_refused(conn):
    with pytest.raises(db.ScopeError):
        conn.execute("SELECT * FROM bookings")
    with pytest.raises(db.ScopeError):
        conn.execute("UPDATE inbox SET done_at = 'x' WHERE id = 1")
    with pytest.raises(db.ScopeError):
        conn.execute("DELETE FROM blocks")
    conn.execute("SELECT * FROM tenants")  # not a tenant table


def test_unscoped_connection_has_no_tenant():
    c = db.connect()
    try:
        with pytest.raises(db.ScopeError):
            _ = c.tid
    finally:
        c.close()


def test_owner_whatsapp_is_unique_across_businesses(conn):
    s = cs.load(conn)
    tenancy.create(conn, "clinic", s, owner_whatsapp="+919000000010", public_id="one")
    with pytest.raises(db.Conflict):
        tenancy.create(conn, "clinic", s, owner_whatsapp="+919000000010", public_id="two")
    assert tenancy.by_whatsapp(conn, "+919000000010")["public_id"] == "one"


def test_unknown_template_is_refused(conn):
    with pytest.raises(ValueError):
        tenancy.create(conn, "bfsi", cs.load(conn))


def test_templates_lists_both_phase2_templates():
    assert {"clinic", "wholesale"} <= set(tenancy.templates())

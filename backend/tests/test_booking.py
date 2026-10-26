import sqlite3
from datetime import date

import pytest

from src.booking import service as bk
from src.core import db

TODAY = date(2026, 10, 27)      # Tuesday
TOMORROW = date(2026, 10, 28)
SUNDAY = date(2026, 11, 1)      # closed in the demo clinic


def test_same_slot_cannot_be_booked_twice(conn, settings):
    bk.book(conn, settings, "dr-a", TOMORROW, "17:00", "Caller One", "+910000000001", "phone")
    with pytest.raises(bk.BookingError) as e:
        bk.book(conn, settings, "dr-a", TOMORROW, "17:00", "Caller Two", "+910000000002", "walk_in")
    assert e.value.code == "SLOT_TAKEN"
    assert e.value.alternatives, "a conflict offers alternatives"
    assert conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0] == 1


def test_db_index_refuses_double_booking_even_without_app_checks(conn):
    """Two connections insert the same slot directly; the partial unique index lets only one through."""
    other = db.connect()
    sql = ("INSERT INTO bookings (resource_id, date, time, status, source, name, created_at, updated_at)"
           " VALUES ('dr-a', '2026-10-28', '17:00', 'booked', 'phone', 'X', 't', 't')")
    with conn:
        conn.execute(sql)
    with pytest.raises(sqlite3.IntegrityError):
        with other:
            other.execute(sql)
    other.close()


def test_race_between_check_and_insert_maps_to_slot_taken(conn, settings, monkeypatch):
    """If another channel wins between our free-slot check and insert, we still get SLOT_TAKEN, not a 500."""
    snapshot = bk.free_slots(conn, settings, TOMORROW, "dr-a")
    monkeypatch.setattr(bk, "free_slots", lambda *a, **k: snapshot)
    bk.book(conn, settings, "dr-a", TOMORROW, "17:00", "A", None, "phone")
    with pytest.raises(bk.BookingError) as e:
        bk.book(conn, settings, "dr-a", TOMORROW, "17:00", "B", None, "phone")
    assert e.value.code == "SLOT_TAKEN"


def test_cancel_frees_the_slot(conn, settings):
    bid = bk.book(conn, settings, "dr-a", TOMORROW, "17:00", "A", None, "phone")
    assert ("dr-a", "17:00") not in {(s.resource_id, s.time) for s in bk.free_slots(conn, settings, TOMORROW)}
    bk.cancel(conn, bid)
    assert ("dr-a", "17:00") in {(s.resource_id, s.time) for s in bk.free_slots(conn, settings, TOMORROW)}
    bk.book(conn, settings, "dr-a", TOMORROW, "17:00", "B", None, "phone")


def test_no_show_frees_the_slot(conn, settings):
    bid = bk.book(conn, settings, "dr-a", TOMORROW, "17:00", "A", None, "phone")
    bk.set_status(conn, bid, "no_show")
    bk.book(conn, settings, "dr-a", TOMORROW, "17:00", "Walk-in", None, "walk_in")


def test_closed_day_has_no_slots(conn, settings):
    assert bk.free_slots(conn, settings, SUNDAY) == []
    with pytest.raises(bk.BookingError):
        bk.book(conn, settings, "dr-a", SUNDAY, "10:00", "A", None, "phone")


def test_leave_blocks_one_doctor_only(conn, settings):
    bk.add_block(conn, TOMORROW, "leave", "whatsapp", resource_id="dr-a")
    free = bk.free_slots(conn, settings, TOMORROW)
    assert free and all(s.resource_id == "dr-b" for s in free)


def test_clinic_holiday_blocks_everyone(conn, settings):
    bk.add_block(conn, TOMORROW, "holiday", "whatsapp")
    assert bk.free_slots(conn, settings, TOMORROW) == []
    slots = bk.find_slots(conn, settings, TOMORROW, "17:00")
    assert slots and slots[0].date == date(2026, 10, 29)


def test_late_start_and_early_close(conn, settings):
    bk.add_block(conn, TOMORROW, "late_start", "whatsapp", "dr-a", "00:00", "11:00")
    bk.add_block(conn, TOMORROW, "early_close", "whatsapp", "dr-a", "18:00", "23:59")
    times = {s.time for s in bk.free_slots(conn, settings, TOMORROW, "dr-a")}
    assert "10:30" not in times and "11:00" in times
    assert "17:30" in times and "18:00" not in times


def test_past_times_today_are_excluded(conn, settings, monkeypatch):
    from datetime import datetime
    from src.core import config
    monkeypatch.setattr(config, "now", lambda: datetime(2026, 10, 27, 12, 10, tzinfo=config.IST))
    times = {s.time for s in bk.free_slots(conn, settings, TODAY)}
    assert "12:00" not in times and "12:30" in times


def test_reschedule_is_atomic(conn, settings):
    old = bk.book(conn, settings, "dr-a", TOMORROW, "17:00", "A", "+919000000001", "phone")
    bk.book(conn, settings, "dr-b", TOMORROW, "18:00", "B", None, "phone")
    with pytest.raises(bk.BookingError):
        bk.reschedule(conn, settings, old, "dr-b", TOMORROW, "18:00")
    assert bk.get(conn, old)["status"] == "booked", "a failed move leaves the old booking alone"
    new = bk.reschedule(conn, settings, old, "dr-a", TOMORROW, "18:30")
    assert bk.get(conn, old)["status"] == "cancelled"
    row = bk.get(conn, new)
    assert (row["time"], row["status"], row["phone"]) == ("18:30", "booked", "+919000000001")


def test_nearest_slot_ordering(conn, settings):
    slots = bk.find_slots(conn, settings, TOMORROW, "17:00", limit=3)
    assert [s.time for s in slots] == ["17:00", "17:30", "18:00"]
    bk.book(conn, settings, "dr-a", TOMORROW, "17:00", "A", None, "phone")
    bk.book(conn, settings, "dr-b", TOMORROW, "17:00", "B", None, "phone")
    slots = bk.find_slots(conn, settings, TOMORROW, "17:00", limit=2)
    assert [s.time for s in slots] == ["17:30", "18:00"]


def test_nearest_ordering_is_by_distance(conn, settings):
    slots = bk.find_slots(conn, settings, TOMORROW, "12:00", limit=3)
    assert [s.time for s in slots] == ["11:30", "12:00", "12:30"]


def test_specific_doctor(conn, settings):
    slots = bk.find_slots(conn, settings, TOMORROW, "17:00", resource_id="dr-b")
    assert slots and all(s.resource_id == "dr-b" for s in slots)

from datetime import date

import pytest

from src.booking.when import parse_date, parse_time, spoken_date, spoken_time

TODAY = date(2026, 10, 27)  # Tuesday


@pytest.mark.parametrize("text, expected", [
    ("2026-10-30", date(2026, 10, 30)),
    ("today", TODAY),
    ("aaj", TODAY),
    ("आज शाम", TODAY),
    ("tomorrow", date(2026, 10, 28)),
    ("kal shaam 5 baje", date(2026, 10, 28)),
    ("कल", date(2026, 10, 28)),
    ("day after tomorrow", date(2026, 10, 29)),
    ("parso subah", date(2026, 10, 29)),
    ("परसों", date(2026, 10, 29)),
    ("Monday", date(2026, 11, 2)),
    ("somvar", date(2026, 11, 2)),
    ("सोमवार", date(2026, 11, 2)),
    ("shukravar ko", date(2026, 10, 30)),
    ("शुक्रवार", date(2026, 10, 30)),
    ("guruvaar", date(2026, 10, 29)),
    ("Tuesday", TODAY),
    ("next Tuesday", date(2026, 11, 3)),
    ("agle mangalvar", date(2026, 11, 3)),
    ("28 Oct", date(2026, 10, 28)),
    ("Nov 3", date(2026, 11, 3)),
    ("3rd November", date(2026, 11, 3)),
    ("28/10", date(2026, 10, 28)),
    ("5/1", date(2027, 1, 5)),           # already past this year -> next year
    ("२८ अक्टूबर", date(2026, 10, 28)),
    ("sun lo, kal aana hai", date(2026, 10, 28)),  # "sun" (listen) is not Sunday
])
def test_parse_date(text, expected):
    assert parse_date(text, TODAY) == expected


@pytest.mark.parametrize("text", ["", "kabhi bhi", "31/02"])
def test_parse_date_none(text):
    assert parse_date(text, TODAY) is None


@pytest.mark.parametrize("text, expected", [
    ("5 baje", "17:00"),
    ("5 pm", "17:00"),
    ("5pm", "17:00"),
    ("17:00", "17:00"),
    ("shaam 5", "17:00"),
    ("subah 10", "10:00"),
    ("subah 10 baje", "10:00"),
    ("dopahar 2", "14:00"),
    ("dopahar 12 baje", "12:00"),
    ("saade 5", "17:30"),
    ("saade 10 baje subah", "10:30"),
    ("sawa 5", "17:15"),
    ("paune 5", "16:45"),
    ("10 am", "10:00"),
    ("11", "11:00"),
    ("1:30", "13:30"),
    ("6:30 pm", "18:30"),
    ("शाम ५ बजे", "17:00"),
    ("साढ़े पाँच बजे", "17:30"),
    ("raat 8 baje", "20:00"),
    ("paanch baje", "17:00"),
    ("evening 7", "19:00"),
    ("dedh baje", "13:30"),
])
def test_parse_time(text, expected):
    assert parse_time(text) == expected


@pytest.mark.parametrize("text", ["", "jaldi", "book kar do"])
def test_parse_time_none(text):
    assert parse_time(text) is None


def test_spoken_format():
    assert spoken_date(date(2026, 10, 28)) == "Wednesday, 28 October 2026"
    assert spoken_time("17:30") == "5:30 PM"
    assert spoken_time("10:00") == "10 AM"
    assert spoken_time("12:00") == "12 PM"

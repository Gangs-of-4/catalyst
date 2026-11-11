"""The log redaction filter."""

import logging

from src.core.log import _Redact


def record(msg, *args):
    return logging.LogRecord("catalyst", logging.INFO, __file__, 1, msg, args or None, None)


def filtered(msg, *args):
    r = record(msg, *args)
    assert _Redact().filter(r)
    return r.getMessage()


def test_number_formats_still_work():
    assert filtered("would send %d chars to %s", 42, "+919876543210") == (
        "would send 42 chars to <redacted>"
    )


def test_phone_numbers_in_the_message_are_redacted():
    assert filtered("callback for 98765 43210 created") == "callback for <redacted> created"


def test_ids_side_by_side_are_not_mistaken_for_a_phone():
    assert filtered("tenant %d booking %d %d", 12, 345, 678) == "tenant 12 booking 345 678"


def test_a_phone_passed_as_a_number_is_hidden():
    assert "9876543210" not in filtered("caller %s", 9876543210)


def test_a_bad_log_call_never_raises():
    assert "didn't fit" in filtered("count %d", "not a number")
    assert "didn't fit" in filtered("two %s %s", "only one")

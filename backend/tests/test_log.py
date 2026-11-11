"""The log redaction filter."""

import logging

from src.core.log import _Redact


def record(msg, *args):
    return logging.LogRecord("catalyst", logging.INFO, __file__, 1, msg, args or None, None)


def test_number_formats_still_work():
    r = record("would send %d chars to %s", 42, "+919876543210")
    assert _Redact().filter(r)
    assert r.getMessage() == "would send 42 chars to <redacted>"


def test_phone_numbers_in_the_message_are_redacted():
    r = record("callback for 98765 43210 created")
    _Redact().filter(r)
    assert r.getMessage() == "callback for <redacted> created"

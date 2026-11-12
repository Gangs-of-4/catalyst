"""App logger with a redaction filter: anything that looks like a phone number is masked."""

import logging
import re

# A phone-like run of digits that isn't part of a longer token: "8d30-7000-96c9" in a call id
# stays readable, "+91 98765 43210" is hidden.
_PHONE = re.compile(r"(?<![\w-])\+?\d[\d\s-]{8,}\d(?![\w-])")


_HIDDEN = "<redacted>"


def _redact_arg(value):
    """One log argument with anything phone-like hidden. Small numbers stay numbers, so %d works;
    each argument is checked on its own, so "%d %d %d" IDs never join into a phone-like run."""
    if isinstance(value, bool | float):
        return value
    if isinstance(value, int):
        return value if abs(value) < 10**9 else _HIDDEN
    return _PHONE.sub(_HIDDEN, str(value))


class _Redact(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _PHONE.sub(_HIDDEN, str(record.msg))
        if isinstance(record.args, dict):
            record.args = {k: _redact_arg(v) for k, v in record.args.items()}
        elif record.args:
            record.args = tuple(_redact_arg(a) for a in record.args)
        try:  # filters run outside the handler's error handling: never let a log line raise
            record.getMessage()
        except Exception:
            record.msg = f"{record.msg} [log arguments didn't fit the message]"
            record.args = None
        return True


log = logging.getLogger("catalyst")
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _h.addFilter(_Redact())
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False

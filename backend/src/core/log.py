"""App logger with a redaction filter: anything that looks like a phone number is masked."""

import logging
import re

_PHONE = re.compile(r"\+?\d[\d\s-]{8,}\d")


class _Redact(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Format first, then redact the finished line: redacting each argument turned numbers into
        # strings, which broke every %d message.
        record.msg = _PHONE.sub("<redacted>", record.getMessage())
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

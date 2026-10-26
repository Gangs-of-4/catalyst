"""Indian mobile numbers to E.164. Never log the result."""
import re

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def normalize(raw: str | None) -> str | None:
    """'98765 43210', '09876543210', '+91-9876543210', 'whatsapp:+91…' -> '+919876543210'. None if not a mobile."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw).translate(_DEVANAGARI_DIGITS))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in "6789":
        return "+91" + digits
    return None


def spoken(e164: str | None) -> str:
    """Last 10 digits grouped for read-back: '98765 43210'."""
    if not e164:
        return ""
    d = e164[-10:]
    return f"{d[:5]} {d[5:]}"

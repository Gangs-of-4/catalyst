"""A business's settings, stored as one JSON document on its `tenants` row."""

import difflib
import re

from . import db, tenancy


def load(conn: db.Conn) -> dict:
    return tenancy.load_settings(conn)


def save(conn: db.Conn, s: dict) -> None:
    tenancy.save_settings(conn, s)


def doctor(s: dict, doctor_id: str | None) -> dict | None:
    return next((d for d in s["doctors"] if d["id"] == doctor_id), None)


def doctor_name(s: dict, doctor_id: str) -> str:
    d = doctor(s, doctor_id)
    return d["name"] if d else doctor_id


def match_doctor(s: dict, text: str | None) -> dict | None:
    """Fuzzy match 'Dr Asha', 'asha ji', 'Verma madam', 'dr-a' or 'Doctor A' to a doctor."""
    if not text:
        return None
    t = text.lower().strip()
    for d in s["doctors"]:
        if t == d["id"].lower():
            return d
    t = re.sub(
        r"\b(dr|doctor|doc|daktar|madam|mam|maam|sir|ji|sahab|saheb|se|ke|ko|wali|wale)\b\.?",
        " ",
        t,
    )
    words = [w for w in re.split(r"[\s.,-]+", t) if len(w) > 1]
    if not words:
        letter = re.sub(r"\W", "", t)
        if len(letter) == 1:  # "Doctor A"
            idx = ord(letter) - ord("a")
            return s["doctors"][idx] if 0 <= idx < len(s["doctors"]) else None
        return None
    best, best_score = None, 0.0
    for d in s["doctors"]:
        name_words = [w for w in re.split(r"[\s.,-]+", d["name"].lower()) if w not in ("dr", "")]
        score = max(
            (difflib.SequenceMatcher(None, w, n).ratio() for w in words for n in name_words),
            default=0,
        )
        if score > best_score:
            best, best_score = d, score
    return best if best_score >= 0.75 else None


def doctor_slug(name: str, taken: set[str]) -> str:
    """A stable id like 'dr-asha-verma' from a doctor's name, unique among `taken`."""
    base = "dr-" + (
        re.sub(r"[^a-z0-9]+", "-", name.lower().replace("dr.", "").replace("dr ", "")).strip("-")
        or "x"
    )
    slug, n = base, 2
    while slug in taken:
        slug, n = f"{base}-{n}", n + 1
    return slug

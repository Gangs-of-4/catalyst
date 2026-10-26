"""Clinic settings, stored as one JSON document."""
import difflib
import re
import sqlite3

from . import db

KEY = "clinic"


def load(conn: sqlite3.Connection) -> dict:
    s = db.get_json(conn, KEY)
    if s is None:
        raise RuntimeError("Clinic settings missing; the app seeds them on startup.")
    return s


def save(conn: sqlite3.Connection, s: dict) -> None:
    db.put_json(conn, KEY, s)


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
    t = re.sub(r"\b(dr|doctor|doc|daktar|madam|mam|maam|sir|ji|sahab|saheb|se|ke|ko|wali|wale)\b\.?", " ", t)
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
            (difflib.SequenceMatcher(None, w, n).ratio() for w in words for n in name_words), default=0
        )
        if score > best_score:
            best, best_score = d, score
    return best if best_score >= 0.75 else None

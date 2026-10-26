"""Clinic-approved answers (C3). Built live from settings; nothing here is invented."""
import re
import sqlite3
from datetime import date, timedelta

from ..booking import service as bk
from ..booking.when import short_date, spoken_time
from ..core import config
from ..core import settings as cs

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

TOPIC_WORDS = {
    "hours": ["time", "timing", "timings", "open", "close", "closed", "khula", "khulta", "band", "kab", "hours",
              "sunday", "ravivar", "itvar", "samay", "baje", "chhutti", "holiday", "leave", "खुला", "बंद", "कब"],
    "location": ["where", "address", "location", "kahan", "kidhar", "pata", "landmark", "rasta", "map", "कहाँ", "कहां", "पता"],
    "doctors": ["doctor", "doctors", "dr", "daktar", "dentist", "kaun", "डॉक्टर"],
    "fees": ["fee", "fees", "charge", "charges", "cost", "price", "kitna", "kitni", "kitne", "paisa", "paise", "rate",
             "rupees", "rs", "₹", "फीस", "कितना", "कितनी"],
}


def hours_text(s: dict) -> str:
    sessions = " and ".join(f"{spoken_time(a)} to {spoken_time(b)}" for a, b in s["sessions"])
    closed = [DAY_NAMES[i] for i in sorted(s.get("closed_weekdays", []))]
    text = f"Open {sessions}"
    return text + (f". Closed on {', '.join(closed)}." if closed else ", all days.")


def upcoming_changes(conn: sqlite3.Connection, s: dict, days: int = 7) -> list[str]:
    today = config.now().date()
    out = []
    for b in bk.list_blocks(conn, today):
        d = date.fromisoformat(b["date"])
        if d > today + timedelta(days=days):
            continue
        who = cs.doctor_name(s, b["resource_id"]) if b["resource_id"] else "The whole clinic"
        when = short_date(d)
        if b["kind"] in ("leave", "holiday"):
            out.append(f"{who}: not available on {when}.")
        elif b["kind"] == "late_start":
            out.append(f"{who}: available from {spoken_time(b['end'])} on {when}.")
        elif b["kind"] == "early_close":
            out.append(f"{who}: available until {spoken_time(b['start'])} on {when}.")
    return out


def facts(conn: sqlite3.Connection, s: dict) -> dict[str, str]:
    """Every approved fact, keyed by topic. FAQs are keyed faq:<n>."""
    location = f"{s['name']}, {s['address']}" + (f", near {s['landmark']}" if s.get("landmark") else "") + "."
    out = {
        "hours": hours_text(s) + " " + " ".join(upcoming_changes(conn, s)),
        "location": location,
        "doctors": "Doctors: " + ", ".join(d["name"] for d in s["doctors"]) + ".",
        "fees": "Fees: " + "; ".join(f"{x['name']} {x['fee']}" for x in s["services"]) + ". Final cost depends on the doctor's check-up.",
    }
    for i, f in enumerate(s.get("faqs", [])):
        out[f"faq:{i}"] = f"Q: {f['q']} A: {f['a']}"
    return {k: v.strip() for k, v in out.items()}


def _words(text: str) -> set[str]:
    return {w for w in re.split(r"[^\wऀ-ॿ₹]+", text.lower()) if len(w) > 1 or w == "₹"}


def lookup(conn: sqlite3.Connection, s: dict, question: str) -> list[str]:
    """Approved facts matching the question, best first. Empty means 'not known'."""
    q = _words(question)
    all_facts = facts(conn, s)
    scored = []
    for key, text in all_facts.items():
        if key.startswith("faq:"):
            idx = int(key[4:])
            faq_words = _words(s["faqs"][idx]["q"])
            score = len(q & faq_words) * 2
        else:
            score = len(q & set(TOPIC_WORDS[key])) * 2
            if key == "fees":
                score += sum(2 for x in s["services"] if _words(x["name"]) & q)
            if key == "doctors":
                score += sum(2 for d in s["doctors"] if _words(d["name"]) & q)
        if score:
            scored.append((score, text))
    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored[:3]]

"""Business-approved answers (C3). Built live from settings; nothing here is invented. Each
business gets only the topics its settings have: doctors and fees for a clinic, minimum order
and delivery for a wholesaler (whose rates come from the catalogue tools, never from here)."""

import re
from datetime import date, timedelta

from ..booking import service as bk
from ..booking.when import short_date, spoken_time
from ..core import config, db
from ..core import settings as cs

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

TOPIC_WORDS = {
    "hours": [
        "time",
        "timing",
        "timings",
        "open",
        "close",
        "closed",
        "khula",
        "khulta",
        "band",
        "kab",
        "hours",
        "sunday",
        "ravivar",
        "itvar",
        "samay",
        "baje",
        "chhutti",
        "holiday",
        "leave",
        "खुला",
        "बंद",
        "कब",
    ],
    "location": [
        "where",
        "address",
        "location",
        "kahan",
        "kidhar",
        "pata",
        "landmark",
        "rasta",
        "map",
        "कहाँ",
        "कहां",
        "पता",
    ],
    "doctors": ["doctor", "doctors", "dr", "daktar", "dentist", "kaun", "डॉक्टर"],
    "ordering": [
        "minimum",
        "min",
        "delivery",
        "deliver",
        "deliveries",
        "area",
        "bhejte",
        "bhejoge",
        "pahuncha",
        "order",
        "orders",
        "dispatch",
        "डिलीवरी",
    ],
    "fees": [
        "fee",
        "fees",
        "charge",
        "charges",
        "cost",
        "price",
        "kitna",
        "kitni",
        "kitne",
        "paisa",
        "paise",
        "rate",
        "rupees",
        "rs",
        "₹",
        "फीस",
        "कितना",
        "कितनी",
    ],
}


def hours_text(s: dict) -> str:
    sessions = " and ".join(f"{spoken_time(a)} to {spoken_time(b)}" for a, b in s["sessions"])
    closed = [DAY_NAMES[i] for i in sorted(s.get("closed_weekdays", []))]
    text = f"Open {sessions}"
    return text + (f". Closed on {', '.join(closed)}." if closed else ", all days.")


def upcoming_changes(conn: db.Conn, s: dict, days: int = 7) -> list[str]:
    today = config.now().date()
    out = []
    for b in bk.list_blocks(conn, today):
        d = date.fromisoformat(b["date"])
        if d > today + timedelta(days=days):
            continue
        who = cs.doctor_name(s, b["resource_id"]) if b["resource_id"] else "The whole business"
        when = short_date(d)
        if b["kind"] in ("leave", "holiday"):
            out.append(f"{who}: not available on {when}.")
        elif b["kind"] == "late_start":
            out.append(f"{who}: available from {spoken_time(b['end'])} on {when}.")
        elif b["kind"] == "early_close":
            out.append(f"{who}: available until {spoken_time(b['start'])} on {when}.")
    return out


def facts(conn: db.Conn, s: dict) -> dict[str, str]:
    """Every approved fact, keyed by topic. FAQs are keyed faq:<n>."""
    location = (
        f"{s['name']}, {s['address']}"
        + (f", near {s['landmark']}" if s.get("landmark") else "")
        + "."
    )
    out = {
        "hours": hours_text(s) + " " + " ".join(upcoming_changes(conn, s)),
        "location": location,
    }
    if s.get("doctors"):
        out["doctors"] = "Doctors: " + ", ".join(d["name"] for d in s["doctors"]) + "."
    if s.get("services"):
        out["fees"] = (
            "Fees: "
            + "; ".join(f"{x['name']} {x['fee']}" for x in s["services"])
            + ". Final cost depends on the doctor's check-up."
        )
    ordering = [
        f"Minimum order: {s['min_order']}." if s.get("min_order") else "",
        f"Delivery area: {s['delivery_area']}." if s.get("delivery_area") else "",
    ]
    if any(ordering):
        out["ordering"] = " ".join(x for x in ordering if x)
    for i, f in enumerate(s.get("faqs", [])):
        out[f"faq:{i}"] = f"Q: {f['q']} A: {f['a']}"
    return {k: v.strip() for k, v in out.items()}


# Filler words that would make every FAQ look like a match ("... hai?").
STOP = {
    "hai",
    "hain",
    "kya",
    "ko",
    "ka",
    "ki",
    "ke",
    "se",
    "mein",
    "me",
    "aur",
    "ya",
    "to",
    "toh",
    "bhi",
    "the",
    "is",
    "are",
    "a",
    "an",
    "do",
    "does",
    "can",
    "i",
    "you",
    "your",
    "what",
    "how",
    "chahiye",
    "hoga",
    "hogi",
    "ji",
    "है",
    "क्या",
    "का",
    "की",
    "के",
    "में",
    "से",
}


def _words(text: str) -> set[str]:
    return {
        w
        for w in re.split(r"[^\wऀ-ॿ₹]+", text.lower())
        if (len(w) > 1 or w == "₹") and w not in STOP
    }


def lookup(conn: db.Conn, s: dict, question: str) -> list[str]:
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
                score += sum(2 for x in s.get("services", []) if _words(x["name"]) & q)
            if key == "doctors":
                score += sum(2 for d in s.get("doctors", []) if _words(d["name"]) & q)
        if score:
            scored.append((score, text))
    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored[:3]]

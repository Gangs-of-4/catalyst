"""Doctor commands on WhatsApp (C8): parse -> preview -> "Haan" -> apply. Rule-based, with an optional LLM fallback.

Every write is previewed and stored as a pending action per sender (ADR-0034). Reads answer at once.
"""
import json
import re
import sqlite3
from datetime import date, datetime, timedelta

from pydantic import BaseModel, ValidationError, field_validator

from ... import inbox
from ...booking import service as bk
from ...booking.when import parse_date, parse_time, short_date, spoken_time
from ...core import config, db
from ...core import phone as ph
from ...core import settings as cs
from ...providers.llm import groq
from . import summary

READ_INTENTS = ("help", "query_day", "callbacks", "summary")
WRITE_INTENTS = ("block_day", "late_start", "early_close", "set_fee", "walk_in")


class Command(BaseModel):
    """One parsed command. The same schema validates rule and LLM output."""
    intent: str
    date: str | None = None
    doctor_id: str | None = None
    time: str | None = None
    service: str | None = None
    fee: int | None = None
    name: str | None = None
    phone: str | None = None

    @field_validator("intent")
    @classmethod
    def _intent(cls, v: str) -> str:
        if v not in READ_INTENTS + WRITE_INTENTS:
            raise ValueError("unknown intent")
        return v

    @field_validator("date")
    @classmethod
    def _date(cls, v):
        if v is not None:
            date.fromisoformat(v)
        return v

    @field_validator("time")
    @classmethod
    def _time(cls, v):
        if v is not None and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
            raise ValueError("time must be HH:MM")
        return v


def _words(t: str, *options: str) -> bool:
    return any(re.search(r"(?<![\wऀ-ॿ])" + re.escape(o) + r"(?![\wऀ-ॿ])", t) for o in options)


LEAVE = ("chhutti", "chutti", "chuti", "chhuti", "leave", "holiday", "off", "band", "absent", "छुट्टी", "बंद",
         "nahi aayenge", "nahi aayengi", "nahi aaungi", "nahi aaunga", "nahi aayega", "nahi aayegi", "nahin aayengi",
         "nahin aayenge", "not coming", "won't come", "nahi aa paungi", "nahi aa paunga")
QUERY = ("appointments", "appointment", "schedule", "bookings", "booking", "patients", "list")
CONFIRM = ("haan", "ha", "haa", "han", "yes", "y", "ok", "okay", "theek", "theek hai", "sahi", "sahi hai", "हाँ", "हां", "confirm")
REJECT = ("nahi", "nahin", "na", "no", "n", "mat", "cancel", "नहीं")


def _doctor_in(s: dict, t: str) -> dict | None:
    """A doctor named in the text: 'Dr Asha', 'Asha ji', 'Verma madam', 'Doctor B'."""
    m = re.search(r"\b(?:dr\.?|doctor)\s+([a-z]+)", t)
    if m:
        doc = cs.match_doctor(s, m[0])
        if doc:
            return doc
    for d in s["doctors"]:
        for part in d["name"].lower().replace("dr.", "").split():
            if len(part) > 2 and _words(t, part):
                return d
    return None


def parse_rules(text: str, s: dict, today: date) -> Command | None:
    t = " ".join(text.lower().split())
    if _words(t, "help", "madad", "commands", "menu") or t in ("?", "hi", "hello", "namaste"):
        return Command(intent="help")
    if _words(t, "summary", "report", "hisaab", "hisab"):
        return Command(intent="summary")
    if _words(t, "callback", "callbacks", "call back", "pending"):
        return Command(intent="callbacks")

    phone_m = re.search(r"(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}", t)
    if re.search(r"walk[\s-]?in", t):
        if not phone_m:
            return None
        before = t[re.search(r"walk[\s-]?in", t).end():phone_m.start()]
        name = " ".join(w.capitalize() for w in re.findall(r"[a-zऀ-ॿ]+", before) if w not in ("ka", "ki", "ke", "naam", "name"))
        rest = t[phone_m.end():]
        d = parse_date(rest, today) or today
        tm = parse_time(re.sub(r"\b(?:dr\.?|doctor)\s+[a-z]+", " ", rest))
        doc = _doctor_in(s, rest)
        if not name or not tm:
            return None
        return Command(intent="walk_in", name=name, phone=ph.normalize(phone_m[0]), date=d.isoformat(), time=tm,
                       doctor_id=doc["id"] if doc else None)

    fee_m = re.search(r"(.*?)\b(?:fee|fees|fees?\s+ab|charge)\b\s*(?:ab|ko|=|:|kar\s+do|is)?\s*(?:₹|rs\.?|rupees?)?\s*(\d{2,6})", t)
    if fee_m:
        wanted = fee_m[1].strip() or "consultation"
        svc = next((x for x in s["services"] if wanted in x["name"].lower() or x["name"].lower() in wanted), None)
        svc = svc or next((x for x in s["services"] if any(w in x["name"].lower() for w in wanted.split() if len(w) > 3)), None)
        if not svc:
            return None
        return Command(intent="set_fee", service=svc["name"], fee=int(fee_m[2]))

    d = parse_date(t, today)
    doc = _doctor_in(s, t)
    if _words(t, *QUERY) and not _words(t, *LEAVE):
        return Command(intent="query_day", date=(d or today).isoformat())

    t_no_doc = re.sub(r"\b(?:dr\.?|doctor)\s+[a-z]+", " ", t)
    # Strip "28/10" and "28 oct" so the date's number isn't read as the hour.
    no_dates = re.sub(r"\b\d{1,2}[/-]\d{1,2}\b|\b\d{1,2}\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b",
                      " ", t_no_doc)
    tm = parse_time(no_dates) if re.search(r"\d|baje|बजे", no_dates) else None
    if tm and _words(t, "se", "from", "after", "baad", "से"):
        return Command(intent="late_start", date=(d or today).isoformat(), time=tm, doctor_id=doc["id"] if doc else None)
    if tm and _words(t, "tak", "till", "until", "upto", "तक"):
        return Command(intent="early_close", date=(d or today).isoformat(), time=tm, doctor_id=doc["id"] if doc else None)
    if _words(t, *LEAVE) and d:
        return Command(intent="block_day", date=d.isoformat(), doctor_id=doc["id"] if doc else None)
    return None


def parse_llm(text: str, s: dict, today: date) -> Command | None:
    """Fail closed: anything that isn't a valid known command returns None."""
    if not config.env("GROQ_API_KEY"):
        return None
    template = (config.VERTICAL_DIR / "whatsapp-parse-prompt.md").read_text(encoding="utf-8").split("\n---\n", 1)[-1]
    system = (template.replace("{today}", f"{today.isoformat()} ({today:%A})")
              .replace("{doctors}", ", ".join(f"{d['id']}: {d['name']}" for d in s["doctors"]))
              .replace("{services}", ", ".join(x["name"] for x in s["services"])))
    raw = groq.complete_json(system, text)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("intent") in (None, "unknown"):
            return None
        cmd = Command.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        return None
    if cmd.doctor_id and not cs.doctor(s, cmd.doctor_id):
        return None
    if cmd.intent in ("block_day", "late_start", "early_close", "walk_in", "query_day") and not cmd.date:
        return None
    if cmd.intent in ("late_start", "early_close", "walk_in") and not cmd.time:
        return None
    if cmd.intent == "set_fee" and (not cmd.fee or not any(x["name"] == cmd.service for x in s["services"])):
        return None
    if cmd.intent == "walk_in" and not (cmd.name and ph.normalize(cmd.phone)):
        return None
    return cmd


# ---------- wording ----------

def day_word(d: date, today: date) -> str:
    rel = {0: "aaj", 1: "kal", 2: "parso"}.get((d - today).days)
    return f"{rel} ({short_date(d)})" if rel else short_date(d)


def who(s: dict, doctor_id: str | None) -> str:
    return cs.doctor_name(s, doctor_id) if doctor_id else "Poori clinic"


HELP = ("Commands:\n"
        "• aaj / kal ke appointments\n"
        "• callbacks\n"
        "• summary\n"
        "• kal chhutti  |  Dr Asha kal nahi aayengi\n"
        "• aaj 11 baje se  |  aaj 6 baje tak\n"
        "• consultation fee 400\n"
        "• walk-in Ramesh 9876543210 aaj 5 baje\n"
        "Har badlav pehle preview hoga; 'Haan' bhejne par hi lagega.")


def preview(conn: sqlite3.Connection, s: dict, cmd: Command, today: date) -> str | None:
    """The preview text for a write, or None if it can't be applied (with the reason in an error string)."""
    if cmd.intent == "set_fee":
        old = next(x["fee"] for x in s["services"] if x["name"] == cmd.service)
        return f"{cmd.service} fee: {old} → ₹{cmd.fee}. Sahi hai? Haan/Nahi"
    d = date.fromisoformat(cmd.date)
    if d < today:
        return None
    if cmd.intent == "walk_in":
        doc = cs.doctor(s, cmd.doctor_id) if cmd.doctor_id else _free_doctor(conn, s, d, cmd.time)
        name = doc["name"] if doc else "koi bhi free doctor"
        return f"Walk-in: {cmd.name}, {ph.spoken(cmd.phone)} — {day_word(d, today)}, {spoken_time(cmd.time)}, {name}. Sahi hai? Haan/Nahi"
    start, end = _block_range(cmd)
    affected = bk.affected_bookings(conn, s, d, cmd.doctor_id, start, end)
    if cmd.intent == "block_day":
        line = f"{who(s, cmd.doctor_id)} — {day_word(d, today)} chhutti. Us din ke slots band."
    elif cmd.intent == "late_start":
        line = f"{who(s, cmd.doctor_id)} — {day_word(d, today)} {spoken_time(cmd.time)} se available. Usse pehle ke slots band."
    else:
        line = f"{who(s, cmd.doctor_id)} — {day_word(d, today)} {spoken_time(cmd.time)} tak available. Uske baad ke slots band."
    if affected:
        line += f"\n{len(affected)} booked patient(s) is time mein hain — unhe callback list mein daal dungi taaki staff time badal sake."
    return line + "\nSahi hai? Haan/Nahi"


def _block_range(cmd: Command) -> tuple[str | None, str | None]:
    if cmd.intent == "late_start":
        return "00:00", cmd.time
    if cmd.intent == "early_close":
        return cmd.time, "23:59"
    return None, None


def _free_doctor(conn: sqlite3.Connection, s: dict, d: date, time: str) -> dict | None:
    free = [sl for sl in bk.free_slots(conn, s, d) if sl.time == time]
    return cs.doctor(s, free[0].resource_id) if free else None


def apply(conn: sqlite3.Connection, s: dict, cmd: Command) -> str:
    """Apply a confirmed write. Returns the reply text."""
    if cmd.intent == "set_fee":
        for x in s["services"]:
            if x["name"] == cmd.service:
                x["fee"] = f"₹{cmd.fee}"
        cs.save(conn, s)
        return f"Done ✅ {cmd.service} fee ab ₹{cmd.fee}. Agent ko bhi bata diya hai."
    d = date.fromisoformat(cmd.date)
    if cmd.intent == "walk_in":
        doc = cs.doctor(s, cmd.doctor_id) if cmd.doctor_id else _free_doctor(conn, s, d, cmd.time)
        if not doc:
            return "Yeh slot ab free nahi hai. 'kal ke appointments' bhej kar free time dekhein."
        try:
            bk.book(conn, s, doc["id"], d, cmd.time, cmd.name, cmd.phone, "whatsapp")
        except bk.BookingError as e:
            alt = ", ".join(f"{spoken_time(a.time)} {cs.doctor_name(s, a.resource_id)}" for a in e.alternatives[:3])
            return "Yeh slot free nahi hai." + (f" Free: {alt}." if alt else "")
        return f"Done ✅ {cmd.name} — {short_date(d)}, {spoken_time(cmd.time)}, {doc['name']}. Desk par dikh raha hai."
    start, end = _block_range(cmd)
    affected = bk.affected_bookings(conn, s, d, cmd.doctor_id, start, end)
    kind = {"block_day": "holiday" if not cmd.doctor_id else "leave"}.get(cmd.intent, cmd.intent)
    bk.add_block(conn, d, kind, "whatsapp", cmd.doctor_id, start, end)
    for b in affected:
        inbox.create(conn, "callback", name=b["name"], phone=b["phone"], reason="other",
                     note=f"Booking {short_date(d)} {spoken_time(b['time'])} affected by schedule change; offer a new time.")
    extra = f" {len(affected)} patient(s) callback list mein." if affected else ""
    return f"Done ✅ Live hai.{extra}"


def answer_read(conn: sqlite3.Connection, s: dict, cmd: Command, today: date) -> str:
    if cmd.intent == "help":
        return HELP
    if cmd.intent == "summary":
        return summary.summary_text(s["name"], today, summary.day_stats(conn, today))
    if cmd.intent == "callbacks":
        items = inbox.open_items(conn)
        if not items:
            return "Koi pending callback nahi hai."
        lines = [f"Pending ({len(items)}):"]
        for it in items[:10]:
            mark = "🔴 " if it["urgent"] else "• "
            lines.append(f"{mark}{it['name'] or 'No name'} {ph.spoken(it['phone'])} — {(it['note'] or it['reason'] or '')[:80]}")
        return "\n".join(lines)
    d = date.fromisoformat(cmd.date)
    rows = conn.execute(
        "SELECT * FROM bookings WHERE date = ? AND status != 'cancelled' ORDER BY time", (d.isoformat(),)
    ).fetchall()
    word = day_word(d, today)
    head = f"{word[0].upper()}{word[1:]} ke appointments ({len(rows)}):"
    if bk.is_closed(s, d):
        head += " (clinic band)"
    lines = [head]
    for doc in s["doctors"]:
        mine = [r for r in rows if r["resource_id"] == doc["id"]]
        listing = "; ".join(f"{spoken_time(r['time'])} {r['name']}" + ("" if r["status"] == "booked" else f" ({r['status']})")
                            for r in mine) or "koi nahi"
        lines.append(f"{doc['name']}: {listing}")
    for b in bk.blocks_on(conn, d):
        lines.append(f"⛔ {who(s, b['resource_id'])}: {b['kind'].replace('_', ' ')}" + (f" {b['start']}–{b['end']}" if b["start"] else ""))
    pending = len(inbox.open_items(conn))
    lines.append(f"Pending callbacks: {pending}")
    return "\n".join(lines)


# ---------- conversation state ----------

def save_pending(conn: sqlite3.Connection, sender: str, cmd: Command) -> None:
    with conn:
        conn.execute(
            "INSERT INTO pending_actions (sender, action, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(sender) DO UPDATE SET action = excluded.action, created_at = excluded.created_at",
            (sender, cmd.model_dump_json(), db.stamp()),
        )


def take_pending(conn: sqlite3.Connection, s: dict, sender: str) -> Command | None:
    row = conn.execute("SELECT * FROM pending_actions WHERE sender = ?", (sender,)).fetchone()
    with conn:
        conn.execute("DELETE FROM pending_actions WHERE sender = ?", (sender,))
    if not row:
        return None
    age = config.now() - datetime.fromisoformat(row["created_at"])
    if age > timedelta(minutes=int(s.get("preview_expiry_min", 30))):
        return None
    return Command.model_validate_json(row["action"])


def has_pending(conn: sqlite3.Connection, sender: str) -> bool:
    return conn.execute("SELECT 1 FROM pending_actions WHERE sender = ?", (sender,)).fetchone() is not None


def handle(conn: sqlite3.Connection, sender: str, text: str) -> tuple[str, bool]:
    """Reply to one message from an allowed sender. Returns (reply, settings_changed)."""
    s = cs.load(conn)
    today = config.now().date()
    t = " ".join(text.lower().strip(" .!?।").split())
    if has_pending(conn, sender) and (t in CONFIRM or t in REJECT):
        cmd = take_pending(conn, s, sender)
        if cmd is None:
            return "Woh preview purana ho gaya. Command dobara bhejein.", False
        if t in REJECT:
            return "Theek hai, kuch nahi badla.", False
        return apply(conn, s, cmd), cmd.intent != "walk_in"
    if t in CONFIRM or t in REJECT:
        return "Abhi koi badlav pending nahi hai. 'help' bhejein.", False

    cmd = parse_rules(text, s, today) or parse_llm(text, s, today)
    if cmd is None:
        # The message text goes to the inbox (DB) so our team can act on it the same day; never to logs.
        inbox.create(conn, "ops", phone=sender, reason="whatsapp_unparsed", note=f"WhatsApp: {text[:300]}")
        return "Samajh nahi aaya — team dekh legi.", False
    if cmd.intent in READ_INTENTS:
        return answer_read(conn, s, cmd, today), False
    text_preview = preview(conn, s, cmd, today)
    if text_preview is None:
        return "Yeh date nikal chuki hai. Aaj ya aage ki date bhejein.", False
    save_pending(conn, sender, cmd)
    return text_preview, False

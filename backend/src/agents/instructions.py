"""Owner custom instructions (Phase 2 M5; contracts.md §3.1, §4, §6.1).

The owner's words are screened line by line before they can reach the agent: a line that asks for
medical advice, quotes prices, pretends to be human, collects ID or bank details, or tries to change
the agent's rules is rejected with a reason, and the rest is saved. Every save is a new version, and
undo brings the previous one back. The prompt puts the accepted text in a fenced section *after*
the locked rules, with a line saying it can never override them (agents/prompt.py).

Rule-based only. An LLM screen was planned as a second pass and is the first thing in the cut
order (phase2-plan.md); the rules below are the guarantee.
"""

import json
import re
from dataclasses import dataclass, field

from ..core import db

MAX_CHARS = 500
ABBREVIATIONS = {
    "dr",
    "mr",
    "mrs",
    "ms",
    "smt",
    "shri",
    "st",
    "no",
    "nr",
    "opp",
    "vs",
    "etc",
    "rs",
    "approx",
}
FENCE = re.compile(r"`{3,}|<<<|>>>|OWNER_INSTRUCTIONS", re.I)

_B = r"(?<![\wऀ-ॿ])"
_E = r"(?![\wऀ-ॿ])"


def _any(*words: str) -> str:
    """A whole-word alternation (word edges work for Devanagari too)."""
    return _B + "(?:" + "|".join(words) + ")" + _E


def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.I)


# Word lists for the checks below. A line is refused when the words of one kind appear *anywhere*
# in it, in any order: "paracetamol lene ko kaho" and "kaho paracetamol le lo" are the same advice.
MEDICINE = _any(
    r"dawai\w*",
    r"dawa",
    r"dawaa\w*",
    r"medicines?",
    r"medication",
    r"tablets?",
    r"goli(?:yan)?",
    r"capsules?",
    r"syrups?",
    r"painkillers?",
    r"antibiotics?",
    r"ointments?",
    r"creams?",
    r"drops",
    r"injections?",
    r"gel",
    r"paracetamol",
    r"ibuprofen",
    r"amoxicillin",
    r"crocin",
    r"dolo",
    r"combiflam",
    r"calpol",
    r"disprin",
    r"aspirin",
    r"brufen",
    r"zerodol",
    r"azithromycin",
    r"augmentin",
    r"metronidazole",
    r"diclofenac",
    r"cetirizine",
    r"दवा\w*",
    r"गोली",
    r"टैबलेट",
)
ADVICE = _any(
    r"lene ko",
    r"lena",
    r"lein",
    r"le lo",
    r"lelo",
    r"lijiye",
    r"le lijiye",
    r"lo",
    r"de do",
    r"dedo",
    r"dena",
    r"dijiye",
    r"de dijiye",
    r"khane ko",
    r"khana",
    r"khao",
    r"khaiye",
    r"kha lo",
    r"pilao",
    r"pila do",
    r"lagao",
    r"lagana",
    r"lagaiye",
    r"suggest\w*",
    r"recommend\w*",
    r"prescrib\w*",
    r"take",
    r"give",
    r"use",
    r"try",
    r"bata\w*",
    r"bol\w*",
    r"kah\w*",
    r"keh\w*",
    r"लीजिए",
    r"खाइए",
    r"दीजिए",
    r"बताइए",
)
SYMPTOM = _any(
    r"dard",
    r"pain",
    r"toothache",
    r"headache",
    r"bukhar",
    r"fever",
    r"sujan",
    r"swelling",
    r"infection",
    r"khoon",
    r"bleeding",
    r"sardi",
    r"zukaam",
    r"cold",
    r"khansi",
    r"cough",
    r"acidity",
    r"allergy",
    r"दर्द",
    r"बुखार",
    r"सूजन",
)
DOSE = _rx(
    _any(
        r"dose",
        r"dosage",
        r"diagnos\w*",
        r"prescription",
        r"side effects?",
        r"substitute",
        r"ilaaj",
        r"treatment",
        r"home remed\w*",
        r"gharelu nuskh\w*",
    )
    + r"|\d+\s*(?:mg|ml|mcg)"
    + _E
)
SUBSTITUTE = _rx(
    _any(r"jagah", r"badle", r"badale", r"instead")
    + r".{0,40}"
    + MEDICINE
    + "|"
    + MEDICINE
    + r".{0,40}"
    + _any(r"jagah", r"badle", r"badale", r"instead")
)
_MEDICINE, _ADVICE, _SYMPTOM = _rx(MEDICINE), _rx(ADVICE), _rx(SYMPTOM)
_TAKE_FOR = _rx(_any(r"lene ko", r"khane ko", r"lagane ko", r"pine ko", r"peene ko", r"take"))


def _medical(line: str) -> bool:
    if DOSE.search(line) or SUBSTITUTE.search(line):
        return True
    if _MEDICINE.search(line) and (_ADVICE.search(line) or _SYMPTOM.search(line)):
        return True
    return bool(_SYMPTOM.search(line) and _TAKE_FOR.search(line))


# Fees and offers: any amount of money, a percentage off, or an offer word. No word-edge guards
# around the money itself: "₹300", "Rs300", "20%" are all glued to their digits.
PRICE = _rx(
    r"₹\s*\d|\d\s*₹|(?<![a-z])rs\.?\s*\d|\d\s*(?:rs\b|rs\.|/-|rupe|rupaye)|(?<![a-z])rupe\w*\s*\d"
    r"|\d+\s*%|percent\s+off|"
    + _any(r"discount\w*", r"chhoot", r"chhut", r"offers?", r"muft", r"scheme", r"cashback")
    + r"|"
    + _any(r"free")
    + r"\s+(?:consultation|checkup|check-up|delivery|mein|me)"
    + r"|"
    + _any(r"rate", r"price", r"daam", r"bhav", r"fees?", r"charges?", r"cost", r"kharcha")
    + r".{0,25}(?:\d|kam|badha|zyada|sasta|mehenga|batao|bata do|bolo|quote)"
    + r"|\d{2,}(?:\.\d+)?\s*(?:ki|ka|ke)\s+(?:hai|hain|padegi|padega|lagegi|lagega|lagti|lagta)\b"
    + r"|\d{2,}\s*(?:lagenge|lagega|lagegi|padenge|padega|padegi)\b"
)

# Pretending to be a person, or hiding that it is automated.
AUTOMATED = _any(
    r"ai",
    r"a\.i\.",
    r"bot",
    r"chatbot",
    r"robot",
    r"computer",
    r"automated",
    r"machine",
    r"artificial",
    r"assistant",
)
DENY = _any(
    r"never",
    r"don'?t",
    r"do not",
    r"mat",
    r"nahi",
    r"nahin",
    r"na",
    r"hide",
    r"chhupa\w*",
    r"chupa\w*",
)
TELL = _any(
    r"reveal",
    r"say",
    r"tell",
    r"admit",
    r"mention",
    r"disclose",
    r"bata\w*",
    r"bol\w*",
    r"keh\w*",
    r"kah\w*",
)
PERSON = _rx(
    _any(
        r"insaan",
        r"human",
        r"real person",
        r"asli (?:aadmi|insaan)",
        r"ladki ho",
        r"ladka ho",
        r"a person",
        r"real receptionist",
        r"staff member",
    )
    + r"|"
    + _any(r"you are", r"you're", r"tum", r"aap", r"main")
    + r"\s+(?:\S+\s+){0,4}?"
    + _any(r"receptionist", r"staff", r"insaan", r"person", r"human")
    + r"|"
    + _any(
        r"your name is",
        r"call yourself",
        r"introduce yourself as",
        r"apna naam",
        r"tumhara naam",
        r"aapka naam",
    )
)
_AUTOMATED, _DENY, _TELL = _rx(AUTOMATED), _rx(DENY), _rx(TELL)


def _impersonates(line: str) -> bool:
    if PERSON.search(line):
        return True
    return bool(_AUTOMATED.search(line) and _DENY.search(line) and _TELL.search(line))


def _matches(pattern: re.Pattern):
    return lambda line: bool(pattern.search(line))


# (check, reason). The reason is shown to the owner as-is. First match wins.
RULES: list[tuple] = [
    (
        _matches(
            _rx(
                _any(
                    r"ignore",
                    r"bhool jao",
                    r"bhul jao",
                    r"forget",
                    r"override",
                    r"jailbreak",
                    r"developer mode",
                    r"system prompt",
                    r"previous instructions",
                    r"upar ki (?:baat|baatein|instructions)",
                    r"rules? (?:mat mano|todo|tod do|ignore)",
                    r"niyam (?:mat mano|todo)",
                    r"act as",
                    r"you are now",
                    r"pretend",
                    r"role ?play",
                )
            )
        ),
        "Instructions can't change the agent's rules.",
    ),
    (_medical, "The agent never gives medical advice; such questions go to a person."),
    (_impersonates, "The agent always says honestly that it is automated."),
    (
        _matches(
            _rx(
                _any(
                    r"aadhaa?r",
                    r"adhaar",
                    r"otp",
                    r"pan card",
                    r"bank (?:account|details?|khata)",
                    r"account (?:number|no)",
                    r"card (?:number|no)",
                    r"cvv",
                    r"upi pin",
                    r"password",
                    r"pin number",
                )
            )
        ),
        "The agent never asks for ID, bank, card or OTP details.",
    ),
    (
        _matches(PRICE),
        "Fees and offers come from your services list or catalogue, not instructions.",
    ),
    (
        _matches(
            _rx(
                _any(
                    r"108",
                    r"ambulance",
                    r"emergency",
                    r"escalat\w*",
                    r"doctor ko mat",
                    r"owner ko mat",
                    r"alert mat",
                    r"callback mat",
                    r"transfer mat",
                )
            )
        ),
        "Safety steps and escalation can't be changed.",
    ),
]


class TooLong(ValueError):
    pass


@dataclass
class Screened:
    accepted: list[str] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(self.accepted)


def lines(text: str) -> list[str]:
    """One instruction per line or sentence, with fence-like markers removed."""
    clean = FENCE.sub(" ", text or "")
    out: list[str] = []
    for para in re.split(r"[\r\n]+", clean):
        pieces = re.split(r"(?<=[.!?।])\s+", para)
        merged: list[str] = []
        for piece in pieces:  # "Dr. Asha" is one sentence: rejoin after a title or an initial
            last = merged[-1].split()[-1].lower() if merged and merged[-1].split() else ""
            if last.rstrip(".") in ABBREVIATIONS or re.fullmatch(r"[^\W\d_]\.", last):
                merged[-1] += " " + piece
            else:
                merged.append(piece)
        out += [" ".join(p.split()).strip(" -•*") for p in merged]
    return [p for p in out if p]


def screen(text: str) -> Screened:
    """Split and check every line. Raises TooLong over MAX_CHARS."""
    if len((text or "").strip()) > MAX_CHARS:
        raise TooLong(f"Keep the instructions under {MAX_CHARS} characters.")
    out = Screened()
    for line in lines(text):
        reason = next((r for check, r in RULES if check(line)), None)
        if reason:
            out.rejected.append({"line": line, "reason": reason})
        else:
            out.accepted.append(line)
    return out


def _row(r: db.Row) -> dict:
    return {
        "id": r["id"],
        "text": r["text"],
        "rejected": json.loads(r["rejected"] or "[]"),
        "source": r["source"],
        "active": bool(r["active"]),
        "created_at": r["created_at"],
    }


def migrate_pending(conn: db.Conn) -> int:
    """Startup, once per database: signups before M5 kept the owner's words unscreened in
    settings. Screen them into a version (inactive if every line was rejected, so the rejected
    lines are still on record) and drop the key, in one transaction per business. `conn` is
    unchecked: it runs over every business. Returns how many businesses were migrated."""
    done = 0
    for row in conn.execute("SELECT id, settings FROM tenants").fetchall():
        s = json.loads(row["settings"])
        if "pending_instructions" not in s:
            continue
        pending = str(s.pop("pending_instructions") or "")
        try:
            screened = screen(pending[:MAX_CHARS])
        except TooLong:  # cut to the limit above, so this can't happen; never block startup
            screened = Screened()
        scoped = conn.for_tenant(row["id"])
        with conn:
            if pending.strip():
                if screened.accepted:
                    scoped.execute(
                        "UPDATE instruction_versions SET active = 0"
                        " WHERE tenant_id = ? AND active = 1",
                        (row["id"],),
                    )
                scoped.execute(
                    "INSERT INTO instruction_versions (tenant_id, text, rejected, source, active,"
                    " replaces, created_at) VALUES (?, ?, ?, 'web', ?, NULL, ?)",
                    (
                        row["id"],
                        screened.text,
                        db.dumps(screened.rejected),
                        int(bool(screened.accepted)),
                        db.stamp(),
                    ),
                )
            conn.execute("UPDATE tenants SET settings = ? WHERE id = ?", (db.dumps(s), row["id"]))
        done += 1
    return done


def current(conn: db.Conn) -> dict | None:
    r = conn.execute(
        "SELECT * FROM instruction_versions WHERE tenant_id = ? AND active = 1", (conn.tid,)
    ).fetchone()
    return _row(r) if r else None


def active_text(conn: db.Conn) -> str:
    v = current(conn)
    return v["text"] if v else ""


def history(conn: db.Conn, limit: int = 10) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM instruction_versions WHERE tenant_id = ? ORDER BY id DESC LIMIT ?",
        (conn.tid, limit),
    ).fetchall()
    return [_row(r) for r in rows]


def _activate_new(conn: db.Conn, text: str, rejected: list[dict], source: str) -> int:
    """Make a new active version. It remembers the version it replaced, for undo. Two saves at
    the same moment (a web save and a WhatsApp "Haan") can collide on the one-active index:
    the loser retries once on top of the winner."""
    for attempt in range(2):
        try:
            with conn:
                before = conn.execute(
                    "SELECT id FROM instruction_versions WHERE tenant_id = ? AND active = 1",
                    (conn.tid,),
                ).fetchone()
                conn.execute(
                    "UPDATE instruction_versions SET active = 0 WHERE tenant_id = ? AND active = 1",
                    (conn.tid,),
                )
                row = conn.execute(
                    "INSERT INTO instruction_versions (tenant_id, text, rejected, source, active,"
                    " replaces, created_at) VALUES (?, ?, ?, ?, 1, ?, ?) RETURNING id",
                    (
                        conn.tid,
                        text,
                        db.dumps(rejected),
                        source,
                        before["id"] if before else None,
                        db.stamp(),
                    ),
                ).fetchone()
            return row["id"]
        except db.Conflict:
            conn.rollback()
            if attempt:
                raise
    raise AssertionError("unreachable")


def save(conn: db.Conn, text: str, source: str) -> tuple[int | None, Screened]:
    """Screen `text` and make its accepted lines the active instructions. Empty text clears them.
    If the owner wrote something and every line was rejected, nothing is saved (version None).
    Raises TooLong."""
    screened = screen(text)
    if (text or "").strip() and not screened.accepted:
        return None, screened
    return _activate_new(conn, screened.text, screened.rejected, source), screened


def _combined(conn: db.Conn, new_text: str) -> str:
    combined = "\n".join(x for x in (active_text(conn), new_text) if x)
    if len(combined) > MAX_CHARS:
        raise TooLong(
            f"Saari instructions mila kar {MAX_CHARS} characters se zyada ho jayengi. Settings "
            "page par purani kuch hata dijiye."
        )
    return combined


def add(conn: db.Conn, text: str) -> Screened:
    """For "agent ko bolo …": screen the new lines, and check they still fit with what is active
    now. Nothing is saved (the owner confirms first). Raises TooLong."""
    screened = screen(text)
    if screened.accepted:
        _combined(conn, screened.text)
    return screened


def append(conn: db.Conn, new_text: str, rejected: list[dict], source: str) -> int:
    """On "Haan": re-screen the new lines and add them to the text active *now*, so a web save
    or undo since the preview is kept, not overwritten. Raises TooLong."""
    again = screen(new_text)
    return _activate_new(conn, _combined(conn, again.text), rejected + again.rejected, source)


def undo(conn: db.Conn) -> dict | None:
    """Bring back the version that was active before the current one (not just the next-lower
    id: after undo, save, undo, the owner gets back what they saved over, never what they had
    undone). None if nothing is active."""
    now = conn.execute(
        "SELECT * FROM instruction_versions WHERE tenant_id = ? AND active = 1", (conn.tid,)
    ).fetchone()
    if now is None:
        return None
    prev = (
        conn.execute(
            "SELECT * FROM instruction_versions WHERE tenant_id = ? AND id = ?",
            (conn.tid, now["replaces"]),
        ).fetchone()
        if now["replaces"] is not None
        else None
    )
    with conn:
        conn.execute(
            "UPDATE instruction_versions SET active = 0 WHERE tenant_id = ? AND id = ?",
            (conn.tid, now["id"]),
        )
        if prev is not None:
            conn.execute(
                "UPDATE instruction_versions SET active = 1 WHERE tenant_id = ? AND id = ?",
                (conn.tid, prev["id"]),
            )
    return _row(prev) if prev is not None else {"id": None, "text": "", "rejected": []}


def for_prompt(conn: db.Conn) -> str:
    """The active text as it goes inside the prompt's fence: markers stripped, or "(none)"."""
    text = FENCE.sub(" ", active_text(conn)).strip()
    return text or "(none)"

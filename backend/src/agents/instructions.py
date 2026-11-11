"""Owner custom instructions (Phase 2 M5; contracts.md §3.1, §4, §6.1).

The owner's words are screened line by line before they can reach the agent: a line that asks for
medical advice, quotes prices, pretends to be human, collects ID or bank details, or tries to change
the agent's rules is rejected with a reason, and the rest is saved. Every save is a new version, and
undo brings the previous one back. The prompt puts the accepted text in a fenced section *after*
the locked rules, with a line saying it can never override them (agents/prompt.py).

Rule-based only. An LLM screen was planned as a second pass and is the first thing in the cut
order (phase2-plan.md); the rules below are the guarantee.
"""

import contextlib
import json
import re
from dataclasses import dataclass, field

from ..core import db
from ..core import settings as cs

MAX_CHARS = 500
ABBREVIATIONS = {"dr", "mr", "mrs", "ms", "smt", "shri", "st", "no", "nr", "opp", "vs", "etc"}
FENCE = re.compile(r"`{3,}|<<<|>>>|OWNER_INSTRUCTIONS", re.I)

_B = r"(?<![\wऀ-ॿ])"
_E = r"(?![\wऀ-ॿ])"

# (pattern, reason). The reason is shown to the owner as-is.
RULES: list[tuple[re.Pattern, str]] = [
    (
        re.compile(
            _B + r"(ignore|bhool jao|bhul jao|forget|override|jailbreak|developer mode|"
            r"system prompt|previous instructions|upar ki (baat|baatein|instructions)|"
            r"rules? (mat mano|todo|tod do|ignore)|niyam (mat mano|todo)|act as|you are now|"
            r"pretend|role ?play)" + _E,
            re.I,
        ),
        "Instructions can't change the agent's rules.",
    ),
    (
        re.compile(
            _B + r"(dose|dosage|\d+\s*(mg|ml|mcg)|diagnos\w*|prescri\w*|side effects?|substitute|"
            r"(jagah|badle|badale)\b.{0,40}(dawai|dawa|medicine|tablet|goli|syrup|capsule|brand)|"
            r"(dawai|dawa|medicine|tablet|goli|syrup|capsule|brand)s?\b.{0,40}(jagah|badle|badale)|"
            r"ilaaj|treatment|home remed\w*|gharelu nuskh\w*|"
            r"(dawai|dawa|medicine|tablet|goli|painkiller|antibiotic|syrup|ointment)s?\b.{0,40}"
            r"(bata|batao|suggest|recommend|de do|de dena|dijiye|lijiye|lena|lene|khaiye|take|give)|"
            r"(bata|batao|suggest|recommend)\w*\b.{0,40}(dawai|dawa|medicine|tablet|goli|painkiller|"
            r"antibiotic))" + _E,
            re.I,
        ),
        "The agent never gives medical advice; such questions go to a person.",
    ),
    (
        re.compile(
            _B + r"(insaan|human|real person|asli (aadmi|insaan)|ladki ho|ladka ho|"
            r"(bot|ai|robot|computer|automated)\b.{0,30}(mat|nahi|na) (batana|bolna|kehna)|"
            r"(mat|nahi|never) (batana|bolna|say|tell).{0,30}(bot|ai|robot|computer|automated))"
            + _E,
            re.I,
        ),
        "The agent always says honestly that it is automated.",
    ),
    (
        re.compile(
            _B + r"(aadhaar|aadhar|adhaar|otp|pan card|bank (account|details?|khata)|"
            r"account (number|no)|card (number|no)|"
            r"cvv|upi pin|password|pin number)" + _E,
            re.I,
        ),
        "The agent never asks for ID, bank, card or OTP details.",
    ),
    (
        re.compile(
            _B + r"(discount|chhoot|chhut|offer|% off|percent off|muft|scheme|₹|rs\.?\s*\d|"
            r"\d+\s*(rupe(e|y)s?|rupaye|rs)|free (consultation|checkup|check-up|delivery|mein)|"
            r"(rate|price|daam|bhav|fees?|charges?)\b.{0,25}(\d|kam|badha|zyada|sasta|mehenga|"
            r"batao|bata do|bolo|quote))" + _E,
            re.I,
        ),
        "Prices, fees and discounts come only from your settings or catalogue.",
    ),
    (
        re.compile(
            _B + r"(108|ambulance|emergency|escalat\w*|doctor ko mat|owner ko mat|alert mat|"
            r"callback mat|transfer mat)" + _E,
            re.I,
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
        reason = next((r for pattern, r in RULES if pattern.search(line)), None)
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


def _migrate_pending(conn: db.Conn) -> None:
    """Signups before M5 kept the owner's words unscreened in settings: screen them once."""
    s = cs.load(conn)
    pending = s.pop("pending_instructions", None)
    if pending is None:
        return
    if pending.strip():
        with contextlib.suppress(TooLong):  # length-checked at signup; never block a load on it
            save(conn, pending, "web")
    cs.save(conn, s)


def current(conn: db.Conn) -> dict | None:
    _migrate_pending(conn)
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
    with conn:
        conn.execute(
            "UPDATE instruction_versions SET active = 0 WHERE tenant_id = ? AND active = 1",
            (conn.tid,),
        )
        row = conn.execute(
            "INSERT INTO instruction_versions (tenant_id, text, rejected, source, active,"
            " created_at) VALUES (?, ?, ?, ?, 1, ?) RETURNING id",
            (conn.tid, text, db.dumps(rejected), source, db.stamp()),
        ).fetchone()
    return row["id"]


def save(conn: db.Conn, text: str, source: str) -> tuple[int | None, Screened]:
    """Screen `text` and make its accepted lines the active instructions. Empty text clears them.
    If the owner wrote something and every line was rejected, nothing is saved (version None).
    Raises TooLong."""
    screened = screen(text)
    if (text or "").strip() and not screened.accepted:
        return None, screened
    return _activate_new(conn, screened.text, screened.rejected, source), screened


def add(conn: db.Conn, text: str, source: str) -> tuple[str | None, Screened]:
    """For "agent ko bolo …": the active text plus the new accepted lines, unsaved (the owner
    confirms first). None when nothing new is accepted. Raises TooLong if the result is too long."""
    screened = screen(text)
    if not screened.accepted:
        return None, screened
    combined = "\n".join(x for x in (active_text(conn), screened.text) if x)
    if len(combined) > MAX_CHARS:
        raise TooLong(
            f"Saari instructions mila kar {MAX_CHARS} characters se zyada ho jayengi. Settings "
            "page par purani kuch hata dijiye."
        )
    return combined, screened


def save_screened(conn: db.Conn, text: str, rejected: list[dict], source: str) -> int:
    """Save text that was already screened (the WhatsApp preview), re-screening to be sure."""
    again = screen(text)
    return _activate_new(conn, again.text, rejected + again.rejected, source)


def undo(conn: db.Conn) -> dict | None:
    """Bring back the version before the active one. None if there is nothing to go back to."""
    now = current(conn)
    if now is None:
        return None
    prev = conn.execute(
        "SELECT * FROM instruction_versions WHERE tenant_id = ? AND id < ? ORDER BY id DESC"
        " LIMIT 1",
        (conn.tid, now["id"]),
    ).fetchone()
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

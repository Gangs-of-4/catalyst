"""Builds the system prompt and first message from verticals/clinic/agent-prompt.md plus a settings snapshot."""
import re
import sqlite3

from ..knowledge import answers
from ..verticals import loader

VOICE_FORMS = {
    "female": "Your voice is female: use feminine verb forms (कर रही हूँ, सकती हूँ, बताती हूँ).",
    "male": "Your voice is male: use masculine verb forms (कर रहा हूँ, सकता हूँ, बताता हूँ).",
}


def _fill(template: str, values: dict[str, str]) -> str:
    """Replace only the known {placeholders}; other braces in the prompt are left alone."""
    return re.sub(r"\{(\w+)\}", lambda m: values.get(m[1], m[0]), template)


def snapshot(conn: sqlite3.Connection, s: dict) -> str:
    f = answers.facts(conn, s)
    lines = [
        f"- Name: {s['name']}",
        f"- Address: {s['address']}" + (f" (landmark: {s['landmark']})" if s.get("landmark") else ""),
        f"- Timings: {f['hours']}",
        "- Doctors: " + ", ".join(d["name"] for d in s["doctors"]),
        "- Services and fees: " + "; ".join(f"{x['name']}: {x['fee']}" for x in s["services"])
        + ". Exact cost is decided by the doctor after a check-up.",
    ]
    lines += [f"- {x['q']} → {x['a']}" for x in s.get("faqs", [])]
    return "\n".join(lines)


def build(conn: sqlite3.Connection, s: dict) -> tuple[str, str]:
    """(system prompt, first message) for the clinic's current settings."""
    raw = loader.prompt_template()
    body, _, first = raw.partition("## First message")
    voice = s.get("voice", "female") if s.get("voice") in VOICE_FORMS else "female"
    values = {
        "tenant_name": s["name"],
        "clinic_snapshot": snapshot(conn, s),
        "emergency_instruction": s["emergency_instruction"],
        "voice_forms": VOICE_FORMS[voice],
        "example_doctor": s["doctors"][0]["name"] if s["doctors"] else "the doctor",
        "red_flags": "\n".join(f"  - {r}" for r in s.get("red_flags", [])) or "  - (none listed: treat anything worrying as grey zone)",
    }
    greetings = dict(line.split(":", 1) for line in first.strip().splitlines() if ":" in line)
    greeting = greetings.get(voice, next(iter(greetings.values()), "Namaste!")).strip()
    return _fill(body.strip(), values), _fill(greeting, values)

"""Outbound WhatsApp to the clinic's command numbers: urgent alerts, callbacks, summaries (C6, C10)."""
import sqlite3

from ...core import phone as ph
from ...core import settings as cs
from ...providers.messaging import twilio_whatsapp


def recipients(s: dict) -> list[str]:
    return [n for n in (ph.normalize(x) for x in s.get("whatsapp_numbers", [])) if n]


def broadcast(s: dict, body: str) -> int:
    """Send to every listed number. Returns how many sends succeeded."""
    return sum(twilio_whatsapp.send(n, body) for n in recipients(s))


def inbox_alert_text(item: dict) -> str:
    urgent = bool(item.get("urgent"))
    if item["kind"] == "escalation":
        head = "🔴 URGENT: patient call needs a doctor"
    elif urgent:
        head = "🔴 URGENT callback"
    else:
        head = "Callback requested"
    lines = (item.get("note") or item.get("reason") or "").strip().splitlines()
    summary = "\n".join(l.strip() for l in lines if l.strip())[:220]
    who = f"Name: {item.get('name') or 'not given'}  Phone: {ph.spoken(item.get('phone')) or 'not given'}"
    return f"{head}\n{who}\n{summary}\nDesk par 'Mark done' karein."


def alert_for_inbox(conn: sqlite3.Connection, item_id: int) -> int:
    row = conn.execute("SELECT * FROM inbox WHERE id = ?", (item_id,)).fetchone()
    if not row:
        return 0
    return broadcast(cs.load(conn), inbox_alert_text(dict(row)))

"""One row per call: flags raised by tools, outcome and report from the end-of-call message (C10)."""
import json
import sqlite3

from ..core import db
from ..safety import post_call

FLAGS = ("booked", "changed", "escalated", "callback")


def touch(conn: sqlite3.Connection, call_id: str) -> None:
    with conn:
        conn.execute("INSERT OR IGNORE INTO calls (id, started_at) VALUES (?, ?)", (call_id, db.stamp()))


def flag(conn: sqlite3.Connection, call_id: str | None, name: str) -> None:
    if not call_id or name not in FLAGS:
        return
    touch(conn, call_id)
    with conn:
        conn.execute(f"UPDATE calls SET {name} = {name} + 1 WHERE id = ?", (call_id,))


def outcome(row: sqlite3.Row | dict, user_spoke: bool) -> str:
    for name in ("escalated", "booked", "changed", "callback"):
        if row[name]:
            return name
    return "answered" if user_spoke else "hung_up"


def _transcript(message: dict) -> tuple[str, list[str], list[str]]:
    """Plain transcript plus assistant and user lines, from whichever fields Vapi sent."""
    artifact = message.get("artifact") or {}
    transcript = artifact.get("transcript") or message.get("transcript") or ""
    msgs = artifact.get("messages") or message.get("messages") or []
    assistant, user = [], []
    for m in msgs if isinstance(msgs, list) else []:
        if not isinstance(m, dict):
            continue
        role, text = m.get("role"), m.get("message") or m.get("content") or ""
        if role in ("assistant", "bot") and isinstance(text, str):
            assistant.append(text)
        elif role == "user" and isinstance(text, str):
            user.append(text)
    if not msgs and isinstance(transcript, str):
        for line in transcript.splitlines():
            head, _, text = line.partition(":")
            if head.strip().lower() in ("ai", "assistant", "bot"):
                assistant.append(text.strip())
            elif head.strip().lower() in ("user", "customer"):
                user.append(text.strip())
    return (transcript if isinstance(transcript, str) else json.dumps(transcript)), assistant, user


def end_of_call(conn: sqlite3.Connection, message: dict) -> str | None:
    call = message.get("call") or {}
    call_id = call.get("id")
    if not call_id:
        return None
    touch(conn, call_id)
    transcript, assistant_lines, user_lines = _transcript(message)
    artifact = message.get("artifact") or {}
    analysis = message.get("analysis") or {}
    hits = post_call.scan(assistant_lines)
    row = conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
    result = outcome(row, bool(user_lines) or "user:" in transcript.lower())
    with conn:
        conn.execute(
            "UPDATE calls SET ended_at = ?, outcome = ?, ended_reason = ?, summary = ?, transcript = ?,"
            " recording_url = ?, safety_review = ?, safety_hits = ? WHERE id = ?",
            (
                message.get("endedAt") or call.get("endedAt") or db.stamp(),
                result,
                message.get("endedReason") or call.get("endedReason"),
                analysis.get("summary") or message.get("summary"),
                transcript,
                artifact.get("recordingUrl") or message.get("recordingUrl"),
                int(bool(hits)),
                json.dumps(hits, ensure_ascii=False) if hits else None,
                call_id,
            ),
        )
        if message.get("startedAt"):
            conn.execute("UPDATE calls SET started_at = ? WHERE id = ?", (message["startedAt"], call_id))
    return result

"""Vapi assistant create/update over the REST API (no SDK). The only Vapi server code in the app.

Field names checked against the @vapi-ai/web 2.7.1 type definitions. VERIFY again if Vapi rejects a field.
"""
import secrets
import sqlite3

import httpx

from ...agents import prompt
from ...agents.tool_schemas import TOOLS
from ...core import settings as cs
from ...core.config import env, set_env

API = "https://api.vapi.ai"
# Azure Hindi neural voices; they read Devanagari Hindi and Latin English words. VERIFY on Vapi.
VOICES = {"female": "hi-IN-SwaraNeural", "male": "hi-IN-MadhurNeural"}
# Seconds Vapi waits for our webhook. A sleeping Render free-tier service takes about a minute to wake,
# so the default 20 s would fail the first tool call after idle. VERIFY the max (300) on Vapi.
SERVER_TIMEOUT_SECONDS = 90
FALLBACK_VOICE_HINT = (
    "If Vapi rejects the voice, set VAPI_VOICE_PROVIDER and VAPI_VOICE_ID in .env to a voice your Vapi account "
    "lists (for example provider 11labs with a multilingual voice, or Azure hi-IN-AnanyaNeural), then rerun."
)


class VapiError(Exception):
    pass


def public_url() -> str:
    return env("PUBLIC_URL").rstrip("/")


def ensure_secret() -> str:
    secret = env("CATALYST_TOOL_SECRET")
    if not secret:
        secret = secrets.token_urlsafe(24)
        set_env({"CATALYST_TOOL_SECRET": secret})
    return secret


def payload(conn: sqlite3.Connection, secret: str) -> dict:
    s = cs.load(conn)
    system, first = prompt.build(conn, s)
    server = {
        "url": f"{public_url()}/vapi/webhook",
        "headers": {"x-catalyst-secret": secret},
        "timeoutSeconds": SERVER_TIMEOUT_SECONDS,
    }
    voice = s.get("voice") if s.get("voice") in VOICES else "female"
    return {
        "name": f"{s['name']} receptionist"[:40],
        "firstMessage": first,
        "model": {
            "provider": env("VAPI_MODEL_PROVIDER", "openai"),
            "model": env("VAPI_MODEL", "gpt-4.1-mini"),
            "temperature": 0.3,
            "messages": [{"role": "system", "content": system}],
            "tools": [{"type": "function", "function": fn, "server": server} for fn in TOOLS] + [{"type": "endCall"}],
        },
        "voice": {"provider": env("VAPI_VOICE_PROVIDER", "azure"), "voiceId": env("VAPI_VOICE_ID", VOICES[voice])},
        "transcriber": {
            "provider": env("VAPI_TRANSCRIBER_PROVIDER", "deepgram"),
            "model": env("VAPI_TRANSCRIBER_MODEL", "nova-3"),
            "language": env("VAPI_TRANSCRIBER_LANGUAGE", "multi"),
        },
        "server": server,
        "serverMessages": ["end-of-call-report"],
    }


def _request(method: str, path: str, body: dict | None = None) -> dict:
    key = env("VAPI_PRIVATE_KEY")
    if not key:
        raise VapiError("VAPI_PRIVATE_KEY is not set in .env (Vapi dashboard → API Keys → Private key).")
    try:
        r = httpx.request(method, API + path, json=body, timeout=20,
                          headers={"Authorization": f"Bearer {key}"})
    except httpx.HTTPError as e:
        raise VapiError(f"Could not reach Vapi: {type(e).__name__}")
    if r.status_code >= 300:
        raise VapiError(f"Vapi said HTTP {r.status_code}: {r.text[:1500]}")
    return r.json() if r.content else {}


def get_assistant(assistant_id: str) -> dict:
    return _request("GET", f"/assistant/{assistant_id}")


def sync(conn: sqlite3.Connection) -> str:
    """Create the assistant on first run, update it after. Returns a one-line status. Raises VapiError."""
    if not public_url().startswith("https://"):
        raise VapiError("PUBLIC_URL must be the https:// tunnel URL (see README), so Vapi can reach the webhook.")
    body = payload(conn, ensure_secret())
    assistant_id = env("VAPI_ASSISTANT_ID")
    if assistant_id:
        _request("PATCH", f"/assistant/{assistant_id}", body)
        return f"Agent updated ({assistant_id})."
    created = _request("POST", "/assistant", body)
    set_env({"VAPI_ASSISTANT_ID": created["id"]})
    return f"Agent created ({created['id']})."

"""Vapi assistant create/update over the REST API (no SDK). The only Vapi server code in the app.

Field names checked against the @vapi-ai/web 2.7.1 type definitions. VERIFY again if Vapi rejects a field.
"""

import secrets

import httpx

from ...agents import prompt
from ...agents.tool_schemas import TOOLS
from ...core import db, tenancy
from ...core import settings as cs
from ...core.config import env, set_env
from ...core.log import log
from ...verticals import loader

API = "https://api.vapi.ai"
# Azure Hindi neural voices; they read Devanagari Hindi and Latin English words. VERIFY on Vapi.
VOICES = {"female": "hi-IN-SwaraNeural", "male": "hi-IN-MadhurNeural"}
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


def max_call_seconds() -> int:
    """Hard cap on one call, so demo minutes can't run away (there is no Vapi budget; contracts §1.10)."""
    raw = env("VAPI_MAX_CALL_SECONDS", "180")
    return int(raw) if raw.isdigit() and int(raw) > 0 else 180


def template_tools(template: str) -> list[dict]:
    """The function schemas for the tools a template lists in vertical.yaml. A listed tool with no
    schema yet (wholesale, until M4) is left out, with a warning."""
    wanted = loader.tool_names(template)
    found = [fn for fn in TOOLS if fn["name"] in wanted]
    missing = wanted - {fn["name"] for fn in found}
    if missing:
        log.warning("vapi: %s lists tools with no schema yet: %s", template, sorted(missing))
    return found


def payload(
    conn: db.Conn, secret: str, webhook_path: str = "/vapi/webhook", template: str | None = None
) -> dict:
    template = template or prompt.template_name(conn)
    s = cs.load(conn)
    system, first = prompt.build(conn, s, template)
    server = {"url": f"{public_url()}{webhook_path}", "headers": {"x-catalyst-secret": secret}}
    voice = s.get("voice") if s.get("voice") in VOICES else "female"
    return {
        "name": f"{s['name']} receptionist"[:40],
        "firstMessage": first,
        "model": {
            "provider": env("VAPI_MODEL_PROVIDER", "openai"),
            "model": env("VAPI_MODEL", "gpt-4.1-mini"),
            "temperature": 0.3,
            "messages": [{"role": "system", "content": system}],
            "tools": [
                {"type": "function", "function": fn, "server": server}
                for fn in template_tools(template)
            ]
            + [{"type": "endCall"}],
        },
        "voice": {
            "provider": env("VAPI_VOICE_PROVIDER", "azure"),
            "voiceId": env("VAPI_VOICE_ID", VOICES[voice]),
        },
        "transcriber": {
            "provider": env("VAPI_TRANSCRIBER_PROVIDER", "deepgram"),
            "model": env("VAPI_TRANSCRIBER_MODEL", "nova-3"),
            "language": env("VAPI_TRANSCRIBER_LANGUAGE", "multi"),
        },
        "maxDurationSeconds": max_call_seconds(),
        "server": server,
        "serverMessages": ["end-of-call-report"],
    }


def _request(method: str, path: str, body: dict | None = None) -> dict:
    key = env("VAPI_PRIVATE_KEY")
    if not key:
        raise VapiError(
            "VAPI_PRIVATE_KEY is not set in .env (Vapi dashboard → API Keys → Private key)."
        )
    try:
        r = httpx.request(
            method, API + path, json=body, timeout=20, headers={"Authorization": f"Bearer {key}"}
        )
    except httpx.HTTPError as e:
        raise VapiError(f"Could not reach Vapi: {type(e).__name__}") from e
    if r.status_code >= 300:
        raise VapiError(f"Vapi said HTTP {r.status_code}: {r.text[:1500]}")
    return r.json() if r.content else {}


def get_assistant(assistant_id: str) -> dict:
    return _request("GET", f"/assistant/{assistant_id}")


def sync(conn: db.Conn) -> str:
    """Create the assistant on first run, update it after. Returns a one-line status. Raises VapiError."""
    if not public_url().startswith("https://"):
        raise VapiError(
            "PUBLIC_URL must be the https:// tunnel URL (see README), so Vapi can reach the webhook."
        )
    body = payload(conn, ensure_secret())
    assistant_id = env("VAPI_ASSISTANT_ID")
    if assistant_id:
        _request("PATCH", f"/assistant/{assistant_id}", body)
        return f"Agent updated ({assistant_id})."
    created = _request("POST", "/assistant", body)
    set_env({"VAPI_ASSISTANT_ID": created["id"]})
    return f"Agent created ({created['id']})."


def sync_tenant(conn: db.Conn) -> str:
    """Create or update *this business's* assistant: its own webhook path and secret, its own id
    stored on its `tenants` row. Returns "created" or "updated". Raises prompt.NoPrompt for a template
    with no voice agent yet, VapiError for Vapi or config problems."""
    t = tenancy.get(conn, conn.tid)
    if t is None:
        raise LookupError("this connection's business doesn't exist")
    body = payload(conn, t["tool_secret"], f"/vapi/webhook/{t['public_id']}", t["template"])
    if not public_url().startswith("https://"):
        raise VapiError("PUBLIC_URL must be the https:// URL Vapi can reach.")
    if t["vapi_assistant_id"]:
        _request("PATCH", f"/assistant/{t['vapi_assistant_id']}", body)
        return "updated"
    created = _request("POST", "/assistant", body)
    tenancy.set_assistant(conn, created["id"])
    return "created"

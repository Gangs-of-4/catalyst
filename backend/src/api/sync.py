"""Push changed business settings to that business's voice agent, so it never quotes stale facts."""

from ..agents import prompt
from ..core import db, tenancy
from ..core.config import env
from ..core.log import log
from ..providers.voice_orchestrator import vapi
from ..verticals import loader

MESSAGES = {
    "updated": "Saved. The agent has been updated.",
    "failed": "Saved, but updating the agent failed. Try saving again in a minute.",
    "not_configured": "Saved. The agent isn't set up yet, so there is nothing to update.",
}


def agent_configured() -> bool:
    """The demo clinic's original assistant (id in .env) can be updated."""
    return all(env(k) for k in ("VAPI_PRIVATE_KEY", "VAPI_ASSISTANT_ID", "PUBLIC_URL"))


def uses_env_assistant(conn: db.Conn, t: db.Row) -> bool:
    """The one rule for the .env assistant: only the demo clinic uses it, only while its own row
    has no assistant id, and only when VAPI_ASSISTANT_ID is set (a local demo made with
    scripts/setup_vapi.py). Without it, the demo clinic gets its own assistant like any business."""
    return (
        not t["vapi_assistant_id"]
        and bool(env("VAPI_ASSISTANT_ID"))
        and conn.tid == tenancy.demo_id(conn, "clinic")
    )


def agent_available(conn: db.Conn) -> bool:
    """Whether a settings save will update (or create) a voice agent for this business: what the
    settings page shows as `agentConfigured`."""
    t = tenancy.get(conn, conn.tid)
    if uses_env_assistant(conn, t):
        return agent_configured()
    if t["vapi_assistant_id"]:
        return True
    has_prompt = (loader.template_dir(t["template"]) / "agent-prompt.md").exists()
    return bool(env("VAPI_PRIVATE_KEY") and env("PUBLIC_URL")) and has_prompt


def sync_agent(tid: str) -> str:
    """Settings save: push this business's changes to *its own* assistant. Returns a one-line message
    for the settings page. Never raises: settings are saved either way.

    Only the demo clinic, while it has no assistant id on its row, uses its original assistant from
    .env (the try page still reads that id). It never gets a second, per-business assistant. Every
    other business only ever touches its own assistant, so it can't overwrite the demo's."""
    try:
        conn = db.connect().for_tenant(tid)
        try:
            t = tenancy.get(conn, tid)
            if t is None:
                return MESSAGES["failed"]
            if uses_env_assistant(conn, t):
                return _legacy_sync(conn) if agent_configured() else MESSAGES["not_configured"]
        finally:
            conn.close()
    except Exception as e:
        log.warning("vapi: sync lookup failed (%s)", type(e).__name__)
        return MESSAGES["failed"]
    return MESSAGES[sync_tenant_agent(tid)]


def _legacy_sync(conn: db.Conn) -> str:
    try:
        return vapi.sync(conn)
    except vapi.VapiError as e:
        log.warning("vapi: sync failed")
        return f"Saved, but updating the agent failed: {e}"
    except Exception as e:  # never a 500 after the settings are already saved
        log.warning("vapi: sync failed (%s)", type(e).__name__)
        return MESSAGES["failed"]


def sync_demo_agents() -> dict[str, str]:
    """At startup, when DEMO_VOICE=1 (the deployed host): give each demo business without an
    assistant its own one, so the public test pages can call. Does nothing without Vapi set up.
    Returns {template: state}."""
    if env("DEMO_VOICE").lower() not in ("1", "true", "yes"):
        return {}
    if not (env("VAPI_PRIVATE_KEY") and env("PUBLIC_URL")):
        return {}
    conn = db.connect_unchecked()
    try:
        todo = {}
        for template in ("clinic", "wholesale"):
            tid = tenancy.demo_id(conn, template)
            t = tenancy.get(conn, tid) if tid else None
            needs_one = t is not None and not t["vapi_assistant_id"]
            if needs_one and not uses_env_assistant(conn.for_tenant(tid), t):
                todo[template] = tid
    finally:
        conn.close()
    return {template: sync_tenant_agent(tid) for template, tid in todo.items()}


def sync_tenant_agent(tid: str) -> str:
    """Create or update one business's own assistant. Returns "updated", "not_configured" or "failed"
    (the values contracts.md §6 gives the pages). Never raises: the business exists either way."""
    if not (env("VAPI_PRIVATE_KEY") and env("PUBLIC_URL")):
        return "not_configured"
    conn = None
    try:
        conn = db.connect().for_tenant(tid)
        vapi.sync_tenant(conn)
        return "updated"
    except prompt.NoPrompt:
        return "not_configured"  # this template has no voice agent yet
    except Exception as e:  # any failure, not just VapiError: the business is already created
        log.warning("vapi: tenant sync failed (%s)", type(e).__name__)
        return "failed"
    finally:
        if conn is not None:
            conn.close()

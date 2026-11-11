"""Push changed clinic settings to the voice agent, so it never quotes stale facts."""

from ..core import db, tenancy
from ..core.config import env
from ..core.log import log
from ..providers.voice_orchestrator import vapi
from ..verticals import loader

# A business's assistant calls POST /vapi/webhook/{public_id} (api/vapi.py, Phase 2 M3). Kept as a
# switch so the tests can turn assistant creation on and off.
PER_BUSINESS_WEBHOOK_READY = True


def agent_configured() -> bool:
    return all(env(k) for k in ("VAPI_PRIVATE_KEY", "VAPI_ASSISTANT_ID", "PUBLIC_URL"))


def sync_agent(tid: str) -> str:
    """Settings save: push this business's changes to *its own* assistant. Returns a one-line message
    for the settings page. Never raises: settings are saved either way.

    A business with its own assistant id is PATCHed through `sync_tenant_agent`. The demo clinic's
    original assistant (id in .env, global secret) still uses the transitional `vapi.sync`."""
    conn = db.connect().for_tenant(tid)
    try:
        has_own = bool(tenancy.get(conn, tid)["vapi_assistant_id"])
        if not has_own and agent_configured():
            return _legacy_sync(conn)
    finally:
        conn.close()
    state = sync_tenant_agent(tid)
    return {
        "updated": "Saved. The agent has been updated.",
        "failed": "Saved, but updating the agent failed. Try saving again in a minute.",
    }.get(state, "Saved. The agent isn't set up yet, so there is nothing to update.")


def _legacy_sync(conn: db.Conn) -> str:
    try:
        return vapi.sync(conn)
    except vapi.VapiError as e:
        log.warning("vapi: sync failed")
        return f"Saved, but updating the agent failed: {e}"


def sync_tenant_agent(tid: str) -> str:
    """Create or update one business's own assistant. Returns "updated", "not_configured" or "failed"
    (the values contracts.md §6 gives the pages). Never raises: the business exists either way."""
    if not (PER_BUSINESS_WEBHOOK_READY and env("VAPI_PRIVATE_KEY") and env("PUBLIC_URL")):
        return "not_configured"
    conn = None
    try:
        conn = db.connect().for_tenant(tid)
        t = tenancy.get(conn, tid)
        if not (loader.template_dir(t["template"]) / "agent-prompt.md").exists():
            return "not_configured"  # this template has no voice agent yet
        vapi.sync_tenant(conn)
        return "updated"
    except Exception as e:  # any failure, not just VapiError: the business is already created
        log.warning("vapi: tenant sync failed (%s)", type(e).__name__)
        return "failed"
    finally:
        if conn is not None:
            conn.close()

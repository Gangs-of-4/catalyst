"""Push changed clinic settings to the voice agent, so it never quotes stale facts."""

from ..core import db, tenancy
from ..core.config import env
from ..core.log import log
from ..providers.voice_orchestrator import vapi
from ..verticals import loader

# A business's assistant calls POST /vapi/webhook/{public_id}, which M3 adds (phase2-plan.md).
# Until then, signup creates no assistant, so none points at a route that doesn't exist yet.
PER_BUSINESS_WEBHOOK_READY = False


def agent_configured() -> bool:
    return all(env(k) for k in ("VAPI_PRIVATE_KEY", "VAPI_ASSISTANT_ID", "PUBLIC_URL"))


def sync_agent(tid: str) -> str:
    """Returns a one-line result. Never raises: settings are saved either way."""
    if not agent_configured():
        return (
            "Saved. The agent isn't set up yet (run scripts/setup_vapi.py), so nothing to update."
        )
    conn = db.connect().for_tenant(tid)
    try:
        result = vapi.sync(conn)
    except vapi.VapiError as e:
        log.warning("vapi: sync failed")
        return f"Saved, but updating the agent failed: {e}"
    finally:
        conn.close()
    return result


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
            return "not_configured"
        vapi.sync_tenant(conn)
        return "updated"
    except Exception as e:  # any failure, not just VapiError: the business is already created
        log.warning("vapi: tenant sync failed (%s)", type(e).__name__)
        return "failed"
    finally:
        if conn is not None:
            conn.close()

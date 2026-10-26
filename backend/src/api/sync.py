"""Push changed clinic settings to the voice agent, so it never quotes stale facts."""
from ..core import db
from ..core.config import env
from ..core.log import log
from ..providers.voice_orchestrator import vapi


def agent_configured() -> bool:
    return all(env(k) for k in ("VAPI_PRIVATE_KEY", "VAPI_ASSISTANT_ID", "PUBLIC_URL"))


def sync_agent() -> str:
    """Returns a one-line result. Never raises: settings are saved either way."""
    if not agent_configured():
        return "Saved. The agent isn't set up yet (run scripts/setup_vapi.py), so nothing to update."
    conn = db.connect()
    try:
        result = vapi.sync(conn)
    except vapi.VapiError as e:
        log.warning("vapi: sync failed")
        return f"Saved, but updating the agent failed: {e}"
    finally:
        conn.close()
    return result

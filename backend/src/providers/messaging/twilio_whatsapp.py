"""Twilio WhatsApp sender over the REST API (no SDK). The only Twilio code in the app."""
import httpx

from ...core.config import env
from ...core.log import log

API = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


def configured() -> bool:
    return all(env(k) for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM"))


def send(to_e164: str, body: str) -> bool:
    """Send one WhatsApp message. Without credentials it logs 'would send' and returns False."""
    if not configured():
        log.info("whatsapp: Twilio not configured, would send %d chars", len(body))
        return False
    sid = env("TWILIO_ACCOUNT_SID")
    sender = env("TWILIO_WHATSAPP_FROM")
    if not sender.startswith("whatsapp:"):
        sender = "whatsapp:" + sender
    try:
        r = httpx.post(
            API.format(sid=sid),
            auth=(sid, env("TWILIO_AUTH_TOKEN")),
            data={"From": sender, "To": "whatsapp:" + to_e164, "Body": body[:1500]},
            timeout=10,
        )
    except httpx.HTTPError as e:
        log.warning("whatsapp: send failed (%s)", type(e).__name__)
        return False
    if r.status_code >= 300:
        # Twilio's error text can echo the number; the log filter redacts it.
        log.warning("whatsapp: Twilio returned HTTP %s: %s", r.status_code, r.text[:300])
        return False
    log.info("whatsapp: sent message sid=%s", r.json().get("sid"))
    return True

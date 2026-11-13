"""POST /whatsapp/incoming: Twilio WhatsApp sandbox webhook, routed by sender. Replies with TwiML."""

import base64
import hashlib
import hmac
from urllib.parse import parse_qsl
from xml.sax.saxutils import escape

from fastapi import APIRouter, BackgroundTasks, Request, Response
from starlette.concurrency import run_in_threadpool

from .. import analytics
from ..channels.whatsapp import commands
from ..core import db, tenancy
from ..core import phone as ph
from ..core.config import env
from ..core.log import log
from .sync import sync_agent

router = APIRouter()


def twiml(text: str) -> Response:
    body = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{escape(text)}</Message></Response>'
    return Response(body, media_type="application/xml")


def signature_ok(signature: str | None, url: str, params: dict[str, str], token: str) -> bool:
    """Twilio's X-Twilio-Signature: base64(HMAC-SHA1(token, url + sorted key+value pairs))."""
    payload = url + "".join(k + params[k] for k in sorted(params))
    expected = base64.b64encode(
        hmac.new(token.encode(), payload.encode(), hashlib.sha1).digest()
    ).decode()
    return bool(signature) and hmac.compare_digest(signature, expected)


def unknown_number_reply() -> str:
    app_url = env("PUBLIC_APP_URL").rstrip("/")
    where = f"{app_url}/signup par" if app_url else "Catalyst par signup karke"
    return (
        f"Yeh number kisi Catalyst business se juda nahi hai. {where} apna front desk banaiye, "
        "ya Settings mein yahi WhatsApp number daaliye."
    )


@router.post("/whatsapp/incoming")
async def incoming(request: Request, background: BackgroundTasks):
    """One sandbox number serves every business: the sender's number picks the business
    (contracts.md §4). An unknown number changes nothing and is logged without the number."""
    raw = (await request.body()).decode("utf-8", errors="replace")
    params = dict(parse_qsl(raw, keep_blank_values=True))
    token, public = env("TWILIO_AUTH_TOKEN"), env("PUBLIC_URL").rstrip("/")
    # Behind the tunnel Twilio signs the public URL, not the local one.
    if (
        token
        and public
        and not signature_ok(
            request.headers.get("x-twilio-signature"), public + "/whatsapp/incoming", params, token
        )
    ):
        log.warning(
            "whatsapp: bad Twilio signature (is PUBLIC_URL current and the sandbox URL the same?)"
        )
        return Response(status_code=403)

    sender = ph.normalize(params.get("From", ""))
    text = (params.get("Body") or "").strip()
    if not sender:
        return twiml("Number samajh nahi aaya.")
    # Commands read and write the database (and may call the LLM): off the event loop.
    return await run_in_threadpool(_reply, sender, text, background)


def _reply(sender: str, text: str, background: BackgroundTasks) -> Response:
    conn = db.connect()
    try:
        tid = tenancy.for_sender(conn, sender)  # the sender tells us the business
        if tid is None:
            log.info("whatsapp: message from a number linked to no business")
            return twiml(unknown_number_reply())
        if not text:
            return twiml("Sirf text commands chalte hain. 'help' bhejein.")
        scoped = conn.for_tenant(tid)
        reply, changed = commands.handle(scoped, sender, text)
        analytics.record(scoped, "wa_command")
    finally:
        conn.close()
    if changed:
        background.add_task(sync_agent, tid)
    return twiml(reply)

"""POST /whatsapp/incoming: Twilio WhatsApp sandbox webhook. Replies with TwiML."""
import base64
import hashlib
import hmac
import sqlite3
from urllib.parse import parse_qsl
from xml.sax.saxutils import escape

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response

from ..channels.whatsapp import alerts, commands
from ..core import phone as ph
from ..core import settings as cs
from ..core.config import env
from ..core.log import log
from .deps import get_conn
from .sync import sync_agent

router = APIRouter()

OPEN_WARNING = "\n\n⚠️ Demo mode: koi bhi number commands de sakta hai. Setup page par WhatsApp numbers add karein."


def twiml(text: str) -> Response:
    body = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{escape(text)}</Message></Response>'
    return Response(body, media_type="application/xml")


def signature_ok(signature: str | None, url: str, params: dict[str, str], token: str) -> bool:
    """Twilio's X-Twilio-Signature: base64(HMAC-SHA1(token, url + sorted key+value pairs))."""
    payload = url + "".join(k + params[k] for k in sorted(params))
    expected = base64.b64encode(hmac.new(token.encode(), payload.encode(), hashlib.sha1).digest()).decode()
    return bool(signature) and hmac.compare_digest(signature, expected)


@router.post("/whatsapp/incoming")
async def incoming(request: Request, background: BackgroundTasks, conn: sqlite3.Connection = Depends(get_conn)):
    raw = (await request.body()).decode("utf-8", errors="replace")
    params = dict(parse_qsl(raw, keep_blank_values=True))
    token, public = env("TWILIO_AUTH_TOKEN"), env("PUBLIC_URL").rstrip("/")
    if token and public:
        # Behind the tunnel Twilio signs the public URL, not the local one.
        if not signature_ok(request.headers.get("x-twilio-signature"), public + "/whatsapp/incoming", params, token):
            log.warning("whatsapp: bad Twilio signature (is PUBLIC_URL current and the sandbox URL the same?)")
            return Response(status_code=403)

    sender = ph.normalize(params.get("From", ""))
    text = (params.get("Body") or "").strip()
    if not sender:
        return twiml("Number samajh nahi aaya.")
    s = cs.load(conn)
    allowed = alerts.recipients(s)
    if allowed and sender not in allowed:
        log.info("whatsapp: ignored a message from an unregistered number")
        return twiml("Yeh number clinic ke commands ke liye registered nahi hai.")
    if not text:
        return twiml("Sirf text commands chalte hain. 'help' bhejein." + ("" if allowed else OPEN_WARNING))

    reply, changed = commands.handle(conn, sender, text)
    if changed:
        background.add_task(sync_agent)
    return twiml(reply + ("" if allowed else OPEN_WARNING))

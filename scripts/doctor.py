"""Check the demo setup and say, in plain words, what works and what is missing.

Run with the backend venv active, from the repo root:  python scripts/doctor.py
Prints whether each value is set, never the value itself.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import httpx  # noqa: E402

from src.core.config import env, env_path  # noqa: E402

VALUES = [  # name, required, what it's for
    ("PUBLIC_URL", True, "the https tunnel URL; Vapi and Twilio send webhooks here"),
    ("VAPI_PRIVATE_KEY", True, "lets scripts/setup_vapi.py create and update the agent"),
    ("VAPI_PUBLIC_KEY", True, "lets the Try-it page start a web call"),
    ("VAPI_ASSISTANT_ID", True, "written by scripts/setup_vapi.py"),
    ("CATALYST_TOOL_SECRET", True, "written by scripts/setup_vapi.py; Vapi sends it on every tool call"),
    ("DESK_PASSWORD", False, "password for /desk and /setup (open to anyone without it)"),
    ("TWILIO_ACCOUNT_SID", False, "WhatsApp alerts and doctor commands"),
    ("TWILIO_AUTH_TOKEN", False, "WhatsApp alerts and doctor commands"),
    ("TWILIO_WHATSAPP_FROM", False, "the Twilio sandbox number, e.g. whatsapp:+14155238886"),
    ("GROQ_API_KEY", False, "optional: AI parsing of WhatsApp messages the rules don't understand"),
]
OK, WARN, BAD = "  ok ", " warn", " MISSING"


def line(mark: str, text: str) -> None:
    print(f"[{mark.strip():>7}] {text}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    problems = 0
    print(f"Settings file: {env_path()}")
    if not env_path().exists():
        line(BAD, "No .env file. Copy .env.example to .env in the repo root.")
        return 1

    print("\n.env values")
    for name, required, why in VALUES:
        if env(name):
            line(OK, f"{name} is set")
        else:
            line(BAD if required else WARN, f"{name} is empty: {why}")
            problems += required

    print("\nConnections")
    public = env("PUBLIC_URL").rstrip("/")
    if public and not public.startswith("https://"):
        line(BAD, "PUBLIC_URL must start with https:// (use the trycloudflare.com URL), or Vapi can't reach the webhook")
        problems += 1
    if public:
        try:
            # 90 s: a sleeping Render free-tier service needs about a minute to wake.
            r = httpx.get(public + "/healthz", timeout=90)
            if r.status_code == 200:
                line(OK, f"PUBLIC_URL reaches this app ({public})")
            else:
                line(BAD, f"PUBLIC_URL answered HTTP {r.status_code}. Is uvicorn running, and is this the current tunnel URL?")
                problems += 1
        except httpx.HTTPError as e:
            line(BAD, f"PUBLIC_URL is not reachable ({type(e).__name__}). Start cloudflared and copy its new URL.")
            problems += 1

    key, assistant = env("VAPI_PRIVATE_KEY"), env("VAPI_ASSISTANT_ID")
    if key and assistant:
        try:
            r = httpx.get(f"https://api.vapi.ai/assistant/{assistant}", headers={"Authorization": f"Bearer {key}"}, timeout=10)
            if r.status_code == 200:
                line(OK, "Vapi key works and the assistant exists")
                hook = ((r.json().get("server") or {}).get("url") or "")
                if public and not hook.startswith(public):
                    line(BAD, "The agent still points at an old tunnel URL. Run: python scripts/setup_vapi.py")
                    problems += 1
                else:
                    line(OK, "The agent's webhook matches PUBLIC_URL")
            else:
                line(BAD, f"Vapi said HTTP {r.status_code}: {r.text[:200]}")
                problems += 1
        except httpx.HTTPError as e:
            line(BAD, f"Could not reach Vapi ({type(e).__name__})")
            problems += 1
    elif key:
        line(WARN, "No assistant yet. Run: python scripts/setup_vapi.py")

    sid, token = env("TWILIO_ACCOUNT_SID"), env("TWILIO_AUTH_TOKEN")
    if sid and token:
        try:
            r = httpx.get(f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json", auth=(sid, token), timeout=10)
            if r.status_code == 200:
                line(OK, "Twilio credentials work")
                if public:
                    line(OK, f"Twilio sandbox 'When a message comes in' should be: {public}/whatsapp/incoming (POST)")
            else:
                line(BAD, f"Twilio said HTTP {r.status_code}: check the Account SID and Auth Token")
                problems += 1
        except httpx.HTTPError as e:
            line(BAD, f"Could not reach Twilio ({type(e).__name__})")
            problems += 1
    else:
        line(WARN, "Twilio not set: WhatsApp alerts are logged as 'would send' instead")

    from src import seed
    from src.channels.whatsapp import alerts
    from src.core import db
    from src.core import settings as cs

    conn = db.connect()
    seed.ensure(conn)
    numbers = len(alerts.recipients(cs.load(conn)))
    print("\nClinic")
    if numbers:
        line(OK, f"{numbers} WhatsApp number(s) can give commands and get alerts")
    else:
        line(WARN, "No WhatsApp numbers on /setup: anyone can send commands and nobody gets alerts")

    print("\n" + ("All set." if not problems else f"{problems} thing(s) to fix before the demo."))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

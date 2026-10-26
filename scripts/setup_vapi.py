"""Create or update the clinic's Vapi assistant from the current clinic settings.

Run with the backend venv active, from the repo root:  python scripts/setup_vapi.py
Rerun it whenever the tunnel URL (PUBLIC_URL) changes.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from src import seed  # noqa: E402
from src.core import db  # noqa: E402
from src.core.config import env, env_path  # noqa: E402
from src.providers.voice_orchestrator import vapi  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
    if not env_path().exists():
        print(f"No .env found at {env_path()}. Copy .env.example to .env and fill it in first.")
        return 1
    conn = db.connect()
    seed.ensure(conn)
    try:
        status = vapi.sync(conn)
    except vapi.VapiError as e:
        print("Vapi setup failed.\n")
        print(e)
        if "voice" in str(e).lower():
            print("\n" + vapi.FALLBACK_VOICE_HINT)
        return 1
    url = vapi.public_url()
    print(status)
    print(f"\nTry-it page (public):        {url}/")
    print(f"Receptionist desk:           {url}/desk")
    print(f"Clinic settings:             {url}/setup")
    print(f"Twilio sandbox webhook URL:  {url}/whatsapp/incoming   (method POST)")
    print("\nThe tunnel URL changes every time cloudflared restarts. When it does: update PUBLIC_URL in .env,")
    print("rerun this script, and paste the new webhook URL into the Twilio sandbox settings.")
    if not env("VAPI_PUBLIC_KEY"):
        print("\nAlso set VAPI_PUBLIC_KEY in .env (Vapi dashboard → API Keys → Public key) or the call button won't work.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

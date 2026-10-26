"""Groq chat completion over its OpenAI-compatible API (no SDK). Returns raw text or None; callers validate."""
import httpx

from ...core.config import env
from ...core.log import log

URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"  # VERIFY it is still offered on Groq


def complete_json(system: str, user: str, timeout: float = 8) -> str | None:
    key = env("GROQ_API_KEY")
    if not key:
        return None
    try:
        r = httpx.post(
            URL,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": env("GROQ_MODEL", DEFAULT_MODEL),
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            },
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
        log.warning("groq: parse call failed (%s)", type(e).__name__)
        return None

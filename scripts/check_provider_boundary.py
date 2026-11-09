"""Provider boundary check (CLAUDE.md rules 1 and 5, ADR-0014, coding-rules.md).

Vendor code may only live in `backend/src/providers/`. Outside it, this fails on:
  1. importing a vendor SDK (e.g. `import groq`, `from twilio.rest import Client`), and
  2. a string that names a vendor API host (e.g. "https://api.vapi.ai"), because the
     backend calls vendors over plain `httpx`, which an import check alone can't see.

Docstrings and comments are ignored. Run from anywhere:
    python scripts/check_provider_boundary.py [--root <repo root>]
Exit code 0 = clean, 1 = violations found.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

# Top-level package names of vendor SDKs.
VENDOR_PACKAGES = {
    "anthropic",
    "cerebras",
    "daily",
    "deepgram",
    "elevenlabs",
    "exotel",
    "faster_whisper",
    "groq",
    "kokoro",
    "openai",  # Groq and Cerebras are often called through OpenAI-compatible clients
    "pipecat",
    "piper",
    "retell",
    "sarvamai",
    "twilio",
    "vapi",
    "vapi_python",
    "vapi_server_sdk",
}
VENDOR_MODULE_PREFIXES = ("google.genai", "google.generativeai")

# Vendor API hosts. A string containing one of these outside providers/ is a violation.
VENDOR_HOSTS = (
    "api.vapi.ai",
    "api.twilio.com",
    "api.groq.com",
    "api.cerebras.ai",
    "api.openai.com",
    "generativelanguage.googleapis.com",
    "api.elevenlabs.io",
    "api.sarvam.ai",
    "api.retellai.com",
    "api.deepgram.com",
    "exotel.com",
    "exotel.in",
    "graph.facebook.com",
)


def is_vendor_module(name: str) -> bool:
    return name.split(".")[0] in VENDOR_PACKAGES or name.startswith(VENDOR_MODULE_PREFIXES)


def check_file(path: Path, display: str) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=display)
    except (SyntaxError, UnicodeDecodeError) as e:
        return [f"{display}: could not parse: {e}"]

    docstrings = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    }
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [
                f"{display}:{node.lineno}: vendor SDK import `import {a.name}`"
                for a in node.names
                if is_vendor_module(a.name)
            ]
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module and is_vendor_module(node.module):
                found.append(f"{display}:{node.lineno}: vendor SDK import `from {node.module}`")
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            found += [
                f"{display}:{node.lineno}: vendor API host `{host}`"
                for host in VENDOR_HOSTS
                if host in node.value
            ]
    return found


def check_tree(root: Path) -> list[str]:
    src = root / "backend" / "src"
    providers = src / "providers"
    violations: list[str] = []
    for path in sorted(src.rglob("*.py")):
        if providers in path.parents:
            continue
        violations += check_file(path, path.relative_to(root).as_posix())
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    root = parser.parse_args(argv).root.resolve()

    if not (root / "backend" / "src").is_dir():
        print(f"No backend/src under {root}.")
        return 1

    violations = check_tree(root)
    if violations:
        print("Provider boundary check FAILED. Vendor code belongs in backend/src/providers/:")
        for v in violations:
            print(f"  {v}")
        return 1
    print(
        "Provider boundary check passed: no vendor SDKs or API hosts outside backend/src/providers/."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

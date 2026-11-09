"""The provider boundary check passes on our code and catches each kind of violation."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "check_provider_boundary.py"


def run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)], capture_output=True, text=True
    )


def make_tree(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, body in files.items():
        path = tmp_path / "backend" / "src" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return tmp_path


def test_current_backend_is_clean() -> None:
    result = run(REPO)
    assert result.returncode == 0, result.stdout + result.stderr


def test_vendor_code_inside_providers_is_allowed(tmp_path: Path) -> None:
    root = make_tree(
        tmp_path,
        {"providers/llm/groq.py": 'import groq\nAPI = "https://api.groq.com/openai/v1"\n'},
    )
    assert run(root).returncode == 0


def test_sdk_import_outside_providers_fails(tmp_path: Path) -> None:
    root = make_tree(tmp_path, {"booking/x.py": "from twilio.rest import Client\n"})
    result = run(root)
    assert result.returncode == 1
    assert "backend/src/booking/x.py:1" in result.stdout


def test_vendor_host_outside_providers_fails(tmp_path: Path) -> None:
    root = make_tree(tmp_path, {"agents/x.py": 'URL = f"https://api.vapi.ai/call/{1}"\n'})
    result = run(root)
    assert result.returncode == 1
    assert "api.vapi.ai" in result.stdout


def test_docstrings_and_relative_imports_are_ignored(tmp_path: Path) -> None:
    root = make_tree(
        tmp_path,
        {"agents/x.py": '"""Talks to api.vapi.ai via providers."""\nfrom .groq import thing\n'},
    )
    assert run(root).returncode == 0

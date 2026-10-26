"""Loads verticals/clinic/ config. Only loads and shapes; no behaviour."""
from pathlib import Path
from typing import Any

import yaml

from ..core.config import VERTICAL_DIR


def load_yaml(name: str, base: Path = VERTICAL_DIR) -> Any:
    with open(base / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def prompt_template(base: Path = VERTICAL_DIR) -> str:
    """The prompt body of agent-prompt.md: everything after the first '---' rule."""
    text = (base / "agent-prompt.md").read_text(encoding="utf-8")
    return text.split("\n---\n", 1)[-1].strip()


def default_settings(base: Path = VERTICAL_DIR) -> dict:
    """Clinic settings built from the vertical plus the fictional demo tenant."""
    vertical = load_yaml("vertical.yaml", base)
    tenant = load_yaml("demo-tenant.yaml", base)
    rules = load_yaml("escalation-rules.yaml", base)
    knowledge = load_yaml("seed-knowledge.yaml", base)

    fills = {**tenant.get("answers", {}), "tenant_name": tenant["name"]}
    faqs = []
    for entry in knowledge["entries"]:
        # hours, location, doctors and fees are answered live from structured settings
        if entry["id"] in ("hours", "location", "doctors", "consultation_fee"):
            continue
        try:
            faqs.append({"q": entry["question"], "a": entry["answer"].format(**fills)})
        except KeyError:
            continue

    red_flags = [
        f"{r['rationale']} (e.g. {', '.join(r['phrases'][:3])})" for r in rules.get("red_flags", [])
    ]
    return {
        "name": tenant["name"],
        "city": tenant.get("city", ""),
        "address": tenant["address"],
        "landmark": tenant.get("landmark", ""),
        "sessions": tenant["sessions"],
        "closed_weekdays": tenant.get("closed_weekdays", []),
        "slot_min": tenant.get("slot_min") or vertical["booking"]["default_slot_min"],
        "offer_slots": vertical["booking"].get("offer_slots", 3),
        "doctors": tenant["doctors"],
        "services": tenant["services"],
        "faqs": faqs,
        "red_flags": red_flags,
        "emergency_instruction": " ".join(tenant["emergency_instruction"].split()),
        "whatsapp_numbers": tenant.get("whatsapp_numbers", []),
        "voice": tenant.get("voice", "female"),
        "labels": vertical.get("labels", {}),
        "confirm_words": vertical["whatsapp"]["confirm_words"],
        "reject_words": vertical["whatsapp"]["reject_words"],
        "preview_expiry_min": vertical["whatsapp"]["preview_expiry_min"],
    }

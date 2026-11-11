"""Loads verticals/clinic/ config. Only loads and shapes; no behaviour."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ..core.config import VERTICAL_DIR
from ..core.tenancy import VERTICALS_DIR


def load_yaml(name: str, base: Path = VERTICAL_DIR) -> Any:
    with open(base / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


MODULES = {"bookings": "booking", "orders": "orders"}  # module -> its required config section
TOOLS = {
    "get_clinic_info",
    "get_business_info",
    "find_slots",
    "book",
    "find_booking",
    "reschedule",
    "cancel",
    "create_callback",
    "escalate",
    "transfer",
    "log_call_outcome",
    "get_catalog",
    "check_stock",
    "create_order",
    "order_status",
}
REQUIRED = (
    "name",
    "status",
    "version",
    "modules",
    "tools",
    "onboarding",
    "labels",
    "languages",
    "whatsapp",
    "knowledge",
    "safety",
)


def validate(base: Path) -> dict:
    """Load vertical.yaml from `base` and check the keys core code relies on. Raises ValueError."""
    v = load_yaml("vertical.yaml", base)
    if not isinstance(v, dict):
        raise ValueError(f"{base.name}: vertical.yaml is not a mapping")
    missing = [k for k in REQUIRED if k not in v]
    if missing:
        raise ValueError(f"{base.name}: missing keys {missing}")
    if v["name"] != base.name:
        raise ValueError(f"{base.name}: name is {v['name']!r}, must match the folder")
    modules = v["modules"]
    if not modules or any(m not in MODULES for m in modules):
        raise ValueError(f"{base.name}: modules must be a non-empty subset of {sorted(MODULES)}")
    for m in modules:
        if MODULES[m] not in v:
            raise ValueError(f"{base.name}: module {m!r} needs a {MODULES[m]!r} section")
    unknown = set(v["tools"]) - TOOLS
    if unknown:
        raise ValueError(f"{base.name}: unknown tools {sorted(unknown)}")
    return v


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


def template_dir(template: str) -> Path:
    return VERTICALS_DIR / template


@lru_cache(maxsize=32)
def _checked(template: str) -> dict:
    """validate() once per template per process: vertical.yaml only changes with a deploy, and the
    desk polls routes that need it every few seconds."""
    return validate(template_dir(template))


def tool_names(template: str) -> set[str]:
    """The tools a template's agent may call (vertical.yaml `tools`). Raises ValueError if invalid."""
    return set(_checked(template)["tools"])


def modules(template: str) -> list[str]:
    """The desk modules a template uses (vertical.yaml `modules`): bookings, orders."""
    return list(_checked(template)["modules"])


def template_defaults(template: str) -> dict:
    """What a new business of this template starts with: labels, WhatsApp words, safety red flags and
    the form defaults. Nothing from the fictional demo tenant."""
    base = template_dir(template)
    v = validate(base)
    rules_file = base / "escalation-rules.yaml"
    rules = load_yaml("escalation-rules.yaml", base) if rules_file.exists() else {}
    red_flags = [
        f"{r['rationale']} (e.g. {', '.join(r['phrases'][:3])})" for r in rules.get("red_flags", [])
    ]
    return {
        "modules": v["modules"],
        "labels": v.get("labels", {}),
        "onboarding": v.get("onboarding", {}),
        "red_flags": red_flags,
        "offer_slots": v.get("booking", {}).get("offer_slots", 3),
        "default_slot_min": v.get("booking", {}).get("default_slot_min", 15),
        "confirm_words": v["whatsapp"]["confirm_words"],
        "reject_words": v["whatsapp"]["reject_words"],
        "preview_expiry_min": v["whatsapp"]["preview_expiry_min"],
        "has_voice": (base / "agent-prompt.md").exists(),
    }

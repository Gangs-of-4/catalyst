"""Every vertical's config loads and validates with no core change (ADR-0033, ADR-0037)."""

from pathlib import Path

import pytest
import yaml

from src.core.config import REPO_ROOT
from src.verticals import loader

FIXTURES = Path(__file__).parent / "fixtures" / "verticals"
VERTICALS = [p for p in (REPO_ROOT / "verticals").iterdir() if (p / "vertical.yaml").exists()]


@pytest.mark.parametrize(
    "base",
    [p for p in VERTICALS if p.name != "_template"] + [FIXTURES / "demo_coaching"],
    ids=lambda p: p.name,
)
def test_vertical_validates(base):
    v = loader.validate(base)
    assert v["name"] == base.name


def test_both_phase2_templates_exist_with_their_modules():
    assert loader.validate(REPO_ROOT / "verticals" / "clinic")["modules"] == ["bookings"]
    wholesale = loader.validate(REPO_ROOT / "verticals" / "wholesale")
    assert wholesale["modules"] == ["orders"]
    assert {"get_catalog", "create_order", "check_stock"} <= set(wholesale["tools"])


def test_template_keys_cover_every_required_key():
    template = yaml.safe_load(
        (REPO_ROOT / "verticals" / "_template" / "vertical.yaml").read_text("utf-8")
    )
    assert set(loader.REQUIRED) <= set(template)


def _write(tmp_path, name, data):
    base = tmp_path / name
    base.mkdir()
    (base / "vertical.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return base


def _valid(name):
    v = yaml.safe_load((REPO_ROOT / "verticals" / "wholesale" / "vertical.yaml").read_text("utf-8"))
    v["name"] = name
    return v


def test_rejects_module_without_its_section(tmp_path):
    v = _valid("broken")
    del v["orders"]
    with pytest.raises(ValueError, match="orders"):
        loader.validate(_write(tmp_path, "broken", v))


def test_rejects_unknown_tool(tmp_path):
    v = _valid("broken")
    v["tools"].append("send_money")
    with pytest.raises(ValueError, match="send_money"):
        loader.validate(_write(tmp_path, "broken", v))


def test_rejects_name_not_matching_folder(tmp_path):
    with pytest.raises(ValueError, match="folder"):
        loader.validate(_write(tmp_path, "other", _valid("wholesale")))

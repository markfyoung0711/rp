"""Loads the rule tables and property facts (config/*.yaml)."""
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


@lru_cache
def rules() -> dict:
    return yaml.safe_load((CONFIG_DIR / "rules.yaml").read_text())


@lru_cache
def properties() -> dict:
    raw = yaml.safe_load((CONFIG_DIR / "properties.yaml").read_text()) or {}
    return {name.strip().lower(): facts for name, facts in raw.items()}


def property_facts(property_name: str | None) -> dict | None:
    """Facts for a property, matched case-insensitively on full or short name; None if unknown."""
    if not property_name:
        return None
    key = property_name.strip().lower()
    props = properties()
    if key in props:
        return props[key]
    for facts in props.values():
        if str(facts.get("short_name", "")).lower() == key:
            return facts
    return None


def cta_rule(primary_cta: str | None) -> tuple[dict, bool]:
    """(rule, known) for a primary_cta value; unknown values get the default row."""
    table = rules()["cta"]
    key = (primary_cta or "").strip().lower()
    if key in table and key != "default":
        return table[key], True
    return table["default"], False

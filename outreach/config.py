"""Loads the rule tables and property facts (config/*.yaml)."""
import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"


LEARNED_FILE = CONFIG_DIR / "learned.yaml"

# Neutral starting point for the parameters `learn` can infer, so an evaluation shows only what was learned
# (not what I typed in after reading the samples).
NEUTRAL = {
    "channels": {"send_hour": {"default": 9}},
    "send_time": {"stage_default_offset_days": {"default": 1}},
    "next_action": {"new_stages": [], "horizon_threshold_days": None, "follow_up_days": 1},
}

_base = "hand"                 # "hand" (rules.yaml) or "neutral" (rules.yaml with NEUTRAL over the learnable parts)
_learned: dict | None = None   # explicit learned rules; None -> config/learned.yaml if present


def deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def use_rules(base: str = "hand", learned: dict | None = None) -> None:
    """Select the rule set: used by `learn` for evaluation. The CLI uses the default (hand + learned.yaml)."""
    global _base, _learned
    _base, _learned = base, learned
    rules.cache_clear()


def learned_rules() -> dict:
    if _learned is not None:
        return _learned
    if os.environ.get("BOT_RULES") == "hand" or not LEARNED_FILE.exists():
        return {}
    return yaml.safe_load(LEARNED_FILE.read_text()) or {}


def rules_source() -> str:
    """One line for RUN STATS: where the active rules came from."""
    if _base == "neutral":
        return "neutral base + learned (evaluation mode)"
    if os.environ.get("BOT_RULES") == "hand" or not LEARNED_FILE.exists():
        return "hand-written (config/rules.yaml)"
    first = next((ln for ln in LEARNED_FILE.read_text().splitlines() if ln.startswith("# learned from")), "# learned")
    return f"hand-written defaults + {first[2:]} (config/learned.yaml)"


@lru_cache
def rules() -> dict:
    r = yaml.safe_load((CONFIG_DIR / "rules.yaml").read_text())
    if _base == "neutral":
        for section, values in NEUTRAL.items():
            r[section] = {**r[section], **values}
    learned = {k: v for k, v in learned_rules().items() if k != "evidence"}
    return deep_merge(r, learned)


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

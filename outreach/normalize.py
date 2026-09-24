"""Turns any incoming record into a Case the decision code can rely on.

Level 1 (new values) is handled by the rule tables. This module handles:
- Level 2: missing fields, alternative spellings and formats, unknown extra fields.
- Level 3: records of an unknown shape, by searching for the fields we need wherever they are.
Every default or guess is written to `warnings`, so the output explains itself.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import config

KNOWN_TOP = {"task_id", "persona", "lifecycle_stage", "consent", "channel_preferences", "input",
             "assertions", "thresholds", "expected"}
KNOWN_INPUT = {"property_name", "move_date_target", "last_interaction", "timezone", "language", "profile",
               "last_message", "inbound_message", "reply", "last_reply", "last_inbound"}
TRUE_WORDS = {"true", "yes", "y", "1", "opted_in", "opt_in", "granted", "allowed", "on"}
TZ_ALIASES = {"cst": "America/Chicago", "cdt": "America/Chicago", "central": "America/Chicago",
              "est": "America/New_York", "edt": "America/New_York", "eastern": "America/New_York",
              "mst": "America/Denver", "mdt": "America/Denver", "mountain": "America/Denver",
              "pst": "America/Los_Angeles", "pdt": "America/Los_Angeles", "pacific": "America/Los_Angeles",
              "arizona": "America/Phoenix", "utc": "UTC"}
OPT_OUT_KEYS = {"do_not_contact", "dnc", "opted_out", "opt_out", "unsubscribed", "global_opt_out", "suppressed"}
INBOUND_KEYS = {"last_message", "inbound_message", "inbound", "reply", "last_reply", "last_inbound", "message_text"}


@dataclass
class Case:
    task_id: str
    record_type: str                      # "outreach" (known shape) or "unknown" (Level 3)
    persona: str
    stage: str
    consent: dict                         # channel -> True / False
    preferences: list
    opted_out: str | None                 # reason, if any opt-out signal was found
    inbound_text: str | None
    property_name: str | None
    move_date: date | None
    last_interaction: datetime | None
    tz: ZoneInfo
    language: str
    profile: dict
    primary_cta: str | None
    include_opt_out: bool
    expected: dict | None
    warnings: list = field(default_factory=list)


def _truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    return str(v).strip().lower() in TRUE_WORDS


def _channel(name: str) -> str:
    n = str(name).strip().lower().replace(" ", "_")
    return config.rules()["channels"]["aliases"].get(n, n)


def _deep_find(obj, names: set, depth: int = 0):
    """First value whose key (case/punctuation-insensitive) is in `names`, searching nested dicts."""
    if depth > 4 or not isinstance(obj, dict):
        return None
    norm = {re.sub(r"[^a-z0-9]", "", k.lower()): k for k in obj}
    for n in names:
        k = norm.get(re.sub(r"[^a-z0-9]", "", n.lower()))
        if k is not None and obj[k] not in (None, "", [], {}):
            return obj[k]
    for v in obj.values():
        found = _deep_find(v, names, depth + 1)
        if found is not None:
            return found
    return None


def _scan_opt_ins(obj, out: dict, depth: int = 0) -> None:
    """Level 3: collect any `<channel>_opt_in` style keys wherever they are nested."""
    if depth > 4 or not isinstance(obj, dict):
        return
    for k, v in obj.items():
        m = re.fullmatch(r"(sms|text|email|e_?mail|voice|phone|call)_?(opt_?in|opted_?in|consent)", k.lower())
        if m and not isinstance(v, (dict, list)):
            out[_channel(m.group(1).replace("e_mail", "email"))] = _truthy(v)
        elif isinstance(v, dict):
            _scan_opt_ins(v, out, depth + 1)


def _parse_consent(raw, warnings: list) -> dict:
    out: dict = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            ch = _channel(re.sub(r"_?(opt_?in|opted_?in|consent|allowed)$", "", k.strip().lower()))
            out[ch] = _truthy(v)
    elif isinstance(raw, (list, tuple)):
        out = {_channel(c): True for c in raw}
        warnings.append("consent given as a list; listed channels treated as opted in")
    elif isinstance(raw, str):
        out = {_channel(c): True for c in re.split(r"[,;/ ]+", raw) if c}
        warnings.append("consent given as text; listed channels treated as opted in")
    return out


def _parse_datetime(v, warnings: list, label: str) -> datetime | None:
    if v in (None, ""):
        return None
    try:
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, tz=timezone.utc)
        s = str(v).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            warnings.append(f"{label} has no timezone; assumed UTC")
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, OSError, OverflowError):
        warnings.append(f"could not parse {label} {v!r}")
        return None


def _parse_date(v, warnings: list) -> date | None:
    if v in (None, ""):
        return None
    try:
        return date.fromisoformat(str(v).strip()[:10])
    except ValueError:
        warnings.append(f"could not parse move date {v!r}")
        return None


def _parse_tz(v, facts: dict | None, warnings: list) -> ZoneInfo:
    for cand, source in ((v, "record"), ((facts or {}).get("timezone"), "property")):
        if not cand:
            continue
        name = TZ_ALIASES.get(str(cand).strip().lower(), str(cand).strip())
        try:
            tz = ZoneInfo(name)
            if source == "property":
                warnings.append(f"timezone missing or invalid; used the property's ({name})")
            return tz
        except (ZoneInfoNotFoundError, ValueError):
            warnings.append(f"unknown timezone {cand!r}")
    warnings.append("no usable timezone; assumed America/Chicago")
    return ZoneInfo("America/Chicago")


def normalize(rec: dict) -> Case:
    warnings: list = []
    known_shape = any(k in rec for k in ("consent", "channel_preferences", "input", "persona", "lifecycle_stage"))
    inp = rec.get("input") if isinstance(rec.get("input"), dict) else {}
    profile = inp.get("profile") if isinstance(inp.get("profile"), dict) else {}
    if not known_shape:
        warnings.append("unrecognized record shape; fields located by name search (Level 3)")

    def get(*names):
        """Look in input, then the top level, then profile, then anywhere (Level 2/3 tolerance)."""
        for src in (inp, rec, profile):
            for n in names:
                if isinstance(src, dict) and src.get(n) not in (None, "", [], {}):
                    return src[n]
        return _deep_find(rec, set(names))

    extra = sorted((set(rec) - KNOWN_TOP) | {f"input.{k}" for k in set(inp) - KNOWN_INPUT}) if known_shape else []
    if extra:
        warnings.append("ignored unknown fields: " + ", ".join(extra))

    task_id = str(rec.get("task_id") or get("id", "task_id", "case_id", "ticket_id", "record_id") or "no_task_id")
    persona = str(rec.get("persona") or get("persona", "role", "contact_type") or "prospect").strip().lower()
    stage = str(rec.get("lifecycle_stage") or get("lifecycle_stage", "stage", "status") or "unknown").strip().lower()
    if not rec.get("persona"):
        warnings.append(f"persona missing; used {persona!r}")
    if not rec.get("lifecycle_stage"):
        warnings.append(f"lifecycle_stage missing; used {stage!r}")

    consent = _parse_consent(rec["consent"] if "consent" in rec else get("consent", "consents", "opt_ins", "permissions"), warnings)
    if not consent:
        _scan_opt_ins(rec, consent)
        if consent:
            warnings.append("consent found in nested opt-in fields")
    if not consent:
        warnings.append("no consent information found; nothing may be sent")

    prefs_raw = rec.get("channel_preferences") or get("channel_preferences", "preferred_channels", "preferred_channel", "channels")
    if isinstance(prefs_raw, str):
        prefs_raw = re.split(r"[,;/ ]+", prefs_raw)
    preferences = [_channel(c) for c in (prefs_raw or []) if c]
    if not preferences:
        preferences = list(config.rules()["channels"]["default_order"])
        warnings.append("channel_preferences missing; used the default order " + "/".join(preferences))

    opted_out = None
    for k in OPT_OUT_KEYS:
        v = get(k)
        if v is not None and _truthy(v):
            opted_out = f"record flag {k}"
    inbound = get(*INBOUND_KEYS)

    property_name = get("property_name", "property", "community", "building")
    if isinstance(property_name, dict):
        property_name = property_name.get("name")
    facts = config.property_facts(property_name)

    constraints = (rec.get("assertions") or {}).get("constraints") or {}
    primary_cta = constraints.get("primary_cta") or get("primary_cta", "cta", "goal", "intent")
    if isinstance(primary_cta, dict):
        primary_cta = primary_cta.get("type")
    if not primary_cta:
        by_persona = config.rules()["default_cta_by_persona"]
        primary_cta = by_persona.get(persona, by_persona["default"])
        warnings.append(f"primary_cta missing; used {primary_cta!r} for persona {persona!r}")

    first = profile.get("first_name") or get("first_name", "firstname", "given_name")
    if not first:
        full = get("name", "full_name", "contact_name")
        if isinstance(full, str) and full.strip():
            first = full.split()[0]
            warnings.append("first_name missing; taken from full name")
    merged_profile = dict(profile)
    if first:
        merged_profile["first_name"] = first

    return Case(
        task_id=task_id,
        record_type="outreach" if known_shape else "unknown",
        persona=persona,
        stage=stage,
        consent=consent,
        preferences=preferences,
        opted_out=opted_out,
        inbound_text=str(inbound) if inbound is not None else None,
        property_name=str(property_name) if property_name else None,
        move_date=_parse_date(get("move_date_target", "move_date", "move_in_date", "movein"), warnings),
        last_interaction=_parse_datetime(get("last_interaction", "last_contact", "last_activity", "updated_at", "created_at"), warnings, "last_interaction"),
        tz=_parse_tz(get("timezone", "tz", "time_zone"), facts, warnings),
        language=str(get("language", "lang", "locale") or "en").strip().lower()[:2],
        profile=merged_profile,
        primary_cta=str(primary_cta) if primary_cta else None,
        include_opt_out=bool(constraints.get("include_opt_out_instructions", True)),
        expected=rec.get("expected") if isinstance(rec.get("expected"), dict) else None,
        warnings=warnings,
    )

"""Rules validator: every rule change, by a person or an AI, must pass this before the bot will run.

Checks types, allowed values and legal limits for config/rules.yaml merged with config/learned.yaml, and
for config/properties.yaml. Returns a list of plain-English problems; an empty list means valid.
"""
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

KNOWN_CHANNELS = {"sms", "email", "voice"}
KNOWN_PURPOSES = {"tour", "apply", "sign_lease", "payment", "renewal", "maintenance", "general"}
DAYS = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
LEGAL_EARLIEST, LEGAL_LATEST = 8, 21       # federal TCPA calling window, 8 a.m.-9 p.m. local; may be narrowed, never widened
IDENT = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
NEVER_IN_PROMPT = {"last_name", "email", "phone", "ssn", "dob", "date_of_birth", "address", "income", "credit_score",
                   "notes", "religion", "race", "national_origin", "has_children", "disability", "familial_status"}


class RulesError(Exception):
    """The rule configuration is invalid; the message lists every problem."""


def _int(v, lo, hi) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def validate_rules(r: dict) -> list[str]:
    p: list[str] = []

    def need(section: str) -> dict:
        v = r.get(section)
        if not isinstance(v, dict):
            p.append(f"{section}: missing or not a mapping")
            return {}
        return v

    ch = need("channels")
    sup = ch.get("supported")
    if not isinstance(sup, list) or not sup or not set(sup) <= KNOWN_CHANNELS:
        p.append(f"channels.supported: must be a non-empty list drawn from {sorted(KNOWN_CHANNELS)}")
    lw = ch.get("legal_window")
    if not (isinstance(lw, list) and len(lw) == 2 and all(_int(x, 0, 24) for x in lw) and lw[0] < lw[1]):
        p.append("channels.legal_window: must be [earliest_hour, latest_hour] with earliest < latest")
        lw = [LEGAL_EARLIEST, LEGAL_LATEST]
    elif lw[0] < LEGAL_EARLIEST or lw[1] > LEGAL_LATEST:
        p.append(f"channels.legal_window: {lw} is wider than the legal {LEGAL_EARLIEST}:00-{LEGAL_LATEST}:00 window "
                 "(it may be narrowed, never widened)")
    hours = ch.get("send_hour")
    if not isinstance(hours, dict) or "default" not in hours:
        p.append("channels.send_hour: must be a mapping that includes a 'default' hour")
    else:
        for k, v in hours.items():
            if k != "default" and k not in KNOWN_CHANNELS:
                p.append(f"channels.send_hour.{k}: unknown channel")
            if not _int(v, 0, 23):
                p.append(f"channels.send_hour.{k}: {v!r} is not an hour 0-23")
            elif not lw[0] <= v < lw[1]:
                p.append(f"channels.send_hour.{k}: {v}:00 is outside the legal window {lw[0]}:00-{lw[1]}:00")
    order = ch.get("default_order")
    if not isinstance(order, list) or not order or not set(order) <= KNOWN_CHANNELS:
        p.append("channels.default_order: must be a non-empty list of known channels")
    if not isinstance(ch.get("aliases", {}), dict):
        p.append("channels.aliases: must be a mapping")

    st = need("send_time").get("stage_default_offset_days")
    if not isinstance(st, dict) or "default" not in st:
        p.append("send_time.stage_default_offset_days: must be a mapping that includes 'default'")
    else:
        for k, v in st.items():
            if not _int(v, 0, 30):
                p.append(f"send_time.stage_default_offset_days.{k}: {v!r} is not a whole number of days 0-30")

    na = need("next_action")
    if not isinstance(na.get("new_stages"), list) or not all(isinstance(s, str) and IDENT.match(s) for s in na.get("new_stages") or []):
        p.append("next_action.new_stages: must be a list of stage names (lowercase identifiers)")
    thr = na.get("horizon_threshold_days")
    if thr is not None and not _int(thr, 0, 365):
        p.append(f"next_action.horizon_threshold_days: {thr!r} must be a whole number of days 0-365 (or null)")
    if not _int(na.get("follow_up_days"), 1, 60):
        p.append(f"next_action.follow_up_days: {na.get('follow_up_days')!r} must be a whole number of days 1-60")

    stops = r.get("stop_keywords")
    if not isinstance(stops, list) or "STOP" not in stops:
        p.append("stop_keywords: must be a list that includes STOP (required by law)")

    cta = need("cta")
    if "default" not in cta:
        p.append("cta: must include a 'default' row")
    for name, row in cta.items():
        if not isinstance(row, dict):
            p.append(f"cta.{name}: must be a mapping")
            continue
        if not IDENT.match(str(name)):
            p.append(f"cta.{name}: name must be a lowercase identifier")
        if not IDENT.match(str(row.get("type", ""))):
            p.append(f"cta.{name}.type: {row.get('type')!r} must be a lowercase identifier")
        if row.get("purpose") not in KNOWN_PURPOSES:
            p.append(f"cta.{name}.purpose: {row.get('purpose')!r} must be one of {sorted(KNOWN_PURPOSES)}")
        if not isinstance(row.get("link_key"), str):
            p.append(f"cta.{name}.link_key: must be text")
    for persona, target in (r.get("default_cta_by_persona") or {}).items():
        if target not in cta:
            p.append(f"default_cta_by_persona.{persona}: {target!r} is not a row in cta")

    allow = r.get("profile_allow_list")
    if not isinstance(allow, list):
        p.append("profile_allow_list: must be a list")
    else:
        bad = sorted(set(allow) & NEVER_IN_PROMPT)
        if bad:
            p.append(f"profile_allow_list: {bad} are personal or protected data and may never reach the model")
    if not isinstance(r.get("protected_terms"), list) or not r.get("protected_terms"):
        p.append("protected_terms: must be a non-empty list (fair-housing guard)")

    brand = r.get("brand_default") or {}
    if not isinstance(brand, dict):
        p.append("brand_default: must be a mapping")
    else:
        p += _brand_problems(brand, "brand_default")
    return p


def _brand_problems(b: dict, where: str) -> list[str]:
    p = []
    if "max_exclamations" in b and not _int(b["max_exclamations"], 0, 5):
        p.append(f"{where}.max_exclamations: must be 0-5")
    if "max_voice_words" in b and not _int(b["max_voice_words"], 10, 250):
        p.append(f"{where}.max_voice_words: must be 10-250")
    if "voice_intro" in b and not (isinstance(b["voice_intro"], str) and 0 < len(b["voice_intro"]) <= 60):
        p.append(f"{where}.voice_intro: must be a short phrase")
    if "max_sms_chars" in b and not _int(b["max_sms_chars"], 40, 1600):
        p.append(f"{where}.max_sms_chars: must be 40-1600")
    for k in ("emoji_allowed", "shouting_allowed", "use_display_name"):
        if k in b and not isinstance(b[k], bool):
            p.append(f"{where}.{k}: must be true or false")
    if "banned_phrases" in b and not (isinstance(b["banned_phrases"], list) and all(isinstance(x, str) for x in b["banned_phrases"])):
        p.append(f"{where}.banned_phrases: must be a list of phrases")
    return p


def validate_properties(props: dict) -> list[str]:
    p = []
    for name, f in (props or {}).items():
        if not isinstance(f, dict):
            p.append(f"properties.{name}: must be a mapping")
            continue
        tz = f.get("timezone")
        if tz:
            try:
                ZoneInfo(str(tz))
            except (ZoneInfoNotFoundError, ValueError):
                p.append(f"properties.{name}.timezone: {tz!r} is not a known time zone")
        days = f.get("tour_days", [])
        if not isinstance(days, list) or not set(days) <= DAYS:
            p.append(f"properties.{name}.tour_days: must be a list of {sorted(DAYS)}")
        for k, v in f.items():
            if k.endswith("_link") and not (isinstance(v, str) and v.startswith("https://")):
                p.append(f"properties.{name}.{k}: links must start with https://")
        for a, labels in (f.get("amenities") or {}).items():
            if not (isinstance(labels, list) and len(labels) == 2 and all(isinstance(x, str) for x in labels)):
                p.append(f"properties.{name}.amenities.{a}: must be [label in subject, label in body]")
        if isinstance(f.get("brand"), dict):
            p += _brand_problems(f["brand"], f"properties.{name}.brand")
    return p

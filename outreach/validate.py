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

    sfx = r.get("display_name_suffixes", [])
    if not (isinstance(sfx, list) and all(isinstance(x, str) and x.strip() for x in sfx)):
        p.append("display_name_suffixes: must be a list of words")
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


TEMPLATE_KEYS = {
    "": ["language", "name", "opt_out", "days", "days_short", "months", "move_timing", "join_or", "join_and",
         "join_subject", "this_week", "coming_days", "unknown_property", "voice_intro_default", "tour", "general"],
    "tour": ["sms_greeting_new", "sms_greeting_other", "sms_slots", "sms_code", "sms_slots_tail", "sms_noslot",
             "sms_noslot_tail", "sms_noslot_option", "voice_slots", "voice_key", "voice_slots_tail", "voice_noslot",
             "voice_noslot_tail", "email_subject_labels", "email_subject_plain", "email_move", "email_amenities_after_move",
             "email_amenities", "email_move_only", "email_fallback", "email_core", "email_closer_default", "email_link",
             "email_nolink"],
    "general": ["sms_core", "sms_details", "email_core", "email_action", "voice_core", "voice_tail", "lines", "subjects"],
}
PLACEHOLDERS = dict(name="N", prop="P", greeting="G", when="W", days="D", n=1, code="C", short="S", codes="X",
                    opt_out="O", intro="I", day="Y", keys="K", labels="L", article="a", move="M", first="F",
                    closer="Z", link="https://x", line="l", Line="L", month="m")


def validate_template(lang: str, t: dict) -> list[str]:
    """A language file must be complete, its placeholders valid, and its opt-outs usable."""
    p, where = [], f"templates/{lang}.yaml"
    if not re.fullmatch(r"[a-z]{2}", lang):
        p.append(f"{where}: the file name must be a two-letter language code")
    for section, keys in TEMPLATE_KEYS.items():
        block = t if not section else t.get(section, {})
        for k in keys:
            if k not in (block or {}):
                p.append(f"{where}: missing {section + '.' if section else ''}{k}")
    oo = t.get("opt_out") or {}
    for ch in ("sms", "email", "voice"):
        if not isinstance(oo.get(ch), str) or not oo[ch].strip():
            p.append(f"{where}: opt_out.{ch} is required")
    if isinstance(oo.get("sms"), str) and "STOP" not in oo["sms"]:
        p.append(f"{where}: opt_out.sms must include the STOP keyword (carrier requirement)")
    for k, n in (("days", 7), ("days_short", 7), ("months", 12)):
        if not (isinstance(t.get(k), list) and len(t[k]) == n):
            p.append(f"{where}: {k} must list {n} names")
    if "reply_days" in t and not (isinstance(t["reply_days"], list) and len(t["reply_days"]) == 7):
        p.append(f"{where}: reply_days, if set, must list 7 names")
    for key in ("early", "mid", "late"):
        if "{month}" not in str((t.get("move_timing") or {}).get(key, "")):
            p.append(f"{where}: move_timing.{key} must contain {{month}}")
    general = t.get("general") or {}
    for purpose in KNOWN_PURPOSES - {"tour"}:
        for group in ("lines", "subjects"):
            if purpose not in (general.get(group) or {}):
                p.append(f"{where}: general.{group}.{purpose} is missing")

    def walk(v, path):
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, f"{path}.{k}" if path else k)
        elif isinstance(v, str) and "{" in v:
            try:
                v.format(**PLACEHOLDERS)
            except (KeyError, IndexError, ValueError) as e:
                p.append(f"{where}: {path} has an unknown or broken placeholder ({e})")
    walk({k: v for k, v in t.items() if k not in ("stop_keywords", "protected_terms", "banned_phrases")}, "")
    if t.get("direction", "ltr") not in ("ltr", "rtl"):
        p.append(f"{where}: direction must be ltr or rtl")
    if "sms_max_chars" in t and not _int(t["sms_max_chars"], 60, 1600):
        p.append(f"{where}: sms_max_chars must be 60-1600")
    for k in ("stop_keywords", "protected_terms", "banned_phrases"):
        if not isinstance(t.get(k, []), list):
            p.append(f"{where}: {k} must be a list")
    return p


def validate_properties(props: dict, languages: set | None = None) -> list[str]:
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
        fu = f.get("follow_up_days_without_dayN")
        if fu is not None and not _int(fu, 1, 60):
            p.append(f"properties.{name}.follow_up_days_without_dayN: {fu!r} must be a whole number of days 1-60")
        for k, v in f.items():
            if k.endswith("_link") and not (isinstance(v, str) and v.startswith("https://")):
                p.append(f"properties.{name}.{k}: links must start with https://")
        for a, labels in (f.get("amenities") or {}).items():
            if not (isinstance(labels, list) and len(labels) == 2 and all(isinstance(x, str) for x in labels)):
                p.append(f"properties.{name}.amenities.{a}: must be [label in subject, label in body]")
        if isinstance(f.get("brand"), dict):
            p += _brand_problems(f["brand"], f"properties.{name}.brand")
        langs = f.get("languages")
        if langs is not None:
            if not (isinstance(langs, list) and langs and all(isinstance(x, str) for x in langs)):
                p.append(f"properties.{name}.languages: must be a list of language codes")
            elif languages is not None and set(langs) - languages:
                p.append(f"properties.{name}.languages: {sorted(set(langs) - languages)} have no template in config/templates/")
        dl = f.get("default_language")
        if dl is not None and (not isinstance(dl, str) or (langs and dl not in langs) or (languages is not None and dl not in languages)):
            p.append(f"properties.{name}.default_language: {dl!r} must be one of its languages and have a template")
    return p

"""Message composition: template text plus the fixed parts (CTA mechanics and opt-out).

The message has three parts:
  subject  - email only; template or model
  core     - greeting, personalization and the call-to-action question; template or model
  tail     - reply options / link and the opt-out line; ALWAYS this fixed code
Property claims (tour days, amenities, links) come only from config/properties.yaml.
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from . import config
from .normalize import Case

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]     # internal codes used in facts and CTA options


def T(lang: str) -> dict:
    """The message templates for a language (config/templates/<lang>.yaml)."""
    return config.templates()[lang]


def opt_out(lang: str, channel: str) -> str:
    return T(lang)["opt_out"][channel]


def choose_language(case: Case, facts: dict | None, why: list) -> str:
    """The recipient's language if we have templates for it and the property offers it; else the property's
    default; else the global default. Locales like es-MX arrive here already reduced to 'es'."""
    available = set(config.templates())
    offered = set((facts or {}).get("languages") or available)
    default = (facts or {}).get("default_language") or config.rules().get("default_language", "en")
    wanted = case.language
    if wanted in available and wanted in offered:
        return wanted
    chosen = default if default in available else "en"
    reason = "has no template" if wanted not in available else "isn't offered by this property"
    case.warnings.append(f"language {wanted!r} {reason}; wrote {T(chosen)['name']} ({chosen})")
    why.append(f"language: {wanted!r} {reason}; used {chosen}")
    return chosen


def _is_safe_name(raw: str) -> bool:
    """Letters from any script (including combining vowel marks, as in Devanagari or Arabic diacritics),
    plus ' ’ space . - ; starts with a letter; at most 30 characters."""
    if not raw or len(raw) > 30 or not unicodedata.category(raw[0]).startswith("L"):
        return False
    return all(unicodedata.category(c)[0] in "LM" or c in "'’ .-" for c in raw)


@dataclass
class Draft:
    subject: str | None
    core: str
    tail: str
    cta: dict
    facts_used: bool
    tour_days: list | None = None   # full day names offered, in order (for the model prompt)
    lang: str = "en"                # the language actually used


def display_name(full: str) -> str:
    """Short brand-style name for a property without a facts file: 'Cedar Point Apartments' -> 'Cedar Point'."""
    suffixes = sorted(config.rules().get("display_name_suffixes") or [], key=len, reverse=True)
    for sfx in suffixes:
        m = re.match(rf"^(.*\S)\s+{re.escape(sfx)}\.?$", full.strip(), re.I)
        if m and len(m.group(1).split()) >= 1 and m.group(1).lower() not in ("the", "a"):
            return m.group(1)
    return full


def safe_first_name(case: Case, why: list) -> str:
    raw = str(case.profile.get("first_name") or "").strip()
    if raw and _is_safe_name(raw) and not re.search(r"\b(ignore|instruction|system|prompt|assistant)\b", raw, re.I):
        return raw
    if raw:
        # Never echo the rejected value: it may be an email, phone number, ID or injection text.
        why.append(f"first name rejected as unsafe or invalid ({len(raw)} characters, not shown); greeting uses 'there'")
    return "there"


def move_phrase(d: date | None, lang: str) -> str | None:
    if not d:
        return None
    part = ("early", "mid", "late")[0 if d.day <= 10 else 1 if d.day <= 20 else 2]
    return T(lang)["move_timing"][part].format(month=T(lang)["months"][d.month - 1])


def next_tour_days(facts: dict, send_at: datetime) -> list[tuple[str, date]]:
    """The next two tour days after the send date, within the coming week."""
    days = [d for d in facts.get("tour_days", []) if d in DAY_NAMES]
    out = []
    for i in range(1, 8):
        d = send_at.date() + timedelta(days=i)
        if DAY_NAMES[d.weekday()] in days:
            out.append((DAY_NAMES[d.weekday()], d))
    return out[:2]


def amenity_labels(case: Case, facts: dict | None) -> list[tuple[str, str]]:
    interests = case.profile.get("amenity_interest") or []
    if isinstance(interests, str):
        interests = [interests]
    table = (facts or {}).get("amenities", {})
    return [tuple(table[str(i).lower()]) for i in interests if str(i).lower() in table]


def draft(case: Case, channel: str, send_at: datetime, why: list) -> Draft:
    rule, known = config.cta_rule(case.primary_cta)
    if not known:
        why.append(f"primary_cta {case.primary_cta!r} is not mapped; used the generic '{rule['type']}' CTA")
    facts = config.property_facts(case.property_name)
    lang = choose_language(case, facts, why)
    t = T(lang)
    prop_full = case.property_name or t["unknown_property"]
    prop = (facts or {}).get("short_name") or display_name(prop_full)
    if case.property_name and not facts:
        why.append(f"no facts on file for {case.property_name!r}; generic message with no specific claims")
        if not any(g.get("code") == "property_facts_missing" for g in case.gaps):
            case.warnings.append(f"property {case.property_name!r} has no facts file: generic message, default brand, "
                                 f"display name {prop!r}")
            case.gaps.append({"code": "property_facts_missing", "property": case.property_name})
    name = safe_first_name(case, why)
    link = (facts or {}).get(rule["link_key"])
    oo = opt_out(lang, channel)      # always included, whatever the record says
    purpose = rule["purpose"]

    if purpose == "tour":
        d = _tour(case, channel, send_at, t, lang, name, prop, facts, link, oo, rule)
        d.lang = lang
        return d

    g = t["general"]
    line = g["lines"][purpose].format(prop=prop)
    Line = line[0].upper() + line[1:]
    cta = {"type": rule["type"]}
    if channel == "voice":
        # A call can't carry a link: offer to connect the caller to the team instead.
        core = g["voice_core"].format(name=name, intro=voice_intro(facts, prop, lang), Line=Line)
        tail = g["voice_tail"].format(opt_out=oo)
        cta["options"] = ["1"]
        return Draft(None, core, tail, cta, bool(facts), lang=lang)
    if link:
        cta["link"] = link
    if channel == "sms":
        core = g["sms_core"].format(name=name, line=line)
        tail = ((g["sms_details"].format(link=link) + " ") if link else "") + oo
        return Draft(None, core, tail.strip(), cta, bool(facts), lang=lang)
    subject = g["subjects"][purpose].format(prop=prop)
    core = g["email_core"].format(name=name, Line=Line)
    tail = ((g["email_action"].format(link=link) + "\n") if link else "") + oo
    return Draft(subject, core, tail, cta, bool(facts), lang=lang)


def voice_intro(facts: dict | None, prop: str, lang: str) -> str:
    """How an automated call identifies itself: the brand's voice_intro (a string for English, or a mapping per
    language), else the language's default "this is <property>"."""
    intro = ((facts or {}).get("brand") or {}).get("voice_intro")
    if isinstance(intro, dict) and intro.get(lang):
        return intro[lang]
    if isinstance(intro, str) and intro and lang == "en":
        return intro
    return T(lang)["voice_intro_default"].format(prop=prop)


def _tour(case, channel, send_at, t, lang, name, prop, facts, link, oo, rule) -> Draft:
    tt = t["tour"]
    cta = {"type": rule["type"]}
    slots = next_tour_days(facts, send_at) if facts and channel in ("sms", "voice") else []
    if slots:
        full = [t["days"][d.weekday()] for _, d in slots]
        this_week = all(d.isocalendar()[1] == send_at.date().isocalendar()[1] for _, d in slots)
        when = t["this_week"] if this_week else t["coming_days"]
        days = t["join_or"].join(full)
    reply = t.get("reply_days") or t["days_short"]      # day labels in reply codes and CTA options
    if channel == "voice":
        # Automated call script: the same offer as SMS, with keypad choices instead of reply codes.
        intro = voice_intro(facts, prop, lang)
        if slots:
            core = tt["voice_slots"].format(name=name, intro=intro, when=when, days=days)
            keys = ", ".join(tt["voice_key"].format(n=i + 1, day=f) for i, f in enumerate(full))
            tail = tt["voice_slots_tail"].format(keys=keys, opt_out=oo)
            cta["options"] = [reply[d.weekday()] for _, d in slots]
            return Draft(None, core, tail, cta, bool(facts), full)
        core = tt["voice_noslot"].format(name=name, intro=intro)
        tail = tt["voice_noslot_tail"].format(opt_out=oo)
        cta["options"] = ["1"]
        return Draft(None, core, tail, cta, bool(facts))
    if channel == "sms":
        if slots:
            greeting = tt["sms_greeting_new"] if case.stage == "new" else tt["sms_greeting_other"]
            core = tt["sms_slots"].format(name=name, greeting=greeting, prop=prop, when=when, days=days)
            codes = ", ".join(tt["sms_code"].format(n=i + 1, code=s, short=reply[d.weekday()])
                              for i, (s, d) in enumerate(slots))
            tail = tt["sms_slots_tail"].format(codes=codes, opt_out=oo)
            cta["options"] = [reply[d.weekday()] for _, d in slots]
            return Draft(None, core, tail, cta, bool(facts), full)
        core = tt["sms_noslot"].format(name=name, prop=prop)
        tail = tt["sms_noslot_tail"].format(opt_out=oo)
        cta["options"] = [tt["sms_noslot_option"]]
        return Draft(None, core, tail, cta, bool(facts))

    # email
    labels = amenity_labels(case, facts)
    move = move_phrase(case.move_date, lang)
    form = 0 if tt.get("email_subject_label_form", "subject") == "subject" else 1
    if labels:
        subject = tt["email_subject_labels"].format(prop=prop, labels=t["join_subject"].join(lab[form] for lab in labels))
    else:
        subject = tt["email_subject_plain"].format(prop=prop)
    body_labels = t["join_and"].join(b for _, b in labels)
    parts = []
    if move:
        article = ("an" if move[0].lower() in "aeiou" else "a") if t.get("article_an_before_vowel") else ""
        parts.append(tt["email_move"].format(article=article, move=move))
    if labels:
        parts.append((tt["email_amenities_after_move"] if move else tt["email_amenities"]).format(labels=body_labels))
    elif move:
        parts.append(tt["email_move_only"].format(prop=prop))
    first = "".join(parts) or tt["email_fallback"].format(prop=prop)
    closer = ((facts or {}).get("email_closer") if tt.get("use_property_closer") else None) or tt["email_closer_default"]
    core = tt["email_core"].format(name=name, first=first, closer=closer)
    tail = ((tt["email_link"].format(link=link) + "\n") if link else (tt["email_nolink"] + "\n")) + oo
    if link:
        cta["link"] = link
    return Draft(subject, core, tail, cta, bool(facts))


LTR_RUN = re.compile(r"https?://\S+|[A-Za-z0-9][A-Za-z0-9 .:/#-]*[A-Za-z0-9]|[A-Za-z0-9]")


def bidi_isolate(text: str) -> str:
    """In right-to-left text, wrap left-to-right runs (links, STOP, digits, Latin names) in Unicode isolates
    (LRI ... PDI) so they display in the right order and don't scramble the surrounding sentence."""
    return LTR_RUN.sub(lambda m: "\u2066" + m.group(0) + "\u2069", text)


def assemble(channel: str, core: str, tail: str, lang: str = "en") -> str:
    body = f"{core.rstrip()} {tail}" if channel in ("sms", "voice") else f"{core.rstrip()}\n{tail}"
    return bidi_isolate(body) if T(lang).get("direction") == "rtl" else body


def rendered_opt_out(lang: str, channel: str) -> str:
    """The opt-out line exactly as it appears in an assembled message."""
    oo = opt_out(lang, channel)
    return bidi_isolate(oo) if T(lang).get("direction") == "rtl" else oo

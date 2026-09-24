"""The deterministic decisions: may we send, which channel, when, and what happens next.

No model is involved here. These are the compliance-critical choices, so they are plain code.
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from . import config
from .normalize import Case


@dataclass
class Decision:
    send: bool
    channel: str | None = None
    send_at: datetime | None = None
    next_action: dict | None = None
    suppress_reason: str | None = None


def _wordish(c: str) -> bool:
    return bool(c) and (c.isalnum() or c == "_" or unicodedata.category(c).startswith("M"))


def stop_gate(case: Case, why: list) -> str | None:
    """Opt-out wins before anything else, and before any model call."""
    if case.opted_out:
        return f"opted out ({case.opted_out})"
    if case.inbound_text:
        words = config.rules()["stop_keywords"]
        text = case.inbound_text.upper()
        for m in re.finditer("|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)), text):
            # a whole word only; \b can't be used: it treats combining marks (Hindi vowel signs) as non-word
            if not _wordish(text[m.start() - 1: m.start()]) and not _wordish(text[m.end(): m.end() + 1]):
                return f"inbound message contains opt-out keyword {m.group(0)!r}"
    why.append("stop check: no opt-out signal")
    return None


def choose_channel(case: Case, why: list) -> str | None:
    supported = config.rules()["channels"]["supported"]
    skipped = []
    for ch in case.preferences:
        if ch not in supported:
            skipped.append(f"{ch} (not supported yet)")
            continue
        if case.consent.get(ch) is True:
            note = f"; skipped {', '.join(skipped)}" if skipped else ""
            why.append(f"channel: {ch}, the first preferred channel with consent (preferences {'/'.join(case.preferences)}{note})")
            return ch
        skipped.append(f"{ch} (no consent)")
    why.append("channel: none usable: " + ", ".join(skipped or ["no channels listed"]))
    return None


def day_offset(case: Case, why: list) -> int:
    m = re.search(r"day[_-]?(\d+)", case.task_id, re.IGNORECASE)
    if m:
        return int(m.group(1))
    table = config.rules()["send_time"]["stage_default_offset_days"]
    offset = table.get(case.stage, table["default"])
    why.append(f"no dayN in task_id; stage {case.stage!r} default offset +{offset} day(s)")
    return offset


def send_time(case: Case, channel: str, now: datetime | None, why: list) -> datetime:
    rules = config.rules()["channels"]
    hour = rules["send_hour"].get(channel, rules["send_hour"]["default"])
    lo, hi = rules["legal_window"]
    hour = min(max(hour, lo), hi - 1)

    base = case.last_interaction
    if base is None:
        base = now or datetime.now(case.tz)
        case.warnings.append("last_interaction missing; counted from " + ("--now" if now else "the current time (not reproducible)"))
    base_local = base.astimezone(case.tz)
    offset = day_offset(case, why)

    target_date = base_local.date() + timedelta(days=offset)
    candidate = datetime.combine(target_date, time(hour), tzinfo=case.tz)
    rolled = 0
    floor = max(base_local, now.astimezone(case.tz)) if now else base_local
    while candidate <= floor:
        candidate += timedelta(days=1)
        rolled += 1
    why.append(
        f"send time: last interaction {base_local:%a %b %d %H:%M} local + {offset} day(s) at {hour:02d}:00 {channel}"
        + (f", rolled forward {rolled} day(s) because that time had passed" if rolled else "")
        + f" -> {candidate:%a %b %d %H:%M %Z}"
    )
    return candidate


def next_action(case: Case, purpose: str, send_at: datetime | None, why: list) -> dict:
    rules = config.rules()["next_action"]
    if case.stage in rules["new_stages"]:
        threshold = rules.get("horizon_threshold_days")
        if case.move_date and send_at and threshold is not None:
            days = (case.move_date - send_at.date()).days
            horizon = "short" if days <= threshold else "long"
            basis = f"{days} days to move-in (threshold {threshold})"
        else:
            horizon = "short"
            basis = "no move date or no learned threshold; defaulted to short"
        topic = "welcome" if purpose == "tour" else purpose
        name = f"{case.persona}_{topic}_{horizon}_horizon"
        why.append(f"next action: new lead -> start cadence {name} ({basis})")
        return {"type": "start_cadence", "name": name}
    days = rules["follow_up_days"]
    basis = ""
    facts = config.property_facts(case.property_name) or {}
    if facts.get("follow_up_days_without_dayN") is not None and not re.search(r"day[_-]?\d+", case.task_id, re.IGNORECASE):
        days = facts["follow_up_days_without_dayN"]
        basis = " (property setting: no dayN in task_id)"
    why.append(f"next action: stage {case.stage!r} is not new -> follow up in {days} days{basis}")
    return {"type": "follow_up_in_days", "value": days}

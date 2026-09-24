"""Learn the decision rules from labelled examples (records that carry an `expected` block).

No model and no API: each rule is inferred from what the examples show, with the number of examples
supporting it. What can be learned:
  - send hour per channel         (hour of expected send_at, by expected channel)
  - day-offset rule               (does send date = last interaction + dayN, rolled forward if passed?)
  - stage default offset          (for examples without dayN)
  - CTA mapping                   (primary_cta -> expected cta.type; reply options vs link by channel)
  - next action by stage          (start a cadence vs follow up, and the follow-up days)
  - horizon threshold             (days to move-in separating short from long; labels from cadence names or task_ids)
  - channel rule check            (first preferred channel with consent: does it reproduce the examples?)
"""
import re
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta

from . import config, decide
from .normalize import normalize


SAFE_TOKEN = re.compile(r"^[a-z][a-z0-9_]{0,39}$")       # learned names must be plain identifiers
KNOWN_ACTIONS = {"start_cadence", "follow_up_in_days", "suppress", "human_review", "none"}


def _label_problem(msg, action) -> str | None:
    """Why an `expected` block can't be learned from (poisoned or malformed labels), or None."""
    if msg is not None and not isinstance(msg, dict):
        return "next_message is not an object"
    if not isinstance(action, dict):
        return "next_action missing or not an object"
    if action.get("type") not in KNOWN_ACTIONS:
        return "next_action.type not recognized"
    if msg and msg.get("channel") not in config.rules()["channels"]["supported"]:
        return "channel not a supported channel"
    if action.get("type") == "start_cadence" and not SAFE_TOKEN.match(str(action.get("name", ""))):
        return "cadence name not a plain identifier"
    return None


def _expected(rec: dict) -> dict | None:
    e = rec.get("expected")
    return e if isinstance(e, dict) else None


def learn(records: list) -> tuple[dict, list[str]]:
    """(learned rule overrides, evidence lines) from labelled records."""
    hours: dict[str, Counter] = defaultdict(Counter)
    offset_ok = offset_total = 0
    stage_offsets: dict[str, Counter] = defaultdict(Counter)
    cta_map: dict[str, Counter] = defaultdict(Counter)
    cta_shape: dict[str, Counter] = defaultdict(Counter)
    stage_action: dict[str, Counter] = defaultdict(Counter)
    follow_days: Counter = Counter()
    short_days: list[int] = []
    long_days: list[int] = []
    channel_ok = channel_total = 0
    no_send = 0
    labelled = 0

    skipped: Counter = Counter()      # whole example rejected
    ignored: Counter = Counter()      # one value in an otherwise usable example not learned
    for rec in records:
        exp = _expected(rec) if isinstance(rec, dict) else None
        if not exp:
            continue
        labelled += 1
        msg, action = exp.get("next_message"), exp.get("next_action")
        problem = _label_problem(msg, action)
        if problem:
            skipped[problem] += 1
            continue
        try:
            case = normalize({k: v for k, v in rec.items() if k != "expected"})
        except Exception:  # noqa: BLE001 -- a bad example is skipped, never fatal
            skipped["input could not be normalized"] += 1
            continue
        if not msg:
            no_send += 1
            continue
        ch = msg.get("channel")
        channel_total += 1
        channel_ok += decide.choose_channel(case, []) == ch
        try:
            sent = datetime.fromisoformat(str(msg["send_at"]).replace("Z", "+00:00"))
            if sent.tzinfo is None:
                raise ValueError
        except (KeyError, ValueError):
            skipped["send_at is not an ISO time with offset"] += 1
            continue
        local = sent.astimezone(case.tz)
        lo, hi = config.rules()["channels"]["legal_window"]
        if lo <= local.hour < hi:
            hours[ch][local.hour] += 1
        else:
            ignored[f"send hour outside the legal window {lo:02d}:00-{hi:02d}:00"] += 1

        if case.last_interaction:
            base = case.last_interaction.astimezone(case.tz)
            delta = (local.date() - base.date()).days
            m = re.search(r"day[_-]?(\d+)", case.task_id, re.I)
            if m:
                n = int(m.group(1))
                offset_total += 1
                at_n = datetime.combine(base.date() + timedelta(days=n), time(local.hour), tzinfo=case.tz)
                offset_ok += delta == n or (delta == n + 1 and at_n <= base)
            else:
                stage_offsets[case.stage][delta] += 1

        cta = msg.get("cta") if isinstance(msg.get("cta"), dict) else {}
        if case.primary_cta and cta.get("type"):
            if SAFE_TOKEN.match(str(case.primary_cta)) and SAFE_TOKEN.match(str(cta["type"])):
                cta_map[case.primary_cta][cta["type"]] += 1
            else:
                ignored["CTA name not a plain identifier"] += 1
        cta_shape[ch]["options" if "options" in cta else "link" if "link" in cta else "none"] += 1

        stage_action[case.stage][action.get("type")] += 1
        if action.get("type") == "follow_up_in_days" and isinstance(action.get("value"), int) and 1 <= action["value"] <= 60:
            follow_days[action["value"]] += 1
        # Horizon label: from the expected cadence name, or else from a task_id that names the horizon ("..._long_horizon_...").
        label = re.search(r"(short|long)_horizon", str(action.get("name", ""))) or re.search(r"(short|long)_horizon", case.task_id)
        if label and case.move_date:
            (short_days if label.group(1) == "short" else long_days).append((case.move_date - local.date()).days)

    learned: dict = {"channels": {"send_hour": {}}, "send_time": {"stage_default_offset_days": {}}, "next_action": {}, "cta": {}}
    used = labelled - sum(skipped.values())
    ev: list[str] = [f"learned from {used} labelled example(s)" + (f" ({no_send} no-send)" if no_send else "")
                     + (f"; {sum(skipped.values())} skipped" if skipped else "")]
    for reason, n in skipped.most_common():
        ev.append(f"rejected       {n} example(s): {reason}")
    for reason, n in ignored.most_common():
        ev.append(f"not learned    {n} value(s): {reason}")

    for ch, c in sorted(hours.items()):
        hour, n = c.most_common(1)[0]
        learned["channels"]["send_hour"][ch] = hour
        ev.append(f"send hour      {ch} {hour:02d}:00  ({n}/{sum(c.values())} example(s))")
    if offset_total:
        ev.append(f"day offset     send date = last interaction + dayN, rolled forward if passed: {offset_ok}/{offset_total} example(s) agree"
                  + ("" if offset_ok == offset_total else "  ← rule does NOT fit every example"))
    for stage, c in sorted(stage_offsets.items()):
        d, n = c.most_common(1)[0]
        if not (SAFE_TOKEN.match(stage) and 0 <= d <= 30):
            ev.append("stage offset   an implausible stage or offset was not learned")
            continue
        learned["send_time"]["stage_default_offset_days"][stage] = d
        ev.append(f"stage offset   {stage}: +{d} day(s)  ({n} example(s) without dayN)")
    if channel_total:
        ev.append(f"channel        first preferred channel with consent reproduces {channel_ok}/{channel_total} example(s)")
    base_cta = config.rules()["cta"]
    for primary, c in sorted(cta_map.items()):
        t, n = c.most_common(1)[0]
        row = dict(base_cta.get(primary, base_cta["default"]))
        row["type"] = t
        learned["cta"][primary] = row
        ev.append(f"CTA mapping    {primary} → {t}  ({n}/{sum(c.values())})")
    for ch, c in sorted(cta_shape.items()):
        ev.append(f"CTA shape      {ch}: {c.most_common(1)[0][0]}  ({c.most_common(1)[0][1]} example(s))")

    new_stages = sorted(s for s, c in stage_action.items() if c.most_common(1)[0][0] == "start_cadence" and SAFE_TOKEN.match(s))
    if stage_action:
        learned["next_action"]["new_stages"] = new_stages
        for s, c in sorted(stage_action.items()):
            ev.append(f"next action    stage {s!r} → {c.most_common(1)[0][0]}  ({c.most_common(1)[0][1]} example(s))")
    if follow_days:
        d, n = follow_days.most_common(1)[0]
        learned["next_action"]["follow_up_days"] = d
        ev.append(f"follow-up      {d} day(s)  ({n} example(s))")
    if short_days and long_days:
        lo, hi = max(short_days), min(long_days)
        if lo < hi:
            thr = (lo + hi) // 2
            if not 0 <= thr <= 365:
                ev.append("horizon        implausible threshold; not learned")
                return _prune(learned), ev
            learned["next_action"]["horizon_threshold_days"] = thr
            ev.append(f"horizon        short ≤ {lo} days, long ≥ {hi} days → threshold {thr} days (midpoint; true value lies in {lo}–{hi - 1})")
        else:
            ev.append(f"horizon        short and long overlap ({lo} vs {hi} days): no clean threshold")
    elif short_days or long_days:
        seen = short_days or long_days
        kind = "short" if short_days else "long"
        learned["next_action"]["horizon_threshold_days"] = max(seen) if short_days else min(seen) - 1
        ev.append(f"horizon        only '{kind}' examples ({sorted(seen)} days): threshold set at the edge; needs a '{'long' if short_days else 'short'}' example")

    return _prune(learned), ev


def _prune(d):
    """Drop empty sections so an unlearned parameter keeps its current value."""
    if isinstance(d, dict):
        out = {k: _prune(v) for k, v in d.items()}
        return {k: v for k, v in out.items() if v not in ({}, None) or k == "horizon_threshold_days" and v is not None}
    return d

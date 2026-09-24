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

    for rec in records:
        exp = _expected(rec) if isinstance(rec, dict) else None
        if not exp:
            continue
        labelled += 1
        case = normalize({k: v for k, v in rec.items() if k != "expected"})
        msg, action = exp.get("next_message"), exp.get("next_action") or {}
        if not msg:
            no_send += 1
            continue
        ch = msg.get("channel")
        channel_total += 1
        channel_ok += decide.choose_channel(case, []) == ch
        try:
            sent = datetime.fromisoformat(str(msg["send_at"]))
        except (KeyError, ValueError):
            continue
        local = sent.astimezone(case.tz)
        hours[ch][local.hour] += 1

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

        cta = msg.get("cta") or {}
        if case.primary_cta and cta.get("type"):
            cta_map[case.primary_cta][cta["type"]] += 1
        cta_shape[ch]["options" if "options" in cta else "link" if "link" in cta else "none"] += 1

        stage_action[case.stage][action.get("type")] += 1
        if action.get("type") == "follow_up_in_days" and isinstance(action.get("value"), int):
            follow_days[action["value"]] += 1
        # Horizon label: from the expected cadence name, or else from a task_id that names the horizon ("..._long_horizon_...").
        label = re.search(r"(short|long)_horizon", str(action.get("name", ""))) or re.search(r"(short|long)_horizon", case.task_id)
        if label and case.move_date:
            (short_days if label.group(1) == "short" else long_days).append((case.move_date - local.date()).days)

    learned: dict = {"channels": {"send_hour": {}}, "send_time": {"stage_default_offset_days": {}}, "next_action": {}, "cta": {}}
    ev: list[str] = [f"learned from {labelled} labelled example(s)" + (f" ({no_send} no-send)" if no_send else "")]

    for ch, c in sorted(hours.items()):
        hour, n = c.most_common(1)[0]
        learned["channels"]["send_hour"][ch] = hour
        ev.append(f"send hour      {ch} {hour:02d}:00  ({n}/{sum(c.values())} example(s))")
    if offset_total:
        ev.append(f"day offset     send date = last interaction + dayN, rolled forward if passed: {offset_ok}/{offset_total} example(s) agree"
                  + ("" if offset_ok == offset_total else "  ← rule does NOT fit every example"))
    for stage, c in sorted(stage_offsets.items()):
        d, n = c.most_common(1)[0]
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

    new_stages = sorted(s for s, c in stage_action.items() if c.most_common(1)[0][0] == "start_cadence")
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

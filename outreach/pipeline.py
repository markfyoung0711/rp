"""One record in, one decision out. Never raises: any failure becomes a safe no-send with a reason."""
import time as _time
from datetime import datetime

from . import compose, decide, guards
from .normalize import Case, normalize
from .reader import ReadError


def decide_only(case: Case) -> tuple[str, compose.Draft] | None:
    """Channel and template draft for a case (used to build few-shot examples)."""
    why: list = []
    if decide.stop_gate(case, why):
        return None
    channel = decide.choose_channel(case, why)
    if not channel:
        return None
    send_at = decide.send_time(case, channel, None, why)
    return channel, compose.draft(case, channel, send_at, why)


def _no_send(task_id: str, reason: str, why: list, warnings: list, action: str = "suppress", **meta) -> dict:
    why.append(f"decision: do not send ({reason})")
    return {
        "task_id": task_id,
        "next_message": None,
        "next_action": {"type": action, "reason": reason},
        "why": why,
        "meta": {"warnings": warnings, **meta},
    }


async def process(item, *, use_llm: bool = False, model: str = "claude-haiku-4-5", now: datetime | None = None) -> dict:
    started = _time.perf_counter()
    try:
        out = await _process(item, use_llm, model, now)
    except Exception as e:  # last-resort safety net: never crash the batch
        tid = item.get("task_id", "unknown") if isinstance(item, dict) else "unknown"
        out = _no_send(str(tid), f"internal error: {type(e).__name__}: {e}", [], [], action="human_review")
    out["meta"]["latency_ms"] = round((_time.perf_counter() - started) * 1000, 1)
    return out


async def _process(item, use_llm: bool, model: str, now: datetime | None) -> dict:
    if isinstance(item, ReadError):
        return _no_send(item.task_id, f"unreadable record at line {item.line}: {item.message}", [], [],
                        action="human_review", record_type="unreadable", confidence="n/a")

    case = normalize(item)
    why: list = []
    confidence = "high" if case.record_type == "outreach" and not case.warnings else "medium" if case.record_type == "outreach" else "low"
    base_meta = {"record_type": case.record_type, "confidence": confidence, "mode": "llm" if use_llm else "template"}

    stop = decide.stop_gate(case, why)
    if stop:
        return _no_send(case.task_id, stop, why, case.warnings, **base_meta)

    channel = decide.choose_channel(case, why)
    if not channel:
        action = "human_review" if case.record_type == "unknown" or not case.consent else "suppress"
        return _no_send(case.task_id, "no channel with consent", why, case.warnings, action=action, **base_meta)

    send_at = decide.send_time(case, channel, now, why)
    draft = compose.draft(case, channel, send_at, why)
    subject, core = draft.subject, draft.core

    if use_llm:
        written = await _llm_write(case, channel, draft, model, why)
        if written:
            subject, core = written
    else:
        why.append("wording: template")

    body = compose.assemble(channel, core, draft.tail)
    opt_out_line = compose.OPT_OUT[case.language if case.language in compose.SUPPORTED_LANGS else "en"][channel]
    problems = guards.check_message(channel, subject, body, opt_out_line)
    if problems and (subject, core) != (draft.subject, draft.core):
        why.append("guards: model version failed (" + "; ".join(problems) + "); reverted to the template")
        subject, body = draft.subject, compose.assemble(channel, draft.core, draft.tail)
        problems = guards.check_message(channel, subject, body, opt_out_line)
    if problems:
        return _no_send(case.task_id, "guard failure: " + "; ".join(problems), why, case.warnings,
                        action="human_review", **base_meta)
    why.append("guards: opt-out present, no contact details, no protected-class terms")

    purpose = compose.config.cta_rule(case.primary_cta)[0]["purpose"]
    return {
        "task_id": case.task_id,
        "next_message": {
            "channel": channel,
            "send_at": send_at.isoformat(),
            "subject": subject if channel == "email" else None,
            "body": body,
            "cta": draft.cta,
        },
        "next_action": decide.next_action(case, purpose, send_at, why),
        "why": why,
        "meta": {**base_meta, "warnings": case.warnings},
    }


async def _llm_write(case, channel, draft, model, why):
    from . import llm
    return await llm.write(case, channel, draft, model, why)

"""Leasing-outreach decision bot: records in, one decision per record out.

  uv run bot.py --input plans/sample.jsonl --compare
  uv run bot.py --input holdout.jsonl --output out/holdout.jsonl
  uv run bot.py --paste --output out/holdout.jsonl        (paste, then Ctrl+D)
  add --llm to have Claude write the wording (the decisions stay in code)
"""
import argparse
import asyncio
import difflib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from outreach import llm
from outreach.llm import DEFAULT_MODEL
from outreach.pipeline import pending_llm_call, process
from outreach.reader import ReadError, UnsupportedInput, decode_bytes, read_batch

FIELDS = ["channel", "send_at", "subject", "body", "cta", "next_action"]


def compare(result: dict, expected: dict) -> list[tuple[str, str, str]]:
    """(field, mark, detail) for each expected field. Exact fields: ✅/❌; text fields: similarity."""
    rows = []
    exp_msg = expected.get("next_message")
    got_msg = result.get("next_message")
    for f in FIELDS:
        if f == "next_action":
            e, g = expected.get("next_action"), result.get("next_action")
        else:
            e = (exp_msg or {}).get(f) if exp_msg is not None else None
            g = (got_msg or {}).get(f) if got_msg is not None else None
        if f in ("subject", "body") and isinstance(e, str) and isinstance(g, str):
            ratio = difflib.SequenceMatcher(None, e, g).ratio()
            mark = "✅" if ratio == 1 else "≈" if ratio >= 0.6 else "❌"
            rows.append((f, mark, "exact" if ratio == 1 else f"{ratio:.0%} similar"))
        else:
            rows.append((f, "✅" if e == g else "❌", "" if e == g else f"expected {json.dumps(e, ensure_ascii=False)}"))
    return rows


def print_readable(results: list[dict], records: list, show_compare: bool) -> None:
    for res, rec in zip(results, records):
        msg = res.get("next_message")
        meta = res.get("meta", {})
        print("─" * 78)
        print(f"{res['task_id']}   [{meta.get('record_type', '?')}, confidence {meta.get('confidence', '?')}, "
              f"{meta.get('mode', '?')}, {meta.get('latency_ms', '?')} ms]")
        if msg:
            print(f"  SEND via {msg['channel']} at {msg['send_at']}")
            if msg.get("subject"):
                print(f"  Subject: {msg['subject']}")
            for line in msg["body"].splitlines():
                print(f"  │ {line}")
            print(f"  CTA: {json.dumps(msg['cta'], ensure_ascii=False)}")
        else:
            print("  DO NOT SEND")
        print(f"  Next: {json.dumps(res['next_action'], ensure_ascii=False)}")
        print("  Why:")
        for w in res.get("why", []):
            print(f"    - {w}")
        for w in meta.get("warnings", []):
            print(f"    ! {w}")
        if show_compare and isinstance(rec, dict) and isinstance(rec.get("expected"), dict):
            print("  Compare to expected:")
            for f, mark, detail in compare(res, rec["expected"]):
                print(f"    {mark} {f:<12} {detail}")


async def run(records: list, args) -> list[dict]:
    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else None
    return await asyncio.gather(*(process(r, use_llm=args.llm, model=args.model, now=now) for r in records))


def cost_gate(records: list, args) -> None:
    """--llm: estimate the paid calls this run needs. Without explicit permission, stop loudly and say why."""
    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else None
    pending = [m for m in (pending_llm_call(r, args.model, now) for r in records) if m is not None]
    if not pending:
        if args.llm:
            print("[cost] --llm: every model answer is already cached; this run costs $0.", file=sys.stderr)
        return
    tokens_in = sum(llm.estimate_tokens(m) for m in pending)
    tokens_out = llm.OUTPUT_TOKENS_PER_CALL * len(pending)
    usd = llm.cost_usd(args.model, tokens_in, tokens_out)
    usd_txt = f"about ${usd:.4f}" if usd is not None else "an unknown amount (no price on file for this model)"
    per = f" (~${usd / len(pending):.5f} per call)" if usd else ""
    budget = args.budget if args.budget is not None else float(os.environ.get("BOT_LLM_BUDGET_USD") or 0)
    if budget > 0 and usd is not None and usd <= budget:
        print(f"[cost] {len(pending)} paid call(s) to {args.model}, estimated ${usd:.4f} "
              f"(within the ${budget:.2f} budget).", file=sys.stderr)
        llm.BUDGET_APPROVED = True
        return
    if llm.paid_calls_allowed():
        print(f"[cost] BOT_ALLOW_API_COST=1 (no limit): making {len(pending)} paid call(s) to {args.model}, "
              f"~{tokens_in:,} input + ~{tokens_out:,} output tokens, {usd_txt}.", file=sys.stderr)
        return
    over = (f"\n  Budget:     ${budget:.2f}, so this run is OVER the budget by about ${usd - budget:.4f}"
            if budget > 0 and usd is not None else "")
    bar = "=" * 78
    print(f"""{bar}
STOPPED: this run would incur AI API cost, and paid calls are turned off.

  Requested:  --llm (Claude writes the message wording)
  Model:      {args.model}
  Would make: {len(pending)} new API call(s), out of {len(records)} record(s)
              (records that won't be sent, and cached answers, are free)
  Estimated:  ~{tokens_in:,} input tokens + ~{tokens_out:,} output tokens
  Cost avoided: {usd_txt}{per}{over}

Nothing was processed and no API call was made.
  - Run without --llm: template mode is free, offline, deterministic, and matches the samples exactly.
  - To allow spending up to a limit: --budget 0.10 (or BOT_LLM_BUDGET_USD=0.10); runs over the limit still stop.
  - To accept any cost: BOT_ALLOW_API_COST=1. Both need ANTHROPIC_API_KEY.
Estimates are local (no API call) and use list prices; actual billing may differ slightly.
{bar}""", file=sys.stderr)
    sys.exit(3)


def main() -> None:
    ap = argparse.ArgumentParser(description="Decide the next outreach message for each record.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", "-i", help="JSONL, JSON array, or pretty-printed JSON objects")
    src.add_argument("--paste", action="store_true", help="read records from the terminal (end with Ctrl+D)")
    ap.add_argument("--output", "-o", help="write results as JSONL to this file")
    ap.add_argument("--llm", action="store_true", help="have Claude write the wording (decisions stay in code)")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"model for --llm (default {DEFAULT_MODEL})")
    ap.add_argument("--now", help="reference time, ISO 8601; sends never land before it")
    ap.add_argument("--compare", action="store_true", help="compare with each record's expected block, if present")
    ap.add_argument("--quiet", action="store_true", help="print only the JSONL block")
    ap.add_argument("--budget", type=float, help="--llm: allow paid calls if the estimated cost is at most this many USD")
    ap.add_argument("--only", help="show only records whose task_id contains this text (for demos)")
    args = ap.parse_args()

    try:
        if args.paste:
            print("Paste records, then press Ctrl+D (Ctrl+Z then Enter on Windows):", file=sys.stderr)
            text, notes = decode_bytes(sys.stdin.buffer.read())
        else:
            path = Path(args.input)
            if not path.is_file():
                sys.exit(f"Input file not found: {path}")
            text, notes = decode_bytes(path.read_bytes())
    except UnsupportedInput as e:
        print(f"Cannot read input: {e}. Nothing was processed.", file=sys.stderr)
        print("Provide the records as text: JSONL, a JSON array, or pasted JSON objects.", file=sys.stderr)
        sys.exit(2)
    batch = read_batch(text)
    records = batch.records
    for note in notes + batch.notes:
        print(f"[input] {note}", file=sys.stderr)
    if not records:
        sys.exit("No records found in the input.")

    if args.only:
        def label(r) -> str:  # task_id, or the whole record for shapes that have none (Level 3)
            if isinstance(r, ReadError):
                return r.task_id
            return str(r.get("task_id") or r.get("Task_ID") or json.dumps(r, ensure_ascii=False))
        keep = [i for i, r in enumerate(records) if args.only in label(r)]
        records = [records[i] for i in keep]
        if not records:
            sys.exit(f"No record's task_id contains {args.only!r}.")
    if args.llm:
        cost_gate(records, args)
    results = asyncio.run(run(records, args))
    seen: dict[str, int] = {}
    for r in results:
        seen[r["task_id"]] = seen.get(r["task_id"], 0) + 1
    for r in results:
        if seen[r["task_id"]] > 1:
            r["meta"].setdefault("warnings", []).append(f"task_id {r['task_id']!r} appears {seen[r['task_id']]} times in this batch")

    if not args.quiet:
        print_readable(results, records, args.compare)
        lat = sorted(r["meta"]["latency_ms"] for r in results)
        p95 = lat[min(len(lat) - 1, int(round(0.95 * (len(lat) - 1))))]
        sent = sum(1 for r in results if r["next_message"])
        bad = sum(1 for r in records if isinstance(r, ReadError))
        print("─" * 78)
        print(f"{len(results)} records: {sent} send, {len(results) - sent} do not send"
              + (f" ({bad} unreadable)" if bad else "") + f" | p95 latency {p95} ms (target 2000)")
        if args.compare:
            scored = [(res, rec) for res, rec in zip(results, records) if isinstance(rec, dict) and rec.get("expected")]
            if scored:
                exact = sum(all(m == "✅" for f, m, _ in compare(res, rec["expected"]) if f not in ("subject", "body"))
                            for res, rec in scored)
                print(f"Controllable fields (channel, send_at, cta, next_action) all match: {exact}/{len(scored)}")

    # Export without timing, so the same input always produces a byte-identical file.
    export = [{**r, "meta": {k: v for k, v in r["meta"].items() if k != "latency_ms"}} for r in results]
    lines = [json.dumps(r, ensure_ascii=False) for r in export]
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Wrote {len(lines)} results to {out}")
    print("=== BEGIN OUTPUT ===")
    print("\n".join(lines))
    print("=== END OUTPUT ===")


if __name__ == "__main__":
    main()

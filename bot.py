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
import sys
from datetime import datetime
from pathlib import Path

from outreach.llm import DEFAULT_MODEL
from outreach.pipeline import process
from outreach.reader import ReadError, read_records

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
    args = ap.parse_args()

    if args.paste:
        print("Paste records, then press Ctrl+D (Ctrl+Z then Enter on Windows):", file=sys.stderr)
        text = sys.stdin.read()
    else:
        text = Path(args.input).read_text(encoding="utf-8")
    records = read_records(text)
    if not records:
        sys.exit("No records found.")

    results = asyncio.run(run(records, args))

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

    lines = [json.dumps(r, ensure_ascii=False) for r in results]
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

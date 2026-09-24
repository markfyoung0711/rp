"""Learn the bot's decision rules from labelled examples, and test how well they generalize. No API calls.

  uv run learn.py plans/sample.jsonl                    # show what the examples teach, vs the current rules
  uv run learn.py plans/sample.jsonl --write            # save as config/learned.yaml (the bot uses it)
  uv run learn.py plans/sample.jsonl --eval             # leave-one-out: learn from the others, predict each one
  uv run learn.py plans/sample.jsonl tests/labelled_extra.jsonl   # more examples -> the rules change
Refuses any file whose path contains "hold" (hold-out data is for testing, never learning).
"""
import argparse
import asyncio
import difflib
import sys
from pathlib import Path

import yaml

from outreach import config
from outreach.learn import learn
from outreach.pipeline import process
from outreach.reader import UnsupportedInput, decode_bytes, read_batch

CONTROLLABLE = ("channel", "send_at", "cta")


def refuse_holdout(paths: list[str]) -> None:
    """Never learn from hold-out data: that would be training on the test set. Any path containing "hold" is refused."""
    held = [p for p in paths if "hold" in str(Path(p)).lower()]
    if held:
        bar = "=" * 78
        print(f"""{bar}
STOPPED: refusing to learn from hold-out data.

  File(s):   {", ".join(held)}
  Reason:    the name contains "hold". A hold-out set is kept back to test how the bot
             handles records it has never seen. Learning from it would be training on
             the test set and would make its score meaningless.

Nothing was learned and config/learned.yaml was not changed.
Score hold-out records instead:  uv run bot.py -i <file> --compare
{bar}""", file=sys.stderr)
        sys.exit(4)


def load(paths: list[str]) -> list[dict]:
    """Same input protections as bot.py: missing files, images/binary, encodings, pasted garbage."""
    recs: list[dict] = []
    for p in paths:
        path = Path(p)
        if not path.is_file():
            sys.exit(f"Input file not found: {path}")
        try:
            text, notes = decode_bytes(path.read_bytes())
        except UnsupportedInput as e:
            print(f"Cannot read {path}: {e}. Nothing was learned.", file=sys.stderr)
            sys.exit(2)
        batch = read_batch(text)
        for note in notes + batch.notes:
            print(f"[input] {path.name}: {note}", file=sys.stderr)
        unreadable = [r for r in batch.records if not isinstance(r, dict)]
        if unreadable:
            print(f"[input] {path.name}: {len(unreadable)} unreadable record(s) ignored", file=sys.stderr)
        recs += [r for r in batch.records if isinstance(r, dict)]
    return recs


def flat(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in (d or {}).items():
        if isinstance(v, dict):
            out.update(flat(v, f"{prefix}{k}."))
        else:
            out[f"{prefix}{k}"] = v
    return out


def predict(rec: dict) -> dict:
    return asyncio.run(process({k: v for k, v in rec.items() if k != "expected"}))


def score(out: dict, exp: dict) -> tuple[list[str], float]:
    """(mismatched controllable fields, body similarity)."""
    got, want = out.get("next_message") or {}, exp.get("next_message") or {}
    bad = [f for f in CONTROLLABLE if got.get(f) != want.get(f)]
    if out.get("next_action") != exp.get("next_action"):
        bad.append("next_action")
    if (want == {}) != (got == {}):
        bad.append("send/no-send")
    sim = difflib.SequenceMatcher(None, got.get("body") or "", want.get("body") or "").ratio() if want else 1.0
    return bad, sim


def main() -> None:
    ap = argparse.ArgumentParser(description="Learn decision rules from labelled examples.")
    ap.add_argument("files", nargs="+", help="JSONL/JSON files whose records carry an `expected` block")
    ap.add_argument("--write", action="store_true", help="save the learned rules to config/learned.yaml")
    ap.add_argument("--eval", action="store_true", help="leave-one-out evaluation (neutral rules + what the others teach)")
    args = ap.parse_args()

    refuse_holdout(args.files)
    recs = [r for r in load(args.files) if isinstance(r.get("expected"), dict)]
    if not recs:
        sys.exit("No labelled records (with an `expected` block) found.")

    current = flat({k: v for k, v in config.rules().items() if k in ("channels", "send_time", "next_action")})
    config.use_rules("neutral", {})
    learned, evidence = learn(recs)
    print("═" * 78)
    print(f"{evidence[0].upper()}  ({', '.join(args.files)})")
    for line in evidence[1:]:
        print("  " + line)
    changes = [(k, current.get(k), v) for k, v in flat({k: v for k, v in learned.items() if k != "cta"}).items()
               if current.get(k) != v]
    print("─" * 78)
    if changes:
        print("Compared with the rules the bot uses now:")
        for k, old, new in changes:
            print(f"  {k}: {old} → {new}")
    else:
        print("The learned rules match the rules the bot uses now.")

    if args.eval:
        print("─" * 78)
        print("LEAVE-ONE-OUT: learn from the other examples (starting from neutral rules), predict this one")
        ok = 0
        for i, rec in enumerate(recs):
            others = recs[:i] + recs[i + 1:]
            config.use_rules("neutral", {})
            rules_i, _ = learn(others)
            config.use_rules("neutral", rules_i)
            bad, sim = score(predict(rec), rec["expected"])
            ok += not bad
            print(f"  {rec.get('task_id', i):<32} {'✅ all controllable fields' if not bad else '❌ ' + ', '.join(bad)}   body {sim:.0%}")
        print(f"  → {ok}/{len(recs)} predicted correctly from the other examples alone")
        config.use_rules("neutral", learned)
        full = sum(not score(predict(r), r["expected"])[0] for r in recs)
        print(f"  (learned from all {len(recs)} and scored on the same {len(recs)}: {full}/{len(recs)}; not a real test, shown for contrast)")

    if args.write:
        out = {k: v for k, v in learned.items()}
        text = "# Learned by `uv run learn.py " + " ".join(args.files) + "` (do not edit; re-run learn.py)\n"
        text += "".join(f"# {line}\n" for line in evidence)
        text += yaml.safe_dump(out, sort_keys=True, allow_unicode=True)
        config.LEARNED_FILE.write_text(text)
        print(f"Wrote {config.LEARNED_FILE.relative_to(config.ROOT)}; the bot now uses these learned rules.")
    print("═" * 78)


if __name__ == "__main__":
    main()

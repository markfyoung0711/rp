"""Make a paste-ready problem report: version, command, the input record(s), the bot's output and the stats.

  uv run python scripts/report.py holdout.jsonl                 # whole file
  uv run python scripts/report.py holdout.jsonl --only task_7   # one record
  uv run python scripts/report.py holdout.jsonl --note "expected email, got sms"

Writes out/report.txt and prints it. Personal data in the input is included, so share it only where the
input itself may go (e.g. this repo's Claude Code session), not publicly.
"""
import argparse
import datetime
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sh(*cmd: str) -> str:
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return (r.stdout + r.stderr).rstrip() + f"\n[exit code {r.returncode}]"


def main() -> None:
    ap = argparse.ArgumentParser(description="Paste-ready report of a bot run.")
    ap.add_argument("file")
    ap.add_argument("--only", help="limit to records whose task_id contains this text")
    ap.add_argument("--note", default="", help="what looked wrong, in your words")
    args = ap.parse_args()

    path = Path(args.file)
    cmd = ["uv", "run", "bot.py", "-i", str(path)] + (["--only", args.only] if args.only else [])
    raw = path.read_bytes()[:20000] if path.is_file() else b"(file not found)"
    try:
        sample = raw.decode("utf-8")
    except UnicodeDecodeError:
        sample = f"(binary or non-UTF-8 input, {len(raw)} bytes shown as repr)\n{raw[:400]!r}"
    if args.only and path.is_file():
        keep = [line for line in sample.splitlines() if args.only in line]
        sample = "\n".join(keep) or sample

    report = "\n".join([
        "=== BOT PROBLEM REPORT ===",
        f"time:    {datetime.datetime.now().isoformat(timespec='seconds')}",
        f"version: {sh('git', 'describe', '--tags', '--always', '--dirty').splitlines()[0]}",
        f"note:    {args.note or '(none)'}",
        f"command: {' '.join(cmd)}",
        "",
        "--- input (first 20 KB, or the matching lines) ---",
        sample,
        "",
        "--- output ---",
        sh(*cmd),
        "=== END REPORT ===",
    ])
    out = ROOT / "out" / "report.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text(report + "\n", encoding="utf-8")
    print(report)
    print(f"\n(saved to {out.relative_to(ROOT)}; paste everything between the === lines into the Claude Code session)",
          file=sys.stderr)


if __name__ == "__main__":
    main()

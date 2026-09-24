"""Automated part of plans/code-review-checklist.md. Prints PASS/FAIL per check; exit 1 on any P0 failure.

  uv run python scripts/run_checks.py            # fast checks (no network)
  uv run python scripts/run_checks.py --full     # + clean clone install and --llm offline fallback
"""
import asyncio
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from outreach.pipeline import process  # noqa: E402
from outreach.reader import read_records  # noqa: E402

SAMPLES = ROOT / "plans" / "sample.jsonl"
EDGES = ROOT / "tests" / "edge_cases.jsonl"
results: list[tuple[str, str, bool, str]] = []


def check(prio: str, name: str, ok: bool, detail: str = "") -> None:
    results.append((prio, name, ok, detail))


def sh(*cmd: str, env: dict | None = None, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})})


def run(records: list) -> list[dict]:
    async def go():
        return await asyncio.gather(*(process(r) for r in records))
    return asyncio.run(go())


def main(full: bool) -> int:
    samples = [json.loads(line) for line in SAMPLES.read_text().splitlines() if line.strip()]

    # A. Sample diff: every graded field
    outs = run([{k: v for k, v in s.items() if k != "expected"} for s in samples])
    for s, o in zip(samples, outs):
        diff = [f for f in ("channel", "send_at", "subject", "body", "cta")
                if (o["next_message"] or {}).get(f) != s["expected"]["next_message"].get(f)]
        if o["next_action"] != s["expected"]["next_action"]:
            diff.append("next_action")
        check("P0", f"sample {s['task_id']} matches", not diff, ", ".join(diff))

    # A. Hardcoding: sample literals must not appear in code (config facts are allowed)
    code = "".join(p.read_text() for p in [ROOT / "bot.py", *(ROOT / "outreach").glob("*.py")])
    hits = [w for w in ("Taylor", "Oak Ridge", "oakridge", "prospect_welcome_day0", "long_horizon_day3") if w in code]
    check("P0", "no sample literals in code", not hits, ", ".join(hits))
    renamed = copy.deepcopy(samples[0])
    renamed.pop("expected")
    renamed["input"].update(property_name="Maple Court", profile={"first_name": "Priya"})
    body = run([renamed])[0]["next_message"]["body"]
    check("P0", "renamed record carries no sample values", "Taylor" not in body and "Oak Ridge" not in body, body[:60])

    # A. Determinism: byte-identical export
    with tempfile.TemporaryDirectory() as d:
        a, b = Path(d, "a.jsonl"), Path(d, "b.jsonl")
        for p in (a, b):
            sh("uv", "run", "bot.py", "-i", str(SAMPLES), "--quiet", "-o", str(p))
        check("P0", "byte-identical output across runs", a.read_bytes() == b.read_bytes())

    # A/C. Channel matrix, no-send, fail closed
    base = copy.deepcopy(samples[0])
    base.pop("expected")
    def variant(**kw):
        r = copy.deepcopy(base)
        r.update(kw)
        return r
    cases = {
        "voice only -> no send": (variant(channel_preferences=["voice"], consent={"voice_opt_in": True}), None),
        "voice first, sms second -> sms": (variant(channel_preferences=["voice", "sms"], consent={"voice_opt_in": True, "sms_opt_in": True}), "sms"),
        "preferred not consented -> fallback": (variant(consent={"sms_opt_in": False, "email_opt_in": True}), "email"),
        "no consent -> no send": (variant(consent={"sms_opt_in": False, "email_opt_in": False}), None),
        "consent null -> no send": (variant(consent=None), None),
        "consent 'maybe' -> no send": (variant(consent={"sms_opt_in": "maybe"}), None),
    }
    for name, (rec, want) in cases.items():
        o = run([rec])[0]
        got = (o["next_message"] or {}).get("channel")
        shape_ok = want is not None or (o["next_message"] is None and "reason" in o["next_action"])
        check("P0", f"channel: {name}", got == want and shape_ok, f"got {got}")

    # B. Formats and isolation
    one = SAMPLES.read_text().splitlines()[0]
    check("P0", "JSON array input", len(read_records(json.dumps(samples))) == 2)
    check("P0", "pretty-printed input", len(read_records(json.dumps(samples[0], indent=2) * 2)) == 2)
    check("P0", "no trailing newline", len(read_records(SAMPLES.read_text().rstrip("\n"))) == 2)
    mixed = run(read_records(one + "\n{broken\n" + one))
    check("P0", "malformed record isolated", [bool(m["next_message"]) for m in mixed] == [True, False, True])
    garbage = sh("uv", "run", "bot.py", "-i", str(ROOT / "tests" / "garbage_inputs.txt"), "--quiet")
    sent = sum(1 for line in garbage.stdout.splitlines() if line.startswith("{") and '"next_message": {' in line)
    check("P0", "garbage input: 13 of 14 records recovered, exit 0", garbage.returncode == 0 and sent == 13, f"sent {sent}")
    utf16 = sh("uv", "run", "bot.py", "-i", str(ROOT / "tests" / "garbage_utf16.jsonl"), "--quiet")
    check("P0", "UTF-16 input file", utf16.returncode == 0 and utf16.stdout.count('"next_message": {') == 2)
    edge_out = sh("uv", "run", "bot.py", "-i", str(EDGES), "--quiet")
    check("P0", "edge cases run, exit 0", edge_out.returncode == 0, edge_out.stderr[-200:])

    # C. Safety on every sent message in samples + edges
    all_out = run(read_records(SAMPLES.read_text() + EDGES.read_text()))
    phone = re.compile(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
    email = re.compile(r"[\w.+-]+@[\w-]+\.\w+")
    steer = re.compile(r"\b(famil|kids?|children|adults only|religio|disab)", re.I)
    bad = []
    for o in all_out:
        m = o["next_message"]
        if not m:
            continue
        if "STOP" not in m["body"]:
            bad.append(f"{o['task_id']}: no opt-out")
        if phone.search(m["body"]) or email.search(m["body"]):
            bad.append(f"{o['task_id']}: contact details")
        if steer.search(m["body"] + (m["subject"] or "")):
            bad.append(f"{o['task_id']}: steering term")
        hour = int(m["send_at"][11:13])
        if not 8 <= hour < 21:
            bad.append(f"{o['task_id']}: send hour {hour}")
    check("P0", "opt-out, PII, steering, send window on all messages", not bad, "; ".join(bad))

    # C. PII: planted personal data must not appear anywhere in the output (only the first name, in the greeting)
    pii_out = sh("uv", "run", "bot.py", "-i", str(ROOT / "tests" / "pii_cases.jsonl"), "--quiet")
    planted = ["Okafor", "taylor.okafor@example.com", "555-0187", "555 0187", "123-45-6789", "1990-04-12", "1200 Elm", "4111 1111"]
    leaked = [x for x in planted if x in pii_out.stdout]
    check("P0", "PII: planted email/phone/SSN/DOB/address/card never in output", not leaked, ", ".join(leaked))

    # D. Static
    check("P0", "pytest", sh("uv", "run", "pytest", "-q").returncode == 0)
    ruff = sh("uv", "run", "ruff", "check", "outreach", "bot.py", "tests", "--select", "E9,F")
    check("P0", "ruff (errors: syntax, undefined names, unused imports)", ruff.returncode == 0, ruff.stdout[-300:])
    secrets = sh("git", "grep", "-nE", r"sk-ant-[A-Za-z0-9_-]{10,}")
    check("P0", "no API keys in repo", secrets.returncode == 1, secrets.stdout[:200])
    tz = sh("uv", "run", "python", "-c", "from zoneinfo import ZoneInfo; ZoneInfo('America/Chicago'); import tzdata")
    check("P0", "time-zone data available", tz.returncode == 0, tz.stderr[-200:])
    check("P1", "README present", (ROOT / "README.md").exists())
    nocost = sh("uv", "run", "bot.py", "-i", str(EDGES), "--llm", "--quiet", env={"BOT_ALLOW_API_COST": "", "ANTHROPIC_API_KEY": "bad"})
    check("P0", "--llm without permission stops loudly (exit 3) and names the cost avoided",
          nocost.returncode == 3 and "Cost avoided: about $" in nocost.stderr and "BEGIN OUTPUT" not in nocost.stdout,
          nocost.stderr[-300:])
    over = sh("uv", "run", "bot.py", "-i", str(EDGES), "--llm", "--budget", "0.001", "--quiet",
              env={"BOT_ALLOW_API_COST": "", "ANTHROPIC_API_KEY": "bad"})
    check("P0", "--budget: a run over the limit stops (exit 3) and says by how much",
          over.returncode == 3 and "OVER the budget" in over.stderr, over.stderr[-300:])

    if full:
        # E. LLM offline fallback: a bad key must still produce complete output (auth fails -> no charge)
        o = sh("uv", "run", "bot.py", "-i", str(SAMPLES), "--llm", "--compare", env={"ANTHROPIC_API_KEY": "bad", "BOT_ALLOW_API_COST": "1"})  # bad key: rejected, never billed
        check("P0", "--llm with bad key falls back, samples still match", "all match: 2/2" in o.stdout, o.stderr[-200:])
        # D/F. Clean clone install from the README commands
        with tempfile.TemporaryDirectory() as d:
            sh("git", "clone", "-q", str(ROOT), d)
            sh("uv", "sync", "-q", cwd=Path(d))
            o = sh("uv", "run", "bot.py", "-i", "plans/sample.jsonl", "--compare", cwd=Path(d))
            check("P0", "clean clone: uv sync + README command", "all match: 2/2" in o.stdout, o.stderr[-200:])

    width = max(len(n) for _, n, _, _ in results)
    for prio, name, ok, detail in results:
        print(f"{'PASS' if ok else 'FAIL'}  {prio}  {name:<{width}}  {'' if ok else detail}")
    failed = [r for r in results if not r[2] and r[0] == "P0"]
    print(f"\n{len(results) - len([r for r in results if not r[2]])}/{len(results)} passed; P0 failures: {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main("--full" in sys.argv))

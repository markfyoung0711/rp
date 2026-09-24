---
name: run-checks
description: Run the code-review checklist against the outreach bot. It validates the rules and branding, runs the automated checks script, then the manual checklist items, and reports findings (at most ~10) with severity, a reproduction, expected vs actual, and whether each is safe to auto-fix. Triggered by "run checks", "run the checks", "run the checklist", "check the bot", "pre-demo check", "are we demo ready", "regression check".
allowed-tools: Bash, Read, Edit, Write
---

# run-checks: verify the bot against the code-review checklist

The checklist is [`plans/code-review-checklist.md`](../../../plans/code-review-checklist.md). Results from earlier runs are in `plans/code-review-results.md`. The graded fields to protect are channel, send_at, subject, CTA, next_action and body similarity.

## 0. Validate the configuration: rules and branding (always, first)

```bash
uv run python scripts/validate_rules.py --brand
```

- **What it checks:**
  - **Rules:** `config/rules.yaml` merged with `config/learned.yaml`. Types and ranges; send hours inside the legal 8:00-21:00 window (it may be narrowed, never widened); STOP present; no personal or protected fields in the AI prompt allow-list; CTA names and purposes.
  - **Properties and branding:** `config/properties.yaml`. Time zones, tour days, `https` links, and each property's `brand` block, which overrides `brand_default` in `rules.yaml`.
  - **Brand preview:** renders a tour message for every property on SMS, email and voice, and brand-checks each one. It covers display name, voice intro, banned phrases, emoji, shouting and length.
- **Result:** exit 0 and `VALID`, or exit 1 with every problem listed.
- **If anything is invalid, stop and fix the configuration first.** The bot and `learn.py` also refuse to run on invalid rules (exit 6).
- Run it after **any** rule or brand change, whether a person or an AI made it.

## 1. Automated checks (always)

```bash
uv run python scripts/run_checks.py          # fast, no network (~15 s)
uv run python scripts/run_checks.py --full   # adds the --llm bad-key fallback and a clean-clone install (~1 min)
```

It prints PASS/FAIL per check and exits 1 on any P0 failure. It covers:
- **A:** the sample diff on every graded field, sample literals in code, a renamed record, byte-identical output, the channel matrix, no-send shape and failing closed
- **B:** JSONL / JSON array / pretty-printed input, no trailing newline, malformed-record isolation, edge cases exiting 0
- **C:** opt-out, PII, steering terms and the send window on every message
- **D:** pytest, ruff errors (`E9,F`), API-key scan, time-zone data, README present
- **Config:** the validator above, including the brand preview; the decision table (all 120 consent × preference combinations match the policy)
- **`--full`:** LLM offline fallback, clean-clone install

Use `--full` before any demo or after a dependency change.

## 2. Manual items (the script does not cover these)

Check these by running the bot and reading the output:
- **A P1:** send time with a missing or invalid time zone and across a DST boundary; horizon at 45 vs 46 days; past or missing move date; resident or renewal records (no tour push, no price).
- **B P0:** odd inputs (nulls, wrong types, very long names, names in other scripts). Use `tests/edge_cases.jsonl` plus ad-hoc variants.
- **C P0:** an injection string or URL in the name or profile is not repeated; `has_children` / `religion` in the profile never shows up.
- **E (only if `--llm` is in the demo):** latency (`uv run bot.py -i tests/edge_cases.jsonl --llm`, p95 under 2000 ms), and whether the wording invents facts (no dates, amenities or availability beyond `config/properties.yaml`).
- **F:** every claim in `README.md` is runnable; the README commands work exactly as written.
- **G:** `uv run bot.py -i <file> -o out/x.jsonl` runs with no prompts; the export copies cleanly.

## 3. Report

- At most ~10 findings. For each: **severity** (P0/P1), **reproducing input**, **expected vs actual**, **safe to auto-fix** or **needs a human decision**.
- Append the run to `plans/code-review-results.md` (date, pass count, findings).

## 4. Applying fixes (the checklist's rules)

1. Make sure the last known-good state is committed or tagged (`git tag` e.g. `v0.1.x`).
2. Fix only findings that have a failing reproduction. Never change graded behavior without one.
3. After each fix: `uv run python scripts/run_checks.py` and `uv run bot.py -i plans/sample.jsonl --compare`. If any sample field changes, revert the fix.
4. One review round only. **Freeze changes about an hour before the demo** (11:00 CT on 2026-09-24).
5. Commit with a message listing the fixed findings, then push.

If only 30 minutes remain: run `scripts/run_checks.py --full` plus the section F README check.

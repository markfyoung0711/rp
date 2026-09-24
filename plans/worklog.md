# Work Log

Times are US Central (CDT). Delivery deadline: **2026-09-24, 12:00 noon** (D-021).

## Phase 1 — Spec and solution development (complete)

| When | What | Artifacts |
|---|---|---|
| 09-18 | Pre-assignment prep: synthetic JSONL fixtures, JSONL profiler, predictions of what the assignment would contain | now in `archive/` (`data/samples/`, `profile_jsonl.py`, `guessing.md`; commit 31c5117) |
| 09-24, early | Assignment captured: the problem statement and `sample.jsonl` (2 records) | `plans/spec.md`, `plans/sample.jsonl` |
| | Project skills copied from `../estimator` | `.claude/skills/` |
| | GitHub issues #1–#10 created: intake, understanding, prior art + competitive intel + UX prior art, detailed spec, add-on agents/tests, alternatives, UX, demo data, independent review, external reviews | github.com/markfyoung0711/rp/issues |
| | Use cases (UC-01–03 original; UC-10–50 add-on), actor walkthroughs, sentiment tracking, the combined design (DB, UX, bot, APIs, security/PII, auth, deployment, legal guardrails, demo data) | `plans/use-cases.md`, `plans/actors.md`, `plans/design.md` |
| | Decision register started, marking ORIGINAL / ANALYSIS / ADD-ON (MFY) | `plans/decisions.md` (D-001 to D-020) |
| | Combined solution document for SME review, generated from the sources and the live issues | `plans/solution.md`, `plans/build_solution.py` |
| | Spec split: the pure assignment vs our analysis | `plans/spec.md`, `plans/sample-analysis.md` |
| | Deadline and the 12-output hold-out requirement added | `plans/spec.md` banner, D-021, `plans/holdout-prep.md` |
| 03:39 | Planning docs committed and pushed | e697cb5 |

## Phase 2 — Two critical reviews (complete)

| When | What | Artifacts |
|---|---|---|
| 03:21 | Review 1 of 2 started: Claude Sonnet 5, independent session | #9 comment |
| 03:39 | Review 1 received: 16 findings (F-01 to F-16), 13 gaps in the spec (S-1 to S-13); blocker F-01 showed the send-time rule was wrong | `plans/review.md`; D-022 to D-030 |
| 03:41 | Review 2 of 2 started | #9 comment |
| 03:45 | Review 2 received: Gemini (Google AI Mode), as an SME. Reconciled with review 1 | `plans/review.md` § Reconciliation; D-031 to D-036; 9e23f85 |
| 03:48 | Review 2 addendum: a core pipeline blueprint | D-037; 969df84 |
| 03:49 | Review 1 addendum: core focus in priority order. The two blueprints merged into one build spec | D-038 (supersedes D-037); 7aa629f |
| 03:50 | Review 2's reference `bot.py` saved and code-reviewed: it fails sample 1's `send_at` and uses a retired model ID. Kept as a reference, not used as the base | `reference/bot_gemini.py`, G-01 to G-13, D-039; 892fa37 |
| 03:52 | Issues #1, #2, #4 and #9 closed; this log written | `plans/worklog.md` |

## Phase 3 — Build (core complete)

| When | What | Artifacts |
|---|---|---|
| ~03:55 | Scope discussion: what a bot is, the core functionality, the operator's role in the demo, the demo steps | `plans/bot-explainer.md`; demo runbook artifact |
| ~04:05 | Levels 1/2/3 for unseen records agreed | D-040 |
| ~04:10 | Project moved to uv | `pyproject.toml`, `uv.lock`; D-041 |
| 04:15 | Bot core: reader (JSONL / array / pretty-printed; bad records isolated), normalizer (Level 2/3), deterministic decisions, templates with fixed opt-out and CTA, guards, optional LLM writer, CLI. Both samples match every field | `bot.py`, `outreach/`, `config/`; 5e06c7c |
| 04:18 | 16 edge cases across Levels 1–3, plus 6 pytest tests | `tests/`; 3281bfa |
| 04:20 | LLM mode fixed and tightened: SDK 1.x has no `temperature` kwarg, strict schema off (+14 s), prompt limited to facts on file; p95 ~1.6 s | D-042; 6eec60f |

**How to run:** `uv run bot.py -i plans/sample.jsonl --compare` · `uv run bot.py -i tests/edge_cases.jsonl` · add `--llm` for model wording · `uv run pytest`.

## Key outcomes

- **The build spec is D-038:** a stateless batch CLI, JSONL in → one output per record. It has a template baseline plus an optional LLM mode (the samples as few-shot examples). Opt-out wording, CTA and `next_action` are fixed code. Send time = local `last_interaction` + the `dayN` offset, at 09:00 for SMS or 10:00 for email, rolled forward if not after the last interaction. Guards and a property-facts file are included, and the output is deterministic. There is a combined export plus a readable per-record view.
- **Deferred ("designed, not built"):** database, auth, the three-pane UI, sentiment, external reviews, voice, inbound handling. Issues #3, #5, #6, #7, #8 and #10 stay open.
- **Decisions awaiting Mark's acceptance:** the ones marked *recommended* in `decisions.md`.

## Issue status

| Issue | Status |
|---|---|
| #1 Intake | Closed. Inputs are in `plans/`; the questions for the interviewer are in `review.md` §8 |
| #2 Understanding | Closed. See `sample-analysis.md`, `holdout-prep.md` and the reviews; the send-time rule was corrected (D-023) |
| #3 Prior art / competitive intel / UX prior art | Open, labelled `deferred` |
| #4 Detailed spec | Closed. `design.md` / `solution.md`, and the build spec D-038 |
| #5 Add-on agents and tests | Open. 16 edge cases + tests done; agents and the REQ/ADD table remain |
| #6 Alternatives | Open. Template and LLM modes are built side by side; the engineer session remains |
| #7 UX | Open, labelled `deferred` |
| #8 Demo data | Open, labelled `deferred` |
| #9 Independent reviews | Closed. Both reviews done |
| #10 External reviews | Open, labelled `deferred` (D-030) |
| #11 Core bot v1 | Closed. Tagged **v0.1.0** |
| #12 Core hardening v0.2 | Closed. Tagged **v0.2.0** (ingestion, PII, cost guard, stats, checks) |

## Next

Rehearse with the runbook; optional: a plain paste-and-copy web page; review the model-mode wording; update `solution.md` with a "built vs designed" table.

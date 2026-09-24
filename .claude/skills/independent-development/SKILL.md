---
name: independent-development
description: Autonomous development mode — analyze the task, plan, work in tracked steps, test, and produce a change/effect summary. Triggered by phrases like "do independent development", "independent development on X", "work autonomously on X", "autonomous mode", "do this independently", "auto-mode for X".
allowed-tools: Bash, Read, Edit, Write, Grep, Glob, TaskCreate, TaskGet, TaskUpdate, TaskList, Agent
---

# Independent Development Mode

Run a full autonomous development cycle on a task: understand → plan → execute → test → summarize, with durable tracking that survives session breaks.

This mode does NOT bypass authorization for risky operations. Commits, pushes, destructive git ops, and external-effect actions still require explicit user OK.

## When invoked

The user has handed off a task and expects autonomous progress. Treat the user as available for clarifying questions but not for moment-to-moment guidance. Match that pace: pause for genuine ambiguity, push through the rest.

## 1 · Understand before acting

Before any code change:

- Read `CLAUDE.md` if not already loaded this session.
- Read the most relevant `docs/claude-context/*.md` files for the task domain — for code changes, at minimum `01-architecture.md` and `03-conventions.md`.
- Restate the task back in 2–4 sentences (goal, scope, success criteria).
- If the restatement reveals genuine ambiguity that materially changes approach, ask ONE focused clarifying question. Otherwise proceed.

## 2 · Capture baseline state

Open a checkpoint file at `docs/dev-sessions/<task-slug>-<YYYY-MM-DD>.md` (create the directory if needed). Slug should be terse and lowercase (e.g., `add-pvc-schema-2026-04-25.md`). Header:

```
# Independent Development — <task title>

**Started:** <YYYY-MM-DD HH:MM>
**Goal:** <one sentence>

## Baseline
- Branch: <git rev-parse --abbrev-ref HEAD>
- HEAD: <git rev-parse --short HEAD>
- Pre-existing dirty files: <git status --porcelain>
```

The pre-existing dirty list matters: those files were dirty before you started, so they're NOT yours to attribute on the diff at the end. Investigate any unexpected dirty file before assuming it's user work-in-progress.

## 3 · Plan and seed task tracking

Append to the checkpoint:

```
## Plan
1. <step>
2. <step>
…

## Scope
- IN scope: <what you will touch>
- OUT of scope: <what you will not touch — list explicitly>

## Success criteria
- <observable, testable thing 1>
- <observable, testable thing 2>

## Known risks
- <potential blocker / unknown>
```

Then call `TaskCreate` to seed the work as discrete tasks. Mark each `in_progress` when starting and `completed` immediately when done. Don't batch.

## 4 · Execute incrementally

For each task:

- Do one logical unit of work
- After the unit is done, append to the checkpoint a brief "what + why" entry with file paths
- Mark the task `completed`
- Move to the next

If you discover work outside the original plan that's required:

- Append a **scope expansion** note to the checkpoint with the why
- Add it as a new task and continue
- If the expansion materially changes the goal, **stop and ask**

## 5 · Test what changed

Before declaring complete, run real checks. Pick what fits the change:

- **Python code** — `uv run pytest <area>` if tests exist; the project's broader test suite if the change is wider; type-check via the project's convention if any
- **Scripts** — execute the happy path; check stderr; confirm output artifacts exist and look right
- **Data work** — spot-check input vs. output; row counts before/after; sample records
- **API/UI changes** — start the dev server, exercise the endpoints / load the page, watch logs
- **SQL/parquet** — confirm schema unchanged unless intended; sample query results

Capture the actual command output (not a paraphrase) in the checkpoint under a `## Tests` section.

**If a test fails:** investigate root cause and fix it. Do NOT skip, comment out, or mock-around the failure to make it pass. If the root cause is genuinely outside the task's scope, stop and ask.

## 6 · Track the diff precisely

When work is done:

```
git status --porcelain
git diff --stat
```

Append to the checkpoint a `## Files changed` section. One line per file: `path/to/file.py — what changed and why`.

Cross-check against the baseline pre-existing dirty list. Anything modified that you don't recognize: investigate before declaring done.

## 7 · Summarize change and effect

Final section of the checkpoint:

```
## Summary

**Goal:** <restated>

**What changed (files):**
- <file>: <one line>
- …

**What was tested + result:**
- <test command>: pass/fail + output excerpt
- …

**Behavioral effect:**
- What is now true that wasn't before, OR what is no longer true that was before. Be concrete: a row count, an endpoint that now returns X, a new artifact at path Y.

**Deliberately NOT done:**
- <thing>: <reason>

**Discoveries outside scope:**
- <thing>: <suggested follow-up>

**Followups:**
- [ ] <suggested next action 1>
- [ ] <suggested next action 2>
```

Also produce a brief in-chat summary (≤8 lines) so the user can scan it without opening the checkpoint.

## Hard rules during this mode

- Never commit, push, or run destructive git operations (`git reset --hard`, `git push --force`, branch delete, `git clean -f`, etc.) without explicit user authorization. Save changes to working tree only.
- Never skip git hooks (`--no-verify`) or bypass signing.
- Never run two `Agent` calls concurrently — strict single-threaded agent execution per `feedback_single_agent.md`. Agent in this mode is for delegated **research only**; do not let it write code while you're also writing code.
- Always `uv run` for Python. Never `python3` directly. Never `source .venv/bin/activate`.
- Never put `#` comments inside Bash tool call commands — write a script file if you need comments.
- Place new Python under `scripts/` (run-once tools) or `src/` (importable code) per `CLAUDE.md`. No new top-level directories without justification.
- Save competitor / vendor analyses under `docs/competitive_analysis/`.
- Don't use the words "atomic" or "prior art" in any estimator-facing output (use "itemized" / "single-line" and "existing approaches" / "what's out there already" instead).
- Update `docs/claude-context/04-decisions-log.md` if you make a non-trivial design decision while working.
- Add to `docs/claude-context/05-open-questions.md` if you park an unresolved question rather than answer it.

## Stop and ask when

- Ambiguity materially changes the approach (not just minor preferences)
- A destructive operation is needed
- A test fails with no clear root cause inside the task's scope
- Scope drifts materially from the original goal
- Two valid approaches exist with very different long-term implications
- An external-effect action is required (sending email, creating a PR, calling a paid API at scale)

## Resumption

If a session ends mid-task:

- The checkpoint at `docs/dev-sessions/<task-slug>-<date>.md` is the resume point. It is durable.
- `TaskList` state may not survive across sessions; the checkpoint is the source of truth.
- On resume: read the checkpoint, run `git status` and `git diff` against the baseline HEAD recorded in the checkpoint, recreate the `TaskCreate` list from the plan, then continue.

## User-facing prompt template

For best results, the user can supply:

```
do independent development on:
  goal:        <what to accomplish, one sentence>
  context:     <relevant files / areas / docs>
  constraints: <what NOT to touch, hard limits>
  done when:   <observable success condition>
```

Only `goal` is required; the other three reduce clarifying-question round-trips.

## What this mode gives the user

- **Resumability** — the checkpoint lets a future session continue cleanly even if the current one ends abruptly
- **Auditable trail** — what was done, in what order, with what justification (better than reading commit messages after the fact)
- **Scope discipline** — the "deliberately NOT done" section forces surfacing of scope decisions and potential creep
- **Test discipline** — running tests is in the lifecycle, not optional

## What this mode does NOT do

- Bypass SME review on judgment calls (e.g., schema decisions still need Jeff's redline)
- Auto-commit (still requires explicit authorization)
- Make work go faster — same effort, just visible and tracked

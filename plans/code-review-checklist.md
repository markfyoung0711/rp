# Code Review Checklist: Context-Aware Messaging Bot

**Deadline context:** the demo is due 2026-09-24 at 12:00 noon CST. At the interview, 12 unseen (hold-out) records must be run and the outputs exported live.

## Instructions for the reviewer

- **Read-only.** Report problems. Do not apply refactors or new features.
- **Run things, don't just read.** Execute the cases below and report actual outputs.
- **Scope:** hardcoded sample answers, crashes, wrong graded fields, consent and opt-out failures, invented facts, and README claims that don't match behavior. Skip style, naming, and restructuring.
- **Legend:** **P0** = run before noon. **P1** = run if time allows.
- **Graded fields to protect:** channel, send time, subject, CTA, next action, and body similarity.

---

## A. Spec and behavior (highest value)

- [ ] **P0 Sample diff.** Run both samples and compare every field to `expected`: channel, send time, subject, CTA, next action, body similarity.
- [ ] **P0 Hardcoding test.** Change the first name, property, dates, and task_id and re-run. Search the code for literals such as "Oak Ridge," "Taylor," and the sample task_ids. Nothing from the samples should appear in the output.
- [ ] **P0 Determinism.** Run the same file twice. Outputs must be identical byte for byte.
- [ ] **P0 Channel matrix.** Test every combination of preference order and consent: voice-only, voice first with SMS second, preferred channel not opted in. Skipped channels must be logged with a reason.
- [ ] **P0 No-send.** With no consent anywhere, the output must be a no-send with a reason, in a consistent shape.
- [ ] **P1 Send-time cases.** Rollover when the send hour has already passed, missing time zone, invalid time zone, daylight-saving boundary, a day offset in the task_id, and no offset.
- [ ] **P1 Boundaries.** Short/long horizon threshold at the edge, a past move date, and a missing move date.
- [ ] **P1 Other stages and personas.** A resident or renewal record: no tour push and no price content.

## B. Robustness (what the hold-out tests)

- [ ] **P0 Bad input.** Missing fields, null values, wrong types, unknown enum values, extra unknown fields, empty strings, very long names, and unicode names.
- [ ] **P0 File formats.** JSONL, a JSON array, pretty-printed objects, an empty file, and a file with no trailing newline.
- [ ] **P0 Isolation.** One malformed record in the middle must not stop the others. Check the exit code and error message.
- [ ] **P1 Duplicates.** A duplicate `task_id`, and the same person appearing twice.

## C. Safety and compliance

- [ ] **P0 Opt-out.** Every sent message contains channel-appropriate opt-out wording, produced deterministically.
- [ ] **P0 Fail closed.** If consent is missing, ambiguous, or malformed, nothing is sent.
- [ ] **P0 Injection.** Put "ignore previous instructions" or a URL in the name and profile fields. The message must not follow or repeat it.
- [ ] **P0 Invented facts.** For an unknown property, no specific amenities, tour days, or links appear.
- [ ] **P0 PII scan.** Scan outputs for phone numbers, emails, and ID-like patterns that should not be there.
- [ ] **P0 Protected traits.** Add fields such as `has_children` or `religion` to the profile. They must not appear in the message.
- [ ] **P1 Word list.** Scan output text for steering language such as "families," "adults only," and "no kids."
- [ ] **P1 Send window.** No send falls outside the allowed local hours.

## D. Static and quality

- [ ] **P0 Lint and type check.** Run the standard tools for the language (for Python, for example ruff or flake8, and mypy). Fix errors, not style.
- [ ] **P0 Clean install.** In a fresh environment, install and run from the README alone. Look for missing or unpinned dependencies.
- [ ] **P0 Time-zone data.** Confirm time-zone lookups work on the demo machine. Some systems, especially Windows, lack the data by default.
- [ ] **P0 Secrets.** Scan the repo and logs for API keys.
- [ ] **P1 Swallowed errors.** Look for bare exception handlers that hide failures, plus dead code and unused imports.
- [ ] **P1 Logging.** Logs must not contain PII or full message bodies where they should not.

## E. LLM path (only if a model writes any wording)

- [ ] **P0 Offline fallback.** Turn the API off or use a bad key. The system must still produce complete, valid output.
- [ ] **P0 Timeouts.** Every model call has a timeout and a fallback.
- [ ] **P0 Compliance text is not model-controlled.** The opt-out line and CTA come from fixed logic. Model output must not be able to remove them.
- [ ] **P1 Output validation.** Model output is checked before use, with a fallback on failure.
- [ ] **P1 Prompt contents.** The prompt includes only the allowed fields.
- [ ] **P1 Latency and usage.** Time it per record against the 2-second target, and estimate calls per run so usage limits are not burned.

## F. Documentation honesty

- [ ] **P0 Claims vs behavior.** Every feature in the README or the "built vs designed" table is runnable, or moved to "designed."
- [ ] **P0 README commands.** Run them exactly as written from a clean checkout.
- [ ] **P1 Assumptions.** The key assumptions are written down: send-time rule, source of property facts, horizon threshold, no-send output shape, AI-disclosure handling, consent semantics, voice deferred.

## G. Demo readiness

- [ ] **P0 One command** runs everything with no interactive prompts.
- [ ] **P0 Export format.** A combined output file and a readable per-record view exist and copy cleanly.
- [ ] **P0 Timing.** The 12-record run finishes quickly, and also with no network.
- [ ] **P1 Rerun.** It works twice in a row with no leftover state.

---

## Ground rules for reporting

- At most about 10 findings.
- For each finding: **severity**, an **input that reproduces it**, **expected vs actual result**, and whether it is **safe to auto-fix** or **needs a human decision**.
- Do not touch graded behavior without a failing reproduction.

## Rules for applying feedback

1. Save a known-good copy before any change.
2. Apply only fixes that have a failing reproduction.
3. After each change, re-run both samples and the extra cases. If a sample field changes, undo the change.
4. One review round only.
5. Freeze changes about an hour before noon.

**If only 30 minutes remain:** run the P0 items in sections A, B, and C, plus lint, a clean install, and the README claims check.

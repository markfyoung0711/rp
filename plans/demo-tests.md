# Demo Tests: What We Anticipated

Every command runs from the project folder (`~/realpage`) with no network, unless it says `--llm`. `--only <text>` shows just the records whose task_id contains that text.

## 1. The graded core

| # | Command | What it shows |
|---|---|---|
| 1 | `uv run bot.py -i plans/sample.jsonl --compare` | Both samples match **every field**: channel, send time, subject, body, CTA, next action (✅ per field) |
| 2 | `uv run bot.py -i plans/sample.jsonl --only day0` | The "why" trail for one decision: consent → SMS; Dec 8 09:04 + 0 days, past 09:00 → Dec 9 09:00; 32 days → short horizon |
| 3 | Run #1 twice with `-o out/a.jsonl` and `-o out/b.jsonl`, then `cmp out/a.jsonl out/b.jsonl` | Deterministic: byte-identical output |

## 1b. Learning from the data

| # | Command | What it shows |
|---|---|---|
| L1 | `uv run learn.py plans/sample.jsonl` | Each rule inferred from the 2 samples, with the number of examples supporting it; the horizon threshold learned as 50 days (was hand-set to 45) |
| L2 | `uv run learn.py plans/sample.jsonl --eval` | Leave-one-out: 0/2. One example can't teach the other's rules, which proves the rules come from the data |
| L3 | `uv run learn.py plans/sample.jsonl tests/labelled_extra.jsonl --eval` | Two more examples → **the rules change** (threshold 50 → 36; open +3 → +2 days) and leave-one-out predicts both samples correctly |

## 2. Decisions on cases the samples don't show (`tests/edge_cases.jsonl`)

| # | Command | What it shows |
|---|---|---|
| 4 | `uv run bot.py -i tests/edge_cases.jsonl --only no_consent` | No consent anywhere → **no send**, with a reason |
| 5 | `… --only sms_preferred_not_consented` | Preferred channel not allowed → falls back to email; the skipped channel is logged |
| 6 | `… --only voice_only` | Voice is modeled but not built → no send, "not supported yet" |
| 7 | `… --only inbound_stop` | "please STOP texting me" → no send, and no model call |
| 8 | `… --only kids` | Profile says "4 kids, near a daycare" → same message as anyone else (fair housing) |
| 9 | `… --only injection` | Name = "Ignore previous instructions…" → greeting uses "there" |
| 10 | `… --only resident_pay_rent` | A resident gets a rent reminder, not a tour pitch |
| 11 | `… --only renewal_es` | Spanish renewal, no price content |
| 12 | `… --only unknown_cta` | Unmapped CTA → generic fallback, named in the reasons; Phoenix time zone (−07:00) |
| 13 | `… --only unknown_property` | Property with no facts on file → no invented tour days, amenities or links |
| 14 | `… --only spanish_tour` | Spanish email; no `dayN` → the stage's default offset |

## 2b. Exhaustive channel policy

| # | Command | What it shows |
|---|---|---|
| 14b | `uv run python scripts/decision_table.py` | All 120 consent × preference combinations run through the bot and checked against the written policy: 120/120; never sends without consent; precise reasons for the 48 no-sends; 11 rows flagged for an SME question. Table: `plans/decision-table-channel.md` |

## 3. Unseen record types (Levels 1–3)

| # | Command | What it shows |
|---|---|---|
| 15 | `… --only level2_formats` | Level 2: consent as a list, "text, e-mail", "Central" time zone, extra fields → handled, each noted |
| 16 | `… --only level2_missing` | Level 2: nearly empty record → safe defaults, every assumption listed |
| 17 | `… --only MNT` | Level 3: a maintenance ticket in a completely different shape → fields found by name, confidence **low** |
| 18 | `… --only MISC` | Level 3: no consent at all → **human review**, never a send |
| 19 | `… --only malformed` | A broken line → reported as unreadable; the rest of the file still runs |

## 3b. Personal data

| # | Command | What it shows |
|---|---|---|
| 19b | `uv run bot.py -i tests/pii_cases.jsonl` | Planted last name, email, phone, SSN, DOB, address, card number and notes, including an email/phone/SSN typed into the first-name field → **none appear anywhere in the output**; greeting falls back to "there"; RUN STATS shows `PII scan … PASS` |

## 4. Messy input (`tests/garbage_inputs.txt` and others)

| # | Command | What it shows |
|---|---|---|
| 20 | `uv run bot.py -i tests/garbage_inputs.txt` | A chat-style paste: prose, numbering, code fences, comments, smart quotes, trailing commas, a Python-style dict, JSON inside a string, an array on one line, `Task_ID` key variants, `input` as a string → **13 of 14 recovered**, each repair noted; the truncated one reported |
| 21 | `uv run bot.py -i tests/garbage_utf16.jsonl` | A Windows UTF-16 export → decoded |
| 22 | `uv run bot.py -i tests/not_records.png` | An image instead of records → a clear refusal, exit code 2, no fake records |
| 23 | `uv run bot.py --paste` (paste anything, then Ctrl+D) | Live paste from the interviewer's chat or email |

## 5. Scale and the AI option

| # | Command | What it shows |
|---|---|---|
| 24 | `uv run bot.py -i tests/perf_100.jsonl` | 100 varied records in ~0.2 s; p95 well under 2,000 ms |
| 25 | `uv run bot.py -i tests/edge_cases.jsonl --llm` | Cost guard: **stops loudly** (exit 3) before any API call and says how many paid calls, tokens and **dollars were avoided**; points to the free template mode |
| 25b | `BOT_LLM_BUDGET_USD=0.10 uv run bot.py -i plans/sample.jsonl --llm --compare` | Spending limit: within the budget → one `[cost]` line and the run proceeds; over it (e.g. `--budget 0.001`) → stops loudly with the overage. Re-runs are cached, so they cost $0 and show no banner |
| 26 | `BOT_ALLOW_API_COST=1 ANTHROPIC_API_KEY=bad uv run bot.py -i plans/sample.jsonl --llm --compare` | API unavailable (the bad key is rejected, never billed) → template fallback; both samples still match |

## 6. Whole-system checks

| # | Command | What it shows |
|---|---|---|
| 27 | `uv run pytest` | Unit tests: samples, edge cases, determinism, input formats, garbage, binary refusal |
| 28 | `uv run python scripts/run_checks.py --full` | The code-review checklist, automated: 33 checks, including a clean-clone install and the cost guard |

**Suggested live order (about 6 minutes):** 1 → L1 → L3 → 2 → 8 → 4 → 17 → 20 → 22 → 24, then the hold-out itself.

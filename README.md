# Leasing Outreach Decision Bot

For each record, the bot decides **whether** to contact the person, and if so **on which channel**, **when**, and **with what message**, plus the **next action**. It takes JSON records in and gives one decision per record out. This is the RealPage take-home; the assignment is in [`plans/spec.md`](plans/spec.md).

## Run it

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
uv sync                                                    # install (once)
uv run bot.py -i plans/sample.jsonl --compare              # the two samples, compared field by field
uv run bot.py -i tests/edge_cases.jsonl                    # 16 unseen-style cases (Levels 1-3)
uv run bot.py -i holdout.jsonl -o out/holdout.jsonl        # a hold-out file -> an output file
uv run bot.py --paste -o out/holdout.jsonl                 # paste records, then Ctrl+D
uv run learn.py plans/sample.jsonl --eval                  # learn the rules from labelled examples; leave-one-out test
uv run pytest                                              # tests
uv run python scripts/run_checks.py --full                 # the code-review checklist, automated (32 checks)
uv run python scripts/gen_records.py 100 > /tmp/p.jsonl    # generate test records (performance: plans/performance.md)
```

Input can be JSONL, a JSON array, a wrapper object, or pretty-printed objects, in UTF-8 or UTF-16. The reader tolerates pasted garbage (prose, numbering, code fences, comments, smart quotes, trailing commas, Python-style dicts, double-encoded JSON, key variants such as `Task_ID`). It repairs what it can, notes each repair in the record's warnings, and turns anything unreadable into a no-send with a reason; see `tests/garbage_inputs.txt`. The screen shows each decision with its reasons, then a **RUN STATS** block (decisions by channel and reason, confidence, latency avg/p50/p95/max and throughput against the input's `p95_latency_ms`, a safety scan against `safety_violations_max`, a PII report (personal-data items found in the input and withheld from the output, by category; protected-class details withheld; anything leaked), plus a pattern scan of every output record, API cost, and with `--compare` per-field match rates and body similarity), then the whole batch between `=== BEGIN OUTPUT ===` and `=== END OUTPUT ===` for copy-paste. Add `--llm` to have Claude (Haiku 4.5) write the wording. **No cost by default:** if `--llm` would need any paid API call, the bot **stops before processing** (exit code 3). It prints how many calls would be made, the estimated tokens, and the **dollar cost avoided**. It runs only if every answer is already cached ($0), or if you allow spending: `--budget 0.10` (or `BOT_LLM_BUDGET_USD=0.10`) runs quietly when the estimate is within the limit and stops loudly when it isn't; `BOT_ALLOW_API_COST=1` allows any amount. Both print the estimated cost first. Any API failure falls back to the template.

## Output (one line per record)

```json
{"task_id": "...", "next_message": {"channel", "send_at", "subject", "body", "cta"} | null,
 "next_action": {...}, "why": ["one line per decision"], "meta": {"record_type", "confidence", "mode", "warnings"}}
```

`next_message` and `next_action` follow the samples' `expected` shape. A no-send has `next_message: null` and `next_action: {"type": "suppress" | "human_review", "reason": ...}`.

## How it decides

| Step | Done by | Rule |
|---|---|---|
| Read | code | A bad record becomes a no-send with a reason; the rest still run |
| STOP / opt-out | code | Any opt-out flag or STOP keyword → no send, and no model call |
| Channel | code | The first preferred channel with consent; voice is skipped (not built) |
| Send time | code | Local `last_interaction` + the `dayN` in the task_id (else a stage default), at 09:00 for SMS or 10:00 for email; moved to the next day if that time isn't after the last interaction |
| Next action | code | A new lead starts a cadence (`short` if ≤ 45 days to move-in, else `long`); otherwise follow up in 3 days |
| Wording | template (default) or Claude (`--llm`) | Property claims come only from `config/properties.yaml` |
| CTA and opt-out | code | Fixed text per channel and language; never written by the model |
| Guards | code | Opt-out present, no phone or email in the body, no protected-class terms, unsafe names → "there" |

The rules live in [`config/rules.yaml`](config/rules.yaml). Each table has a default row for values the bot hasn't seen before.

## How it learns

The decision rules are **learned from labelled examples**, meaning records that carry an `expected` block, not just typed in. `uv run learn.py <files>` infers each rule from the examples and prints the evidence: the send hour per channel, the day-offset rule, stage offsets, CTA mapping, next action per stage, follow-up days, and the short/long horizon threshold. `--write` saves the result to `config/learned.yaml`, which the bot then uses. RUN STATS shows which rules are active.

- **From the 2 samples:** SMS 09:00 and email 10:00; dayN with roll-forward (2/2); book_tour → schedule_tour; new → start a cadence, open → follow up in 3 days; horizon threshold **50 days** (short at 32, long at 68).
- **Add examples and the rules change:** `uv run learn.py plans/sample.jsonl tests/labelled_extra.jsonl` moves the threshold to 36 and learns +2 days for "open".
- **Generalization is measured, not claimed:** `--eval` runs leave-one-out, learning from the other examples starting from neutral rules and predicting each one. With the 2 samples it scores 0/2, because one example can't teach the other's rules. With 4 examples, both samples are predicted correctly. The hold-out records are never learned from.

## Built vs designed

| Built and runnable | Designed, not built (see [`plans/solution.md`](plans/solution.md)) |
|---|---|
| Batch CLI, three input formats, export file plus a readable view | Database, APIs, login |
| Consent/STOP gate, channel, send time, next action | Owner / support / renter web UI |
| Templates (English, Spanish) and the optional Claude wording | Real SMS/email/voice sending, inbound replies |
| Guards; handling of unseen records at Levels 1–3 | Sentiment tracking, review-site ingestion |
| 16 edge cases and tests | Adjacent agents (maintenance, billing, …) |

## Assumptions

These were inferred from two samples and stated rather than hidden. The details are in [`plans/decisions.md`](plans/decisions.md).

- **Send time:** the rule above; 09:00/10:00 are per-channel settings in `config/rules.yaml`. Use `--now` to set a reference time.
- **Property facts** (tour days, amenities, links) come from `config/properties.yaml`. For an unknown property the message makes no specific claims.
- **Horizon threshold:** 45 days to move-in (samples: 32 → short).
- **No-send shape:** as above. The assignment doesn't define one.
- **Consent:** only an explicit opt-in counts; missing or unclear consent means no send.
- **Voice:** modeled but not built; skipped, with a reason.
- **AI disclosure:** not added to message bodies, because the expected outputs don't include it; it would be a policy setting.
- **Personal data in output:** only the first name (in the greeting) and your own `task_id`. Nothing else from the profile ever appears, in any field; see `tests/pii_cases.jsonl`.
- **Output determinism:** the same input gives a byte-identical output file. `--llm` answers are cached.

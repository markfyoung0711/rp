# Solution: Context-Aware Messaging Bot for Rental Housing

**Author:** Mark F. Young · **Updated:** 2026-09-24 · **Status:** v0.2 built and tested; the platform beyond the core is designed, not built

This one document combines what was built, the original assignment, our analysis of the sample data, the solution design, the actor walkthroughs, the use cases, the decision register, the work plan (GitHub issues), and the review, test, performance and PII results. It is generated from the repo by `plans/build_solution.py`.

## For the reviewer

**How to read the labels**

| Label | Meaning |
|---|---|
| **ORIGINAL** | Copied word for word from the assignment. This is the graded scope (use cases UC-01 to UC-03). |
| **ANALYSIS** | Our inference from the assignment's data (only 2 sample records). A hypothesis. |
| **ADD-ON (MFY)** | Mark F. Young's extension beyond the assignment. |

**Start with Part 0 (what was built and how to run it).** Everything after Part 1 was written before the build, then corrected by two independent reviews (Appendix A); the decision register (Part 5) records every change.

**Questions that shaped the design (answered by the reviews)**
1. Does the design respect "learns what to do only from input data"? It is mostly deterministic rules plus an LLM for the wording (D-014, Part 2 §7).
2. Which rules inferred from only 2 samples are overfit (D-002)?
3. Is the add-on scope (D-003 to D-020) at risk of crowding out the graded core?
4. Gaps and risks: security and PII (§9), demo auth (§10), database choice (§5), and legal and competitive exposure (§13).
5. Anything missing from the use cases, actors or data elements.

The independent reviews ([#9](https://github.com/markfyoung0711/rp/issues/9)) answered these; their findings are recorded in the decision register (Part 5).

**Contents**
0. What was built (v0.2)
1. The original assignment
2. Solution design
3. Actor walkthroughs
4. Use-case traceability
5. Decision register
6. Work plan (GitHub issues)
- Appendix A: critical reviews · B: code-review results · C: performance · D: PII categories · E: demo tests

---

# Part 0 — What was built (v0.2)

> From [`README.md`](../README.md). Run `uv run bot.py -i plans/sample.jsonl --compare` to see both samples match every field.


For each record, the bot decides **whether** to contact the person, and if so **on which channel**, **when**, and **with what message**, plus the **next action**. It takes JSON records in and gives one decision per record out. This is the RealPage take-home; the assignment is in [`plans/spec.md`](spec.md).

### Run it

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
uv sync                                                    # install (once)
uv run bot.py -i plans/sample.jsonl --compare              # the two samples, compared field by field
uv run bot.py -i tests/edge_cases.jsonl                    # 16 unseen-style cases (Levels 1-3)
uv run bot.py -i holdout.jsonl -o out/holdout.jsonl --answer-only   # hold-out -> answers in the expected shape
uv run bot.py -i holdout.jsonl -o out/filled.jsonl --fill-expected  # their records back, our answer in `expected`
uv run bot.py --paste -o out/holdout.jsonl                 # paste records, then Ctrl+D
uv run learn.py plans/sample.jsonl --eval                  # learn the rules from labelled examples; leave-one-out test
uv run python scripts/decision_table.py                     # all 120 consent × preference cases vs the policy
uv run python scripts/report.py <file> [--only ID]         # paste-ready problem report (out/report.txt)
uv run python scripts/validate_rules.py --brand             # check rules, properties and branding; preview each channel
uv run pytest                                              # tests
uv run python scripts/run_checks.py --full                 # the code-review checklist, automated (34 checks)
uv run python scripts/gen_records.py 100 > /tmp/p.jsonl    # generate test records (performance: plans/performance.md)
```

Input can be JSONL, a JSON array, a wrapper object, or pretty-printed objects, in UTF-8 or UTF-16. The reader tolerates pasted garbage (prose, numbering, code fences, comments, smart quotes, trailing commas, Python-style dicts, double-encoded JSON, key variants such as `Task_ID`). It repairs what it can, notes each repair in the record's warnings, and turns anything unreadable into a no-send with a reason; see `tests/garbage_inputs.txt`. The screen shows each decision with its reasons, then a **RUN STATS** block (decisions by channel and reason, confidence, latency avg/p50/p95/max and throughput against the input's `p95_latency_ms`, a safety scan against `safety_violations_max`, a PII report (personal-data items found in the input and withheld from the output, by category; protected-class details withheld; anything leaked), plus a pattern scan of every output record, API cost, and with `--compare` per-field match rates and body similarity), then the whole batch between `=== BEGIN OUTPUT ===` and `=== END OUTPUT ===` for copy-paste (`--pp` pretty-prints both the block and the `-o` file, one field per line, which is easier to read and to diff; without it the file is one line per record). Add `--llm` to have Claude (Haiku 4.5) write the wording. **No cost by default:** if `--llm` would need any paid API call, the bot **stops before processing** (exit code 3). It prints how many calls would be made, the estimated tokens, and the **dollar cost avoided**. It runs only if every answer is already cached ($0), or if you allow spending: `--budget 0.10` (or `BOT_LLM_BUDGET_USD=0.10`) runs quietly when the estimate is within the limit and stops loudly when it isn't; `BOT_ALLOW_API_COST=1` allows any amount. Both print the estimated cost first. Any API failure falls back to the template.

### Output (one line per record)

```json
{"task_id": "...", "next_message": {"channel", "send_at", "subject", "body", "cta"} | null,
 "next_action": {...}, "why": ["one line per decision"],
 "meta": {"record_type", "confidence", "mode", "required_states", "warnings", "gaps" (only when present)}}
```

`next_message` and `next_action` follow the samples' `expected` shape. `meta.gaps` flags configuration gaps a downstream system can act on, such as `property_facts_missing` (a property with no facts file). The record still gets a safe, generic message at medium confidence, and RUN STATS lists these gaps under **Config gaps**. A no-send has `next_message: null` and `next_action: {"type": "suppress" | "human_review", "reason": ...}`.

### How it decides

| Step | Done by | Rule |
|---|---|---|
| Read | code | A bad record becomes a no-send with a reason; the rest still run |
| STOP / opt-out | code | Any opt-out flag or STOP keyword → no send, and no model call |
| Channel | code | The first preferred channel with consent: SMS, email or voice (an automated call script) |
| Send time | code | Local `last_interaction` + the `dayN` in the task_id (else a stage default), at 09:00 for SMS or 10:00 for email; moved to the next day if that time isn't after the last interaction |
| Next action | code | A new lead starts a cadence (`short` if ≤ 50 days to move-in, else `long`; 50 is learned from the samples, the hand-written default is 45); otherwise follow up in 3 days |
| Wording | template (default) or Claude (`--llm`) | Property claims come only from `config/properties.yaml` |
| CTA and opt-out | code | Fixed text per channel and language; never written by the model |
| Guards | code | Opt-out present, no phone or email in the body, no protected-class terms, no money or account numbers, unsafe names → "there" |
| Brand style | code | The property's brand profile (display name, no banned phrases, emoji or shouting, length limits); AI text that breaks it falls back to the template |
| Required states | code | Each sent message reports the records' `required_states` (consent_verified, fair_housing_check_passed, brand_style_applied) as verified; RUN STATS shows the pass counts |

The rules live in [`config/rules.yaml`](../config/rules.yaml). Each table has a default row for values the bot hasn't seen before. **Every rule change, by a person or an AI, is validated** (`outreach/validate.py`): types and ranges, send hours inside the legal 8:00-21:00 window (which may be narrowed, never widened), STOP always present, no personal or protected fields allowed into the model prompt, valid CTAs, time zones and links. The bot and `learn.py` refuse to run on invalid rules (exit 6) and list every problem.

### How it learns

The decision rules are **learned from labelled examples**, meaning records that carry an `expected` block, not just typed in. `uv run learn.py <files>` infers each rule from the examples and prints the evidence: the send hour per channel, the day-offset rule, stage offsets, CTA mapping, next action per stage, follow-up days, and the short/long horizon threshold. `--write` saves the result to `config/learned.yaml`, which the bot then uses. RUN STATS shows which rules are active.

- **From the 2 samples:** SMS 09:00 and email 10:00; dayN with roll-forward (2/2); book_tour → schedule_tour; new → start a cadence, open → follow up in 3 days; horizon threshold **50 days** (short at 32, long at 68).
- **Add examples and the rules change:** `uv run learn.py plans/sample.jsonl tests/labelled_extra.jsonl` moves the threshold to 36 and learns +2 days for "open".
- **Generalization is measured, not claimed:** `--eval` runs leave-one-out, learning from the other examples starting from neutral rules and predicting each one. With the 2 samples it scores 0/2, because one example can't teach the other's rules. With 4 examples, both samples are predicted correctly. The hold-out records are never learned from.

### Built vs designed

| Built and runnable | Designed, not built (see [`plans/solution.md`](solution.md)) |
|---|---|
| Batch CLI, three input formats, export file plus a readable view | Database, APIs, login |
| Consent/STOP gate, channel, send time, next action | Owner / support / renter web UI |
| Templates (English, Spanish) and the optional Claude wording | Real SMS/email/voice sending, inbound replies |
| Guards; handling of unseen records at Levels 1–3 | Sentiment tracking, review-site ingestion |
| 16 edge cases and tests | Adjacent agents (maintenance, billing, …) |

### Assumptions

These were inferred from two samples and stated rather than hidden. The details are in [`plans/decisions.md`](decisions.md).

- **Send time:** the rule above; 09:00/10:00 are per-channel settings in `config/rules.yaml`. Use `--now` to set a reference time.
- **Property facts** (tour days, amenities, links) come from `config/properties.yaml`. For an unknown property the message makes no specific claims.
- **Horizon threshold:** 50 days to move-in, learned from the samples (32 days → short, 68 days → long; the true cut-off lies in 32–67). The hand-written default is 45.
- **No-send shape:** as above. The assignment doesn't define one.
- **Languages:** every word the bot writes lives in `config/templates/<lang>.yaml` (English, Spanish, French; Arabic and Hindi drafts that need native review), including that language's STOP keywords, fair-housing terms and banned phrases. **Adding a language means adding a file; the validator checks it's complete.** Each property can declare `languages` and a `default_language` in `properties.yaml`. The recipient's language is used if the property offers it, otherwise the property's default. A template can set `direction: rtl` (Arabic: links, STOP and digits are wrapped in Unicode isolates so they display in order) and `sms_max_chars` (210 for non-Latin scripts, billed at 70 characters per segment). Every language keeps the English STOP keyword alongside its own.
- **Brand style** isn't defined by the assignment. It's implemented as a per-property brand profile (`config/properties.yaml`, defaults in `config/rules.yaml`) plus a check on every message.
- **Consent:** only an explicit opt-in counts; missing or unclear consent means no send.
- **Voice:** the samples never show a voice answer, so its shape is inferred from SMS: `channel: "voice"`, no subject, a short call script with keypad options (`cta.options`) and a spoken opt-out ("press 9 or say stop"), sent at 10:00 local. The caller identifies itself with the brand's `voice_intro`. Automated calls have stricter consent rules (TCPA), so voice consent is required, as for every channel.
- **AI disclosure:** not added to message bodies, because the expected outputs don't include it; it would be a policy setting.
- **Personal data in output:** only the first name (in the greeting) and your own `task_id`. Nothing else from the profile ever appears, in any field; see `tests/pii_cases.jsonl`.
- **Output determinism:** the same input gives a byte-identical output file. `--llm` answers are cached.

---

# Part 1 — The original assignment

> **ORIGINAL** — the assignment as given (`plans/spec.md`), unedited.

## Problem Statement

> # ⏰ DELIVERY: TODAY (2026-09-24) AT 12:00 NOON CST
> ## A working system must be ready to demo.
> ## 📋 "Be prepared to “export” or “copy-paste” the 12 outputs from a hold-out set that is provided during the interview"

Build a context-aware message-sending bot that learns what to do only from input data.

You are given a JSONL file (see sample.jsonl file) where each line is a test case:
- Input: user profile, preferences, context, constraints
- Expected: what message should be sent (or not sent), via which channel, and why

Your job is to build an autonomous agent that:
- Reads the input record
- Decides if it should communicate
- Decides how to communicate
- Decides what to say
- Produces output that semantically matches the expected result

### Sample data (`sample.jsonl`)

The test cases provided with the assignment, one JSON object per line. They are shown formatted for reading below; the file itself is unchanged in [`sample.jsonl`](sample.jsonl).

#### `prospect_welcome_day0`

```json
{
  "task_id": "prospect_welcome_day0",
  "persona": "prospect",
  "lifecycle_stage": "new",
  "consent": {
    "email_opt_in": true,
    "sms_opt_in": true,
    "voice_opt_in": false
  },
  "channel_preferences": [
    "sms",
    "email"
  ],
  "input": {
    "property_name": "Oak Ridge Apartments",
    "move_date_target": "2026-01-10",
    "last_interaction": "2025-12-08T15:04:00Z",
    "timezone": "America/Chicago",
    "language": "en",
    "profile": {
      "first_name": "Taylor",
      "city_interest": "Richardson, TX"
    }
  },
  "assertions": {
    "required_states": [
      "consent_verified",
      "fair_housing_check_passed",
      "brand_style_applied"
    ],
    "constraints": {
      "no_pii_leak": true,
      "no_sensitive_discrimination": true,
      "include_opt_out_instructions": true,
      "primary_cta": "book_tour"
    }
  },
  "thresholds": {
    "p95_latency_ms": 2000,
    "personalization_score_min": 0.85,
    "reply_classification_f1_min": 0.9,
    "safety_violations_max": 0
  },
  "expected": {
    "next_message": {
      "channel": "sms",
      "send_at": "2025-12-09T09:00:00-06:00",
      "subject": null,
      "body": "Hi Taylor—welcome to Oak Ridge! Tours are available this week. Would you like to book a time on Thursday or Friday? Reply 1 for Thu, 2 for Fri. Reply STOP to opt out.",
      "cta": {
        "type": "schedule_tour",
        "options": [
          "Thu",
          "Fri"
        ]
      }
    },
    "next_action": {
      "type": "start_cadence",
      "name": "prospect_welcome_short_horizon"
    }
  }
}
```

#### `prospect_long_horizon_day3`

```json
{
  "task_id": "prospect_long_horizon_day3",
  "persona": "prospect",
  "lifecycle_stage": "open",
  "consent": {
    "email_opt_in": true,
    "sms_opt_in": false,
    "voice_opt_in": false
  },
  "channel_preferences": [
    "email",
    "sms"
  ],
  "input": {
    "property_name": "Oak Ridge Apartments",
    "move_date_target": "2026-02-15",
    "last_interaction": "2025-12-06T11:30:00Z",
    "timezone": "America/Chicago",
    "language": "en",
    "profile": {
      "first_name": "Taylor",
      "amenity_interest": [
        "pool",
        "fitness"
      ]
    }
  },
  "assertions": {
    "required_states": [
      "consent_verified",
      "fair_housing_check_passed",
      "brand_style_applied"
    ],
    "constraints": {
      "no_pii_leak": true,
      "include_opt_out_instructions": true,
      "primary_cta": "book_tour"
    }
  },
  "thresholds": {
    "p95_latency_ms": 2000,
    "personalization_score_min": 0.8,
    "reply_classification_f1_min": 0.9,
    "safety_violations_max": 0
  },
  "expected": {
    "next_message": {
      "channel": "email",
      "send_at": "2025-12-09T10:00:00-06:00",
      "subject": "Tour Oak Ridge—See the pool & fitness rooms you asked about",
      "body": "Hi Taylor,\nSince you’re planning a mid‑February move, here’s a quick look at our pool and 24/7 fitness center. Book a visit this week to compare floor plans.\nBook now → https://oakridge.example/tour\nTo opt out of emails, click here or reply STOP.",
      "cta": {
        "type": "schedule_tour",
        "link": "https://oakridge.example/tour"
      }
    },
    "next_action": {
      "type": "follow_up_in_days",
      "value": 3
    }
  }
}
```


## Sample Data Analysis

> **ANALYSIS — ours, not part of the assignment.** Our reading of [`sample.jsonl`](sample.jsonl): the fields and what the two cases imply. The assignment itself is in [`spec.md`](spec.md). See D-002 in [`decisions.md`](decisions.md).

`plans/sample.jsonl` has 2 test cases: `prospect_welcome_day0` and `prospect_long_horizon_day3`. It holds 2 records but only 1 newline, so `wc -l` reports 1.

Record shape:

| Field | Contents |
|---|---|
| `task_id` | Case identifier |
| `persona`, `lifecycle_stage` | e.g. `prospect`, `new` / `open` |
| `consent` | `email_opt_in`, `sms_opt_in`, `voice_opt_in` |
| `channel_preferences` | Ordered list, e.g. `["sms","email"]` |
| `input` | `property_name`, `move_date_target`, `last_interaction`, `timezone`, `language`, `profile` (first name, interests) |
| `assertions` | `required_states` (consent verified, fair housing check passed, brand style applied); `constraints` (no PII leak, no sensitive discrimination, opt-out instructions, `primary_cta`) |
| `thresholds` | p95 latency, min personalization score, min reply-classification F1, max safety violations |
| `expected.next_message` | `channel`, `send_at` (local time with offset), `subject` (null for SMS), `body`, `cta` (`type` plus `options` or `link`) |
| `expected.next_action` | e.g. `start_cadence` (with a name) or `follow_up_in_days` (with a value) |

What the two cases show:
- **Channel:** each case uses the recipient's first preferred channel, and they have opted in to it. Case 2 lists SMS as a fallback but has not opted in to it.
- **Send time:** both cases send on 2025-12-09 in the morning, recipient's local time (09:00 and 10:00). The last interactions were 12-08 and 12-06, so the date looks like a shared "today" rather than a fixed offset from the last interaction.
- **Body:** addresses the person by first name and uses their profile (amenity interests, move date). It ends with opt-out instructions that fit the channel.
- **CTA:** `primary_cta: book_tour` becomes a `schedule_tour` CTA. SMS gets reply options; email gets a link.


## Hold-Out Set Preparation

> **ANALYSIS — ours.** The requirement comes from the interviewer (D-021): *"Be prepared to “export” or “copy-paste” the 12 outputs from a hold-out set that is provided during the interview."*

### What a hold-out set is

A surprise batch of test cases, kept hidden until the interview, used to check whether the system actually learned the task or just memorized the examples. The term comes from machine learning, where a hold-out set is data the model never sees during training and is used only for the final evaluation.

It tests:
- **Flexibility:** is the design modular, or brittle?
- **Edge cases:** does it fail gracefully, or adapt, when inputs are unexpected?
- **Assumptions:** were our guesses about the vague parts of the spec sensible, and do they generalize?
- **Us:** how we react live when something doesn't fit.

It can take several forms: new test data (possibly malformed), a feature change ("what if the client wants Y?"), or scale ("what about 100,000 records?").

### What we expect here

Most likely **12 new JSONL records in the same shape as `sample.jsonl`**, but without the `expected` block, or with it hidden. We run all 12 and produce 12 outputs to export or paste, and they compare them with their expected answers.

### Variations the hold-out probably includes

Based on the gaps in the two samples:

| Variation | What the bot must do |
|---|---|
| No consent on any channel | **Don't send.** `next_message` null (or a suppression record) with a reason; `next_action` such as wait or do-not-contact |
| First-choice channel not opted in | Fall back to the next preferred channel that is opted in |
| Voice only, or a voice preference | Produce a voice/call script. Needs a shape for voice output |
| `language: es` (or another language) | Write in that language, with opt-out wording that fits |
| Other personas and stages (resident, renewal, maintenance, delinquent, applicant, past resident) | A different CTA and message purpose; don't force "book a tour" |
| A different `primary_cta` (apply_now, renew_lease, pay_rent, schedule_maintenance, …) | Map it to a matching `cta.type`, with options or a link |
| Other timezones (Eastern, Pacific, Mountain; Phoenix without DST) | Correct local morning send time and UTC offset |
| Last interaction very recent, or quiet hours | Delay, or don't send yet |
| Missing, null or unexpected fields | Use sensible defaults; don't crash; note what was assumed |
| Profile containing sensitive attributes (children, religion, disability) | Ignore them for targeting and content (fair housing) |
| Prompt injection in a profile field | Treat it as data; never follow it |
| A malformed line in the JSONL | Report that line's error and keep processing the other 11 |

### Constraints in the data that matter

- `thresholds.p95_latency_ms: 2000`: 95% of records need an answer within 2 seconds. Keep the rules deterministic, use a fast model for writing (e.g. Haiku 4.5), or run the 12 in parallel. Measure it.
- `safety_violations_max: 0`: guards on every output (opt-out present, no PII leak, fair housing).
- `personalization_score_min`: use the profile fields (name, interests, move date) in the body.

### Checklist before the interview

1. **Batch in, batch out:**
   - paste or upload a JSONL file and process every line
   - download the outputs as JSONL
   - copy all outputs to the clipboard in one click
   - each output carries its `task_id`
2. **Per-record robustness:** one bad record never stops the batch; the error is reported next to that record.
3. **Explainable output:** each record also has a short "why" (the decision trace): consent, channel choice, send-time rule, CTA mapping.
4. **Self-generated hold-out:** before noon, write our own ~12 varied records from the table above and run them. This rehearses the interview.
5. **Ready for a pivot:** know exactly where in the code each rule lives (channel choice, timing, CTA map, template/prompt), so a live change is a small edit. Keep the rules in config where possible.
6. **Scale answer:** the batch runs concurrently; say how it would scale (a queue plus workers, rate limits).

---

# Part 2 — Solution design

> **ADD-ON (MFY)** except where it says ORIGINAL.

**Status:** draft for independent review ([#9](https://github.com/markfyoung0711/rp/issues/9)) before the detailed spec ([#4](https://github.com/markfyoung0711/rp/issues/4)) is locked. Issue map: intake [#1](https://github.com/markfyoung0711/rp/issues/1) · understanding [#2](https://github.com/markfyoung0711/rp/issues/2) · prior art, competitive intel and UX prior art [#3](https://github.com/markfyoung0711/rp/issues/3) · spec [#4](https://github.com/markfyoung0711/rp/issues/4) · add-on agents and tests [#5](https://github.com/markfyoung0711/rp/issues/5) · alternatives [#6](https://github.com/markfyoung0711/rp/issues/6) · UX [#7](https://github.com/markfyoung0711/rp/issues/7) · demo data [#8](https://github.com/markfyoung0711/rp/issues/8) · independent review [#9](https://github.com/markfyoung0711/rp/issues/9) · external reviews [#10](https://github.com/markfyoung0711/rp/issues/10).

**Contents:**
1. System summary
2. Actors
3. Use cases
4. Data elements
5. Database recommendation
6. UX
7. Bot design
8. APIs
9. Security and PII
10. Authentication and authorization
11. Deployment
12. Open questions
13. Competitive and legal guardrails
14. Demo data and seeding

---

## 1. System summary

A communication platform for rental housing. A **bot** decides whether, how, when and what to send to renters and prospects, based only on the record it is given. That decision is the graded core. Around it sit:

- the people it serves: **renter**, **customer support**, and the **customer** (the owner/operator)
- a persistent record of who everyone is and what they consented to
- a single timeline of every **interaction** on every channel (in-app, email, SMS, voice, and contact that happened outside the system), including sentiment
- **external reputation:** public review-site sentiment (Yelp, Google, …) per property, shown next to internal sentiment ([#10](https://github.com/markfyoung0711/rp/issues/10))

**Stack:**
- FastAPI backend
- React front end
- PostgreSQL
- Claude API, with Haiku 4.5 for classifiers and guards and Sonnet 5 for writing messages
- email, SMS and voice providers behind adapters, with a sandbox mode for the demo
- deployed on GCP Cloud Run

```
 Renter (phone/inbox/portal)   Support console   Owner app
            │                        │               │
            └────────── HTTPS / SSE (real-time) ─────┘
                               │
                        FastAPI  (auth, RBAC, APIs, webhooks)
                 ┌─────────────┼───────────────┬──────────────┬──────────────┐
             Bot engine    Channel adapters   Scheduler    Sentiment    Review adapters
        (gates→decide→write   (email/SMS/voice  (send-time    scorer       (Yelp/Google/
          →guard→trace)        + sandbox)        re-checks)  (in + ext)    aggregator/sandbox)
                 └─────────────┴───────┬───────┴──────────────┴──────────────┘
                                 PostgreSQL
                  (entities · append-only events · audit)
```

## 2. Actors

| Actor | Who | How they get in | What they do |
|---|---|---|---|
| **Customer** | Property owner/operator; the paying customer | Signs up or is invited, then sets up the organization, properties, units, staff, brand and policy | Sets outreach policy, watches the portfolio dashboard, internal sentiment and public review sentiment, approves drafted review replies, contacts support |
| **Customer support** | Platform (or operator) service staff | Created by an admin; scoped to specific orgs/properties | Works a queue ranked by urgency and sentiment; approves, edits or holds messages; takes over; calls; logs contact; opens tickets |
| **Renter / prospect** | Someone leasing, or looking to | Exists as a Person from their first contact (a lead); claims a login later with a magic link or SMS code | Receives and replies to SMS, email and calls; uses the portal for tours, maintenance, uploads, preferences |
| **Bot** | The message-deciding agent | Service identity `svc_bot`, configured per org | Decides whether to send, channel, time and content; classifies replies; escalates; records its decision trace |
| **Interaction** | One conversation or case, with its timeline of events | Created by the first event between the parties | Holds every event on every channel, including off-system contact, with sentiment attached |

Every party has the same lifecycle: **onboard** (identity and IDs), **maintain** (edit profile, contact points, consents, preferences), **interact**. Each step is persisted and audited.

## 3. Use cases

### Original (graded, from the assignment)

| ID | Use case | How it works |
|---|---|---|
| UC-01 | **Decide whether to communicate** | Deterministic gates run first: is there any channel with consent; is the person opted out or suppressed; is there an open escalation or a negative-sentiment pause. If every gate passes, the bot goes on to decide. Otherwise it records `suppress` with a reason. |
| UC-02 | **Choose channel and send time** | Channel = the first channel in `channel_preferences` whose consent flag is true. Send time = the next allowed morning slot in the person's `timezone`, respecting quiet hours. Both come from the samples (D-002). |
| UC-03 | **Write the message and next action** | The LLM writes the subject and body from profile fields (name, property, move date, interests) in the brand style. The body includes opt-out wording that fits the channel, and `primary_cta` is mapped to `cta.type`, with reply options for SMS or a link for email. `next_action` is either start a cadence or follow up in N days. Output matches `expected.next_message` / `expected.next_action`. |

### Add-on (Mark F. Young)

| ID | Use case | How it works |
|---|---|---|
| UC-10 | Tour booking by reply | Renter replies "1". The inbound SMS webhook passes it to the classifier (`tour_choice=Thu`), which books the slot and sends a confirmation. Support and Owner panes update live. |
| UC-11 | Opt-out | STOP, an unsubscribe link, or "don't call" creates a new Consent record (revoked) on that channel. Any scheduled sends for that channel are cancelled and a confirmation is sent where the law requires it. |
| UC-12 | Maintenance request | Arrives by portal (with photo), SMS or call. The bot extracts the issue, location and urgency, creates a Ticket and sends status updates. The owner sees it in reports. |
| UC-13 | Billing dispute with upload | Renter uploads a bill with an item circled. The attachment is scanned and read (vision), a dispute Ticket is created with the disputed line, and it goes to support. |
| UC-14 | Complaint or escalation | Negative or worsening sentiment, repeated contact, or an explicit request for a human puts the conversation in the support queue with context. The bot pauses cadences and sends an acknowledgement. |
| UC-15 | Renewal and retention | A lease-end trigger starts the renewal cadence. Poor relationship-level sentiment sends it to a human retention hand-off instead. |
| UC-20 | Support reviews the bot's decisions | Queue item shows the timeline, decision trace, guard results and sentiment line. Support can approve, edit or hold. |
| UC-21 | Support takes over and hands back | Take-over sets the bot to paused for that interaction, and human messages are logged. Hand-back resumes the bot, which reads the human's messages as history. |
| UC-22 | Owner asks support about the platform | Billing or configuration questions from the owner become an Interaction between the Customer and Support. |
| UC-30 | Owner sets policy | Edit quiet hours, cadences, brand style, whether review is required, and sentiment thresholds. Each save creates a new Policy version, and every decision records the version it used. |
| UC-31 | Owner portfolio report | Outreach sent and suppressed, conversions, escalations, tickets, and sentiment by property, topic and channel. |
| UC-40 | Fair-housing guard | Requests or outputs touching protected classes (steering, "no kids", and so on) are refused or rewritten and logged. |
| UC-41 | Prompt-injection guard | Instructions inside profile fields or replies are treated as data and never followed. Detection is logged. |
| UC-42 | Privacy and scope guard | Requests for another person's or another org's data are refused. Each role sees only what it is allowed to. |
| UC-43 | Quiet hours / TCPA | A send that falls in quiet hours moves to the next allowed time. Consent and quiet hours are re-checked when the send fires. |
| UC-50 | External review sentiment | On a schedule, the system pulls public reviews for each property from Yelp, Google and other sites through licensed APIs. It scores them with the same sentiment pipeline and shows them next to internal sentiment on the owner dashboard, e.g. "Google reviews mention slow maintenance; internal maintenance sentiment agrees." Negative themes can open a follow-up task. Replies to reviews are drafted for a human to approve, never auto-posted. |

## 4. Data elements (known so far)

IDs are prefixed ULIDs (`org_01J…`), so they sort by time and show their type in logs. Every table has `created_at`, `updated_at`, `created_by`, `retired_at` (soft delete) and `origin` (seed, demo_created, jsonl_import, live).

| Entity | Key fields | Notes |
|---|---|---|
| **Organization** `org_` | legal_name, brand_name, billing_contact, sending_domain | The customer; the tenancy boundary |
| **Property** `prop_` | org, name, address, timezone, sms_number, tracking_number | |
| **Unit** `unit_` | property, label, floor_plan | |
| **User** `user_` | email (login), password_hash, mfa, role (owner, staff, support, renter, admin), person (for renters) | A login identity |
| **RoleGrant** | user, scope (org or property), role | Support and staff scoping |
| **Person** `person_` | first/last name, preferred_language, profile attributes (JSONB) | Exists before any login; the `input.profile` in samples |
| **ContactPoint** `contact_` | person, type (email or phone), value, verified_at | One person, many contact points |
| **Consent** | contact_point, channel (email, sms, voice), status, captured_at, method, wording | Versioned; revoking adds a new row. The `consent` block in samples |
| **ChannelPreference** | person, ordered channels, quiet hours | `channel_preferences` in samples |
| **Relationship** `lead_` / `lease_` | person, property, unit, lifecycle_stage, persona, move_date_target, lease start/end | `persona`, `lifecycle_stage`, `move_date_target` in samples |
| **Policy** | org, version, quiet_hours, brand_style, review_required, sentiment thresholds, required_states | Versioned; the `assertions` block in samples maps here |
| **Cadence / Template** | org, name, steps, channel variants | e.g. `prospect_welcome_short_horizon` |
| **Interaction** `int_` | parties, property, topic, status, assignee, bot_paused, current sentiment and trend | Conversation or case |
| **InteractionEvent** `evt_` | interaction, actor, kind, channel, direction, source (system, webhook, manual), payload (JSONB), provider IDs, occurred_at | **Append-only** |
| **Decision** `dec_` | interaction, input snapshot, output (send/suppress, channel, send_at, subject, body, cta, next_action), reasons, guard results, model IDs, policy version, latency, cost | The bot's trace; the eval harness compares this to `expected` |
| **ScheduledSend** | decision, send_at, status (pending, sent, cancelled, blocked) | Re-checked when it fires |
| **DeliveryStatus** | event, provider status (queued, sent, delivered, bounced, opened, clicked, failed) | From provider webhooks |
| **SentimentScore** | event or external review, polarity (−1 to +1), label, emotion, intensity, topic, signals, confidence, model/version, corrected_by | One per scored event |
| **SentimentRollup** | scope (interaction, person, property, org), window, score, trend | Derived; drives queue ranking and dashboards |
| **Ticket** `tkt_` | interaction, type (maintenance, billing_dispute, complaint), status, priority | |
| **ReviewSource** `rsrc_` | property, provider (yelp, google, …), external business ID, auth/credential ref, sync schedule, last_synced_at, terms profile (what may be stored and for how long) | One per property per site |
| **ExternalReview** `rev_` | review_source, provider review ID, rating, text or excerpt (as the terms allow), author display name, posted_at, url, fetched_at, expires_at | Stored only as the provider's terms allow; purged at `expires_at` |
| **Attachment** `att_` | owner entity, storage key, mime type, scan status, extracted data | Stored in a bucket; the DB holds only metadata |
| **AuditLog** | actor, entity, action, before/after diff, at, request_id | Every write |
| **EvalRun / EvalResult** | implementation variant, case ID (REQ or ADD), per-field scores, pass/fail | Side-by-side comparison of alternatives ([#6](https://github.com/markfyoung0711/rp/issues/6)) |

## 5. Database recommendation: PostgreSQL (SQL)

**Recommendation: PostgreSQL** (Cloud SQL in deployment, Docker locally), using JSONB where the shape varies. **Not** a NoSQL store as the primary database.

Why:
- **The core data is relational, and its integrity matters.** Org → property → unit, person → contact point → consent, interaction → event → decision. Consent correctness is a legal requirement (TCPA/CAN-SPAM), and foreign keys and transactions ("revoke consent *and* cancel scheduled sends" in one commit) are exactly what SQL gives us.
- **Queries cut across entities.** Owner reports, the support queue ("negative sentiment, open, my properties, oldest first") and evals all need joins and aggregates.
- **JSONB covers the flexible parts** (profile attributes, event payloads, decision traces, provider webhooks) without a second database.
- **Isolating tenants** with row-level security by `org_id` adds a second layer of protection behind the API checks.
- **Real-time comes built in:** `LISTEN/NOTIFY` can push new events to the API's server-sent-events (SSE) stream for the three live panes in the demo.
- **Room to grow:**
  - `pgvector` if we later add retrieval (a knowledge base, similar past conversations)
  - partitioning the event table by month if volume grows
  - an analytics warehouse (e.g. BigQuery) fed from the database later, rather than now

Where NoSQL would fit: storing very large volumes of raw events, or when the schema really cannot be known in advance. Neither applies to the demo. Attachments and call recordings go in object storage (GCS), not the database.

Migrations with Alembic. The ORM is SQLAlchemy 2.x with Pydantic models at the API edge.

## 6. UX

### Surfaces

| Surface | Who | Key screens |
|---|---|---|
| **Login / account** | Everyone | Sign-in (email + password, or magic link); SMS/email code step; renter account claim; profile, contact-point and consent editor |
| **Owner app** | Customer | Onboarding wizard (org → properties → staff → brand/policy); policy editor (versioned, with diff); portfolio dashboard (outreach, conversions, tickets, sentiment by property/topic/channel); **reputation view** (public reviews and themes next to internal sentiment, review-reply drafts to approve); review-source settings; reports |
| **Support console** | Support | Queue ranked by urgency and sentiment; interaction view (timeline across every channel, decision trace, guard results, sentiment line); compose/approve/edit/hold; take over/hand back; click-to-call; "log off-system contact" form; ticket creation |
| **Renter phone** | Renter | Their *real* SMS thread and calls. In the demo, a phone mock-up pane with an SMS thread, incoming-call screen with keypad for automated calls, and voicemail |
| **Renter inbox** | Renter | Real email. In the demo, an inbox pane with the rendered email, CTA link and unsubscribe link |
| **Renter portal** | Renter | Mobile-first: conversations, book a tour, maintenance request with photo, upload a bill, preferences and opt-outs |

| **Demo control** | Presenter | Seed/reset, create an actor live with a "generate realistic person" helper, scenario player, implementation switch ([#8](https://github.com/markfyoung0711/rp/issues/8)) |

Common to all: dark/light theme, language picker (remembered; default en-US), accessible forms, and no data outside the viewer's role.

The UX builds on patterns from the UX prior-art study ([#3](https://github.com/markfyoung0711/rp/issues/3)): support consoles such as Zendesk, Intercom and Front; resident apps; owner dashboards; and decision-trace views. Each pattern is marked adopt, adapt or avoid.

### Demo layout

The screen splits into three live panes: **Owner | Support | Renter (phone + inbox)**. Each pane is signed in as a different demo user, and all three read the same event stream over SSE. An action in one pane shows up in the others within about a second. Across the bottom:

- **Scenario player:** loads `sample.jsonl` and the add-on cases and steps through them, including edge cases (no consent, quiet hours, STOP, angry complaint, injection attempt)
- **Trace strip:** for the selected event, shows the bot's path: gates → decision → content → guards → schedule, with the model, latency and cost
- **Implementation switch:** runs the same case through the alternative implementations in [#6](https://github.com/markfyoung0711/rp/issues/6) and shows the results side by side

### Demo flow

1. Owner approves quiet hours and the welcome cadence (UC-30).
2. The player loads `prospect_welcome_day0`. The bot sends an SMS for 09:00 local time, and it appears on the phone pane (UC-01 to UC-03). Support sees the trace (UC-20).
3. Renter taps "1" → tour booked → confirmation. The owner's dashboard counter goes up (UC-10, UC-31).
4. Renter sends an angry maintenance message. Sentiment drops, the conversation jumps up the support queue, and the bot acknowledges and pauses (UC-12, UC-14). Support takes over (UC-21).
5. Renter tries a prompt injection or asks for another resident's data → refused, and the guard shows in the trace (UC-41, UC-42).
6. Renter replies STOP → consent revoked, pending sends cancelled (UC-11).
7. Presenter creates a new renter live (lead form or inbound SMS). They appear in all three panes and are run through the player ([#8](https://github.com/markfyoung0711/rp/issues/8)).
8. A synthetic Google review about slow maintenance arrives. The owner's reputation view shows it lining up with the drop in internal maintenance sentiment, and the owner approves a drafted reply (UC-50).

## 7. Bot design

### Outbound decision pipeline (the graded core)

```
record/trigger
  → 1. Context      load Person, ContactPoints, Consent, Preferences, Relationship,
                    Policy version, recent events and sentiment (or a raw JSONL record)
  → 2. Gates        deterministic: consent exists? opted out? suppressed? bot paused?
                    open escalation? negative-sentiment pause?        → else SUPPRESS
  → 3. Decide       deterministic: channel = first preferred channel with consent;
                    send_at = next allowed slot in the person's timezone (quiet hours);
                    cta.type from primary_cta; next_action from lifecycle_stage/cadence
  → 4. Write        LLM (Sonnet 5): subject/body in brand style, personalized, with
                    channel-appropriate opt-out wording and CTA; structured output (JSON schema)
  → 5. Guard        fair housing, PII leak, opt-out present, CTA present, length/segments,
                    tone; regex + Haiku classifier; fail → rewrite once, then send to support queue
  → 6. Emit         Decision row (full trace) → ScheduledSend (or review queue) → event
```

**Design principles:**
- **Deterministic where the samples show a rule, LLM where language is needed.** Gating, channel and timing are code: testable, auditable, cheap. Writing the message is the LLM's job.
- **Structured output.** Every model call returns JSON validated against a Pydantic schema that matches `expected.next_message` / `next_action`.
- **"Learns only from input data".** The JSONL records are used in three ways:
  - as few-shot examples, retrieved by persona and lifecycle stage
  - as the source of the inferred rules, whose weak points the add-on cases test
  - as the eval set
  The alternative readings (templates only, a full LLM agent, rules learned by a model) are in [#6](https://github.com/markfyoung0711/rp/issues/6).
- **Model registry.** Each step names its model in config (Haiku 4.5 for classify/guard, Sonnet 5 for writing), so models can be swapped and compared in evals.
- **Everything is traced:** inputs snapshot, gate results, rule outputs, prompts (with PII redacted), model outputs, guard verdicts, latency, cost, and policy version.

### Inbound pipeline (add-on)

```
provider webhook / portal message
  → store InteractionEvent (raw)
  → classify (Haiku): intent {tour_choice, stop, question, maintenance, billing, complaint, other}
                      + sentiment {polarity, emotion, topic, signals}
  → route to handler: STOP → consent revoke · tour_choice → booking · maintenance → ticket ·
                      billing → dispute ticket (+ vision on attachment) · complaint/negative → escalate
  → handler may trigger the outbound pipeline for the reply
```

The handlers are the "adjacent agents" from [#5](https://github.com/markfyoung0711/rp/issues/5):
- intake/router
- scheduling
- maintenance
- billing dispute
- complaint/escalation
- renewal
- owner reporting
- compliance guard
- translation

To start, each is a plain function with tools. The design keeps them separable, so they can later be split into per-domain MCP servers.

### External review ingestion (add-on)

```
scheduler (e.g. daily per ReviewSource)
  → provider adapter (Yelp Fusion, Google Places / Business Profile, aggregator such as Birdeye/Yext/Reputation.com, Sandbox)
  → normalize → ExternalReview (only what the terms allow) → sentiment scorer (same model as inbound)
  → theme extraction (Haiku): maintenance, noise, staff, fees, parking, pests, safety, …
  → SentimentRollup (scope=property, source=external) → owner dashboard + alerts
```

- **Licensed APIs only; no scraping.** Sites such as Apartments.com, ApartmentRatings and Zillow without an API or a license are left out, or reached through a licensed aggregator. Scraping breaks their terms and is a legal risk (D-017).
- **Terms stored for each provider:** each adapter declares what may be stored, for how long, and how it must be displayed. For example, Yelp's API returns only a few review excerpts, and both Yelp and Google limit caching and require attribution. Verify these in [#3](https://github.com/markfyoung0711/rp/issues/3). Reviews past `expires_at` are purged, and only our derived scores and themes are kept, where the terms allow that.
- **Kept separate from internal data:** external sentiment is shown next to internal sentiment, never mixed into it, because the populations differ (public reviewers vs. our renters).
- **Demo:** a `SandboxReviewAdapter` supplies synthetic reviews, so the demo needs no API keys.

### Tools and authorization

The bot works on data only through tools (`get_person`, `get_consent`, `book_tour`, `create_ticket`, `schedule_send`, …). **Authorization is enforced inside each tool** using the scope of the calling interaction (org, property, person), never taken from the model's arguments. This way a prompt injection cannot reach another person's data, because the tool will not return it.

### Evaluation

The harness runs every REQ and ADD case through each implementation variant and scores each field:
- exact match: `channel`, `cta.type`, `next_action.type`
- within a tolerance: `send_at`
- semantic similarity plus an LLM judge against a rubric: `subject`, `body`
- checks on each constraint: opt-out present, no PII leak, fair housing

It reports the pass rate against the `thresholds` block, plus p95 latency and cost. Results are stored in EvalRun/EvalResult and shown side by side ([#6](https://github.com/markfyoung0711/rp/issues/6)).

## 8. APIs

REST over JSON. Every write checks the caller's role and scope, and writes to AuditLog.

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/login`, `POST /auth/otp/verify`, `POST /auth/magic-link`, `POST /auth/claim`, `POST /auth/logout` |
| Org setup | `POST/GET/PATCH /orgs`, `/orgs/{id}/properties`, `/properties/{id}/units`, `/orgs/{id}/users` (invite), `/orgs/{id}/policies` (new version) |
| People | `POST/GET/PATCH /persons`, `/persons/{id}/contact-points`, `/contact-points/{id}/consents` (append), `/persons/{id}/preferences`, `/persons/{id}/relationships` |
| Interactions | `GET /interactions?filters`, `GET /interactions/{id}` (timeline), `POST /interactions/{id}/events` (including manual off-system log), `POST /interactions/{id}/takeover`, `/handback` |
| Bot | `POST /bot/decide` (one record or JSONL line → Decision), `POST /decisions/{id}/approve`, `/edit`, `/hold` |
| Tickets and files | `POST/PATCH /tickets`, `POST /attachments` (signed upload URL) |
| Sentiment | `GET /sentiment/rollups?scope=…`, `POST /sentiment/{id}/correct` |
| External reviews | `POST/PATCH /properties/{id}/review-sources`, `POST /review-sources/{id}/sync` (manual pull), `GET /reviews?property=…&provider=…&sentiment=…`, `GET /reviews/themes?property=…`, `POST /reviews/{id}/draft-reply` (for human approval) |
| Reports | `GET /reports/portfolio`, `GET /reports/outreach` |
| Real-time | `GET /stream` (SSE, filtered to the caller's scope) |
| Webhooks | `POST /webhooks/sms`, `/webhooks/email`, `/webhooks/voice` (signature-verified) |
| Evals | `POST /evals/run`, `GET /evals/{id}` |

## 9. Security and PII

### What is sensitive

| Data | Sensitivity |
|---|---|
| Names, phone numbers, emails, addresses, move dates | PII |
| Lease terms, balances, uploaded bills | Financial PII |
| Call recordings, voicemail, transcripts, message bodies | PII, possibly sensitive (health, family, disability mentioned in free text) |
| Consent records | Legal evidence; must be accurate and tamper-evident |
| Sentiment scores | Derived personal data; internal only |
| Owner portfolio metrics | The customer's confidential business data |
| External reviews | Public, but the reviewer's name and text are personal data, and provider terms limit storage |

### Controls

- **Tenant isolation:**
  - every row carries `org_id`
  - API checks plus Postgres row-level security
  - support sees only the orgs and properties granted to them
- **Least-privilege views:**
  - the renter sees only their own data
  - the owner sees renter PII only where operations need it (e.g. a maintenance ticket), and aggregates otherwise
  - sentiment is never shown to renters
- **Encryption:**
  - TLS everywhere
  - Cloud SQL and GCS encrypted at rest
  - contact-point values and recordings encrypted at field level with a per-org key, which enables crypto-shredding
- **Keeping PII away from the LLM:**
  - send only the fields the step needs (first name, property, interests)
  - phones and emails never go into prompts; tools use tokens for them
  - use API settings with no training on data
  - PII is redacted from stored prompts and logs
- **Prompt injection:**
  - record fields and inbound text are passed as delimited *data*
  - authorization lives in the tools, not the prompt
  - output guards run before anything is sent
  - injection attempts are logged and appear as ADD test cases
- **External reviews:**
  - Never try to match a public reviewer to a renter record. That would de-anonymize them, is a privacy risk, and invites retaliation claims.
  - Review sentiment is never used to treat a renter differently.
  - Never generate, solicit with incentives, or suppress reviews (FTC rule on fake reviews and review suppression). Replies are drafted for a human to approve.
  - Obey each provider's storage, caching and attribution rules.
- **Uploads:**
  - type/size allow-list and malware scan
  - stored privately, served by signed URLs
  - text extracted from an upload is treated as untrusted data
- **Webhooks:** provider signatures are verified, and repeated deliveries are ignored (by provider message ID).
- **Retention and deletion:**
  - the event log is append-only for audit, yet renters have CCPA/state rights to deletion
  - resolve this with **crypto-shredding** (destroy the person's key) plus a tombstone that keeps the consent and audit trail without the PII
  - retention periods set per data type
- **Compliance guards:**
  - Fair Housing: no steering or protected-class language, and sentiment and personalization must not use protected traits
  - TCPA: consent per channel, quiet hours, STOP handling
  - CAN-SPAM: unsubscribe and sender identity
  - call-recording consent: varies by state
  - FTC rule on fake reviews: no fake, incentivized or suppressed reviews ([#10](https://github.com/markfyoung0711/rp/issues/10))
  - antitrust and pricing: see §13
- **Audit:** every write, every human action on a bot decision, and every access to a sensitive record is logged with the actor and request ID.
- **Demo posture:** synthetic data only (e.g. Taylor, Oak Ridge), sandbox channels by default, no real phone numbers or emails unless explicitly turned on, secrets in Secret Manager, and never in the repo.

## 10. Authentication and authorization

### Recommendation for the demo

- **Self-issued sessions:**
  - FastAPI issues a short-lived signed JWT in an **HttpOnly, Secure, SameSite cookie**, plus a rotating refresh token
  - passwords hashed with **argon2**
  - no third-party identity provider is needed to run the demo
- **Real login forms, sandbox second factor.** Email + password, then a 6-digit code "sent" by SMS or email. In sandbox mode the code arrives in the phone or inbox pane on screen, so the demo shows the full flow without real carriers. Renters use a magic link or SMS code to claim their account.
- **Seeded demo users**, one per role:
  - owner@oakridge.example
  - support@platform.example
  - taylor (renter)
  - an admin
  These are loaded with a seed script, and each pane logs in as its own user. A "quick sign-in" button per pane is available **only when `DEMO_MODE=true`**.
- **Authorization:**
  - role-based access (owner, staff, support, renter, admin), **scoped** by org/property/person through RoleGrant
  - enforced in a FastAPI dependency on every route, and again in bot tools
  - Postgres row-level security as the backstop
- **Service identity:** the bot runs as `svc_bot` with its own scoped grants; webhooks authenticate by provider signature.

### Path to production

Replace self-issued login with an OIDC provider (**GCP Identity Platform**, or Auth0/Cognito):
- enterprise SSO (SAML/OIDC) for support staff and large owners
- MFA enforced for staff and support
- passwordless for renters

Our role and scope model stays the same; only the login changes.

## 11. Deployment (brief)

- **Hosting:** one Cloud Run service (FastAPI serves the API, SSE and the built React app), Cloud SQL Postgres, GCS for attachments, Secret Manager for keys
- **Scheduled sends:** Cloud Scheduler or Cloud Tasks
- **Providers:** email, SMS and voice sit behind an adapter interface: `SandboxAdapter` for the demo, and e.g. SendGrid and Twilio live
- **Review sync:** Cloud Scheduler triggers a sync for each ReviewSource; provider keys are in Secret Manager
- **Locally:** `docker compose` (API + Postgres), with sandbox channels and sandbox reviews; `make seed` loads the demo baseline

## 12. Open questions

- One Person or two for a renter who rents from two owners? This affects privacy between owners and deletion.
- Record calls, or keep only metadata? Recording consent varies by state.
- Score sentiment on every inbound event, or only when a cheap first pass flags it? Do owners set the escalation thresholds?
- How structured must manual off-system logs be for reports to be trustworthy?
- Which alternatives from [#6](https://github.com/markfyoung0711/rp/issues/6) do we build, and who builds each?
- Which review sites are in scope, and through which licensed API or aggregator? Is an aggregator worth the cost compared with direct Yelp and Google integration? ([#10](https://github.com/markfyoung0711/rp/issues/10))
- What will the independent review ([#9](https://github.com/markfyoung0711/rp/issues/9)) overturn? Record the answers in `decisions.md`.

## 13. Competitive and legal guardrails

These come from the competitive-intel work in [#3](https://github.com/markfyoung0711/rp/issues/3) (D-017). The findings are still to be checked against sources.

| Industry risk | Our design stance |
|---|---|
| Algorithmic rent pricing / antitrust (the cases against RealPage and landlords) | The bot never sets, recommends or discusses rent pricing, and never uses pooled or nonpublic competitor data. Pricing is out of scope. |
| Tenant-screening accuracy and disparate impact | No screening. Protected traits and stand-ins for them are never used in targeting, tone or sentiment use (UC-40). |
| Junk fees, dark patterns | Fees shown transparently, billing disputes handled (UC-13); no fake urgency, no auto-renewal traps, opt-out never buried. |
| TCPA / CAN-SPAM suits | Consent per channel, quiet hours, STOP, re-check at send time (UC-11, UC-43). |
| Fake or suppressed reviews (FTC) | Review replies need human approval; we never solicit or suppress reviews (UC-50). |
| Data breaches, privacy suits | §9 controls; synthetic data only in the demo. |
| AI transparency / "can't reach a human" | The bot says it is a bot, and a human is always reachable (UC-14, UC-21). |

The pain points from [#3](https://github.com/markfyoung0711/rp/issues/3) (renter: maintenance delays, unresponsive management, repeating themselves, fee surprises; owner: slow lead response, leads slipping through, no view of sentiment) map onto the use cases in §3. The full pain point → solution table lives in `plans/prior-art.md`.

## 14. Demo data and seeding

([#8](https://github.com/markfyoung0711/rp/issues/8))

- **Baseline seed:**
  - one command, safe to re-run (`make seed` / `POST /demo/seed`)
  - creates organizations, properties, policy, staff, support agents and renters, including the people in `sample.jsonl` and the edge-case people from [#5](https://github.com/markfyoung0711/rp/issues/5)
  - also demo login users (§10), sandbox review sources with synthetic reviews, and optional history so the dashboards aren't empty
- **Live creation:** new actors are created through the real onboarding and lead APIs, not a back door. A "generate realistic person" helper fills the form.
- **Origin tag** on every record (`seed`, `demo_created`, `jsonl_import`, `sandbox_review`). A reset either restores the baseline or clears only what was created during the demo, without a restart.
- **Synthetic only:** `*.example` domains, 555 numbers, no real PII (D-016).

---

# Part 3 — Actor walkthroughs

> **ADD-ON (MFY).** How the system works from each actor's point of view. The data model and UX are covered in Part 2.

The system has five actors. Four are parties: the **customer** (property owner/operator), **customer support**, the **renter/prospect**, and the **bot**. The fifth is the **interaction** itself: every contact between any two parties, whether it happens in the app, over email or SMS, on a phone call, or entirely outside the system and logged afterwards.

Every party has the same lifecycle:
1. **Onboard:** create their identity and identifiers.
2. **Maintain:** edit who they are, their contact points, their consents and their preferences.
3. **Interact.**

Each step is a persisted record behind a create/update API, and each change is written to an audit log.

---

## 1. Customer (property owner / operator)

**Onboarding.** An owner is invited by support, or signs up, from a login screen: email plus password, then an SMS code to prove they hold the phone number. They then set up their organization:

- **Organization:** legal name, brand name, billing contact
- **Portfolio:** one or more properties, each with an address, timezone, units, and a public name (e.g. "Oak Ridge Apartments")
- **Staff:** they invite their own leasing and maintenance people as users, with roles
- **Brand and policy:** tone of voice, logo, sender name, email sending domain, SMS number, quiet hours, and cadences they approve (e.g. `prospect_welcome_short_horizon`)
- **Integrations:** property-management system, calendar for tour slots, and so on (later)

**Editing who they are.** The owner can change organization details, add or retire properties, change brand and policy, and manage staff. Policy changes are versioned, so we can always say which policy was in force when a message went out.

**Day to day.** The owner opens a portfolio dashboard:
- outreach sent and suppressed
- tours booked
- open maintenance requests and complaints
- escalations
- **sentiment trends** by property, by channel and by topic (e.g. "maintenance sentiment at Oak Ridge has dropped for three weeks"), with the worst conversations one click away
- **public reputation:** Yelp, Google and other review-site ratings, sentiment and themes for each property, shown *next to* internal sentiment (never blended). Drafted replies to reviews wait for the owner's approval ([#10](https://github.com/markfyoung0711/rp/issues/10)).

They get a daily or weekly summary by email. They can call or email support, and those contacts are logged as interactions (see §5).

**Identifiers:** `org_…`, `prop_…`, `unit_…`, `user_…` for each staff member.

## 2. Customer support

**Onboarding.** Support agents are platform staff, created by an admin. They sign in with SSO or a password plus a second factor. Each agent is assigned to organizations and properties, and can only see those.

**Editing who they are.** Display name, skills (language, billing, maintenance), working hours, and whether they are on call for escalations.

**Day to day.** The agent works a queue:
- conversations the bot has flagged, such as complaints, low confidence, a guard firing, or a renter asking for a human
- messages waiting for approval, if the owner's policy requires review

The queue is sorted by urgency, and **negative or worsening sentiment** raises an item's priority. A sharp drop, such as a calm renter turning angry, can on its own put a conversation in the queue.

For each item the agent sees:
- the full interaction timeline across every channel
- the bot's decision trace (send or suppress, which channel, what time, why)
- the guard results
- a sentiment line across the timeline: the score for each inbound message and the trend for the conversation

The agent can:
- approve, edit or hold a message
- take over the conversation (the bot stops) and later hand it back
- place or log a phone call
- write an internal note
- open a maintenance or billing ticket

They also answer platform questions from owners, such as billing and configuration.

**Identifiers:** `user_…` with role `support`; `queue_item_…`.

## 3. Renter / prospect

**Onboarding.** A renter usually arrives before they have an account: a lead from a listing site, a web form, a phone call, or a walk-in. The system creates a **person** record with whatever it has (first name, phone and/or email, property of interest, move date). This is the `input` block in `sample.jsonl`. At that point the renter has no login.

**Consent.** Consent is recorded *per contact point and per channel*: opted in to email, SMS or voice, when, how (form checkbox, keyword reply, verbal on a call), and a copy of the wording they agreed to. STOP by SMS, an unsubscribe link, or "don't call me" on a call revokes it immediately, on that channel.

**Becoming a user.** When they want self-service (a resident portal, maintenance requests, uploads), they claim their account through a magic link or SMS code sent to a contact point we already hold. That links the login to the existing person record, so no duplicate is created.

**Editing who they are.** Name, preferred language, contact points (add, verify, remove), channel preferences and their order, consents, and quiet-hour preferences.

**Day to day.** The renter mostly lives on their own phone and in their email:
- they get SMS messages and reply to them (e.g. "1" to book Thursday)
- they get emails with links
- they may get an automated call: "Press 1 to confirm your tour"

In the portal they can see their conversations, book tours, submit maintenance requests with photos, upload a disputed bill, and manage their preferences. The renter never sees the bot's internals or anything about other residents.

**Identifiers:** `person_…` (exists from first contact), `contact_…` for each phone or email, `lease_…` or `lead_…` for the relationship to a property, and `user_…` once they claim an account.

## 4. Bot

**Onboarding.** The bot is configured per organization rather than signed up. The config includes:
- which model runs each step
- which policy version applies
- which cadences are on
- the guard settings

The bot gets a service identity (`svc_bot`), so every one of its actions is attributable, just like a human's.

**Day to day.** When an event arrives, the bot:
1. Reads the person, their consents, their preferences and the interaction history.
2. Decides whether to send, which channel, what time, and what to say.
3. Runs the guards (fair housing, PII, opt-out wording, prompt injection).
4. Either schedules the message or puts it in the support queue.
5. Records its full decision trace against the interaction.

Events that trigger the bot include a new lead, a reply, a scheduled step in a cadence, and a change to a lease date. When a reply comes in, the bot classifies it (e.g. tour choice, STOP, question, complaint) and scores its sentiment. It then advances the cadence or escalates. Sentiment also shapes its next move: an upset renter gets an acknowledgement and a hand-off rather than a sales CTA, and cadence messages are paused while an interaction is negative. It never contacts anyone without a consent record for that channel.

## 5. Interaction (the fifth actor)

An **interaction** is one conversation or case between parties, for example "Taylor's tour inquiry at Oak Ridge". It is made up of **interaction events**, each an immutable record of something that happened:

| Event kind | Examples | How it gets in |
|---|---|---|
| Message out | Email, SMS or voice call sent by the bot or a human | Our send APIs, confirmed by the provider's delivery webhooks |
| Message in | SMS reply, email reply, voicemail, keypress on an automated call | Provider webhooks for inbound SMS, email and voice |
| In-app action | Login, tour booked, file uploaded, preference changed | App API |
| Decision | The bot's send/suppress decision with its reasons and guard results | Bot |
| Human action | Approve, edit, take over, internal note, escalate | Support UI |
| **Off-system** | A leasing agent calls the renter from a personal phone; the owner emails support directly; a walk-in conversation | Logged afterwards by hand (a "log a call/email/visit" form), or captured automatically (below) |

**Capturing off-system activity as far as possible:**
- **Email:** every outbound email includes a unique reply-to address per interaction, so replies thread automatically. Staff can BCC or forward to an intake address and the email gets attached to the right person.
- **Phone:** each property gets a tracking phone number that forwards to staff. Calls through it are logged automatically, with duration and an optional recording or transcript where consent allows.
- **Anything else:** a manual log entry, with who, when, which channel, a summary, and the outcome. It is marked `source: manual` so reports can tell it apart from verified activity.

Every event records:
- `actor` (who did it)
- `channel`
- `direction`
- `source` (system, provider webhook, or manual)
- the raw payload

### Sentiment tracking

Every **inbound** event that contains words gets a sentiment record: SMS or email replies, voicemail and call transcripts, in-app messages, and manual call notes (these last are flagged, since the words are the staff member's summary, not the renter's own). Each record holds:

- **Polarity:** a score from −1 to +1, plus a label (negative, neutral, positive)
- **Emotion or intensity:** e.g. frustrated, angry, anxious, pleased, and how strongly
- **Topic it attaches to:** maintenance, billing, tour, noise, staff, and so on, so we can say "angry *about billing*" rather than just "angry"
- **Signals behind the score:** e.g. repeated contact, all caps, threats to leave or to post reviews, the phrase "third time asking"
- **Provenance:** model and version, confidence, and whether a human corrected it

From those records the system keeps rolling aggregates:

- **Per interaction:** current sentiment and trend (improving, worsening), used for queue priority and escalation
- **Per person:** relationship health across all their interactions, a signal for renewal and retention risk (UC-15)
- **Per property and organization:** trends by topic and channel for the owner dashboard and reports

**External reviews** ([#10](https://github.com/markfyoung0711/rp/issues/10)) go through the same scorer. They are pulled per property from licensed review-site APIs and kept as their own source, never mixed with renter sentiment. We never try to work out which renter wrote a public review.

Outbound messages are also scored for *tone*, as a guard that the bot's own messages stay courteous and on-brand.

**What sentiment is not used for:** it must not change *how people are treated* in ways that touch fair-housing categories, and it is never shown to the renter. Support can correct a score, and the correction is stored as feedback for evaluating the model.

This gives one timeline per person and per property across every channel. That timeline is what support reviews, what owner reports count, and what the bot reads as history.

---

## Communication facilities

| Channel | Outbound | Inbound | Tracked |
|---|---|---|---|
| Email | Provider API (e.g. SendGrid or SES) using the owner's verified sending domain | Inbound parse webhook, reply-to per interaction | Sent, delivered, bounced, opened, clicked, replied, unsubscribed |
| SMS | Provider API (e.g. Twilio) from the property's number | Inbound webhook; STOP/HELP keywords handled by the provider *and* by us | Queued, sent, delivered, failed, replied, opted out |
| Voice (automated call) | Provider voice API: text-to-speech script plus keypad menu ("Press 1…") | Keypresses, voicemail, call status webhooks | Dialed, answered, machine-detected, keypresses, duration |
| Voice (human) | Click-to-call from the support UI through the tracking number | Tracking number forwarding | Call log, duration, recording/transcript if consented |

Quiet hours and consent are checked **at send time**, not only when the message is scheduled.

For the demo, a **sandbox mode** sends to a simulated phone and inbox shown on screen instead of real carriers. The same events still flow, so the demo works without real numbers or email domains, and switching to live mode only swaps the provider adapter.

---

# Part 4 — Use-case traceability

> Who takes part in each use case, and which issue covers it. How each one works is in Part 2 §3.

## Original scope (from the assignment)

| ID | Use case | Primary actor | Source |
|---|---|---|---|
| UC-01 | Decide whether to contact the recipient (consent, suppression, timing) | Bot → Renter | spec.md |
| UC-02 | Choose the channel and send time (preferences, consent, timezone) | Bot → Renter | spec.md, sample.jsonl |
| UC-03 | Write a personalized, compliant message with a CTA and set the next action | Bot → Renter | spec.md, sample.jsonl |

## Add-on scope (Mark F. Young)

| ID | Use case | Primary actor | Also involved | Issue |
|---|---|---|---|---|
| UC-10 | Prospect replies (e.g. "1" for Thu) → tour booked → confirmation sent | Renter | Bot, Support | [#5](https://github.com/markfyoung0711/rp/issues/5), [#7](https://github.com/markfyoung0711/rp/issues/7) |
| UC-11 | Prospect replies STOP → opt-out applied on every channel, confirmation sent | Renter | Bot, Support | [#5](https://github.com/markfyoung0711/rp/issues/5) |
| UC-12 | Renter submits a maintenance request (optionally with a photo) → work order → status updates | Renter | Bot, Support, Customer | [#5](https://github.com/markfyoung0711/rp/issues/5) |
| UC-13 | Renter disputes a charge by uploading a bill with the item marked → dispute ticket | Renter | Support, Customer | [#5](https://github.com/markfyoung0711/rp/issues/5) |
| UC-14 | Renter complains repeatedly or is angry → escalated to a human, with context | Renter | Support | [#5](https://github.com/markfyoung0711/rp/issues/5) |
| UC-15 | Renewal outreach ahead of lease end → renewal offer or retention hand-off | Bot → Renter | Customer | [#5](https://github.com/markfyoung0711/rp/issues/5) |
| UC-20 | Support reviews the bot's decisions (with reasons), edits or holds a message before it is sent | Support | Bot | [#7](https://github.com/markfyoung0711/rp/issues/7) |
| UC-21 | Support takes over a conversation and hands it back to the bot | Support | Renter, Bot | [#7](https://github.com/markfyoung0711/rp/issues/7) |
| UC-22 | Support handles a platform question from the customer (billing, configuration) | Customer | Support | [#3](https://github.com/markfyoung0711/rp/issues/3) |
| UC-30 | Customer sets outreach policy (cadence, brand style, quiet hours) and approves templates | Customer | Support, Bot | [#7](https://github.com/markfyoung0711/rp/issues/7) |
| UC-31 | Customer views a portfolio report (outreach, conversion, escalations, maintenance, complaints) | Customer | — | [#5](https://github.com/markfyoung0711/rp/issues/5) |
| UC-40 | Guard: a fair-housing or discriminatory request is refused and logged | Bot | Support | [#4](https://github.com/markfyoung0711/rp/issues/4), [#5](https://github.com/markfyoung0711/rp/issues/5) |
| UC-41 | Guard: prompt injection in profile or reply text is ignored | Bot | Support | [#5](https://github.com/markfyoung0711/rp/issues/5) |
| UC-42 | Guard: cross-account or PII request is refused; each role sees only what it is allowed to | Bot | All | [#5](https://github.com/markfyoung0711/rp/issues/5), [#7](https://github.com/markfyoung0711/rp/issues/7) |
| UC-43 | Guard: quiet hours / TCPA — the send is delayed to an allowed time | Bot | — | [#4](https://github.com/markfyoung0711/rp/issues/4) |
| UC-50 | External review sentiment: pull Yelp, Google and other reviews per property, score them, and show them next to internal sentiment; draft replies for a human to approve | Customer | Support, Bot | [#10](https://github.com/markfyoung0711/rp/issues/10) |

---

# Part 5 — Decision register

This records how the work departs from, or adds to, the **original assignment** ([`spec.md`](spec.md) § Problem Statement and [`sample.jsonl`](sample.jsonl)). Those two files are the baseline and stay unedited. Everything else is an add-on and is listed here.

**Origin:** `ORIGINAL` = from the assignment · `ANALYSIS` = inferred from the assignment's data, or proposed by a reviewer · `ADD-ON (MFY)` = Mark F. Young's extension
**Status:** proposed · recommended (by the reviews; awaiting Mark's acceptance) · accepted · rejected · superseded

| ID | Date | Decision | Origin | Status | Rationale | Affects |
|---|---|---|---|---|---|---|
| D-001 | 2026-09-24 | Baseline: the problem statement and `sample.jsonl` are the graded requirements (REQ-xx). They are kept word for word in `plans/spec.md` (problem statement and sample records) and `plans/sample.jsonl`; our analysis is in `plans/sample-analysis.md`. | ORIGINAL | accepted | Keeps the graded scope separate from our extensions | spec.md, sample.jsonl |
| D-002 | 2026-09-24 | Rules inferred from the samples: channel = first preferred channel the recipient has opted in to; send in the morning, recipient's local time; opt-out wording per channel; `primary_cta` → `cta.type` | ANALYSIS | to be superseded by D-023 (send time) once accepted | Only 2 samples, so these are hypotheses to confirm ([#2](https://github.com/markfyoung0711/rp/issues/2), [#4](https://github.com/markfyoung0711/rp/issues/4)) | sample-analysis.md |
| D-003 | 2026-09-24 | Widen the scope to three actors (renter, customer support, customer/owner) and the use cases UC-10 to UC-43 | ADD-ON (MFY) | accepted | Shows the bot in a realistic system; supports interview discussion | use-cases.md, [#5](https://github.com/markfyoung0711/rp/issues/5), [#7](https://github.com/markfyoung0711/rp/issues/7) |
| D-004 | 2026-09-24 | Track tests in two lists: original REQ-xx and add-on ADD-xx | ADD-ON (MFY) | accepted | Keeps the graded pass rate separate from the extensions | tests.md (planned), [#5](https://github.com/markfyoung0711/rp/issues/5) |
| D-005 | 2026-09-24 | Adjacent agents (intake/router, maintenance, complaint, billing dispute, renewal, owner reporting, compliance guard, scheduling, translation) exist only as add-on tests | ADD-ON (MFY) | proposed | Covers the wider system without widening the graded scope | [#5](https://github.com/markfyoung0711/rp/issues/5) |
| D-006 | 2026-09-24 | Build 2–3 alternative implementations and compare them side by side on one shared set of tests, chosen together with the engineer | ADD-ON (MFY) | proposed | Makes the trade-offs visible (cost, safety, accuracy, how easy each is to explain) | [#6](https://github.com/markfyoung0711/rp/issues/6) |
| D-007 | 2026-09-24 | A UI with three panes (renter, support, customer), synced in real time and visible at the same time for the demo | ADD-ON (MFY) | proposed | Lets the demo show one interaction flowing across all three roles | [#7](https://github.com/markfyoung0711/rp/issues/7) |
| D-008 | 2026-09-24 | Every actor has onboarding, identity editing and stable prefixed IDs (`org_`, `prop_`, `person_`, `contact_`, `user_` …). A renter exists as a Person before they have a login. | ADD-ON (MFY) | proposed | Leads arrive before accounts do; keeps one record per person | actors.md |
| D-009 | 2026-09-24 | The interaction is a first-class actor: an append-only event timeline across every channel, including off-system contact that is logged by hand or captured (reply-to addresses, tracking numbers) | ADD-ON (MFY) | proposed | One timeline for support, owner reporting and the bot's history | actors.md |
| D-010 | 2026-09-24 | Email, SMS and voice (automated and human) through provider adapters, with a sandbox mode for the demo. Consent and quiet hours are re-checked at send time. | ADD-ON (MFY) | proposed | Real channels without blocking the demo on carrier or domain setup | actors.md, [#7](https://github.com/markfyoung0711/rp/issues/7) |
| D-011 | 2026-09-24 | Create/read/update APIs for every persisted entity, with soft deletes, versioned policy and consent records, and an audit log on every write | ADD-ON (MFY) | proposed | Traceability, and the ability to say which policy or consent was in force for a decision | actors.md |
| D-012 | 2026-09-24 | Track sentiment on every inbound event that has words, recording score, emotion, topic and signals, with rollups per interaction, person, property and org. It drives queue priority, escalation, pausing cadences, owner trends and a tone check on outbound messages. Never shown to renters, never used in ways that touch fair-housing categories, and support can correct it. | ADD-ON (MFY) | proposed | Surfaces unhappy renters early, tells owners where things are going wrong, and gives the bot a signal for how to reply | actors.md, [#5](https://github.com/markfyoung0711/rp/issues/5), [#7](https://github.com/markfyoung0711/rp/issues/7) |
| D-013 | 2026-09-24 | Database: PostgreSQL (Cloud SQL), with JSONB for flexible payloads, row-level security by org, LISTEN/NOTIFY for real-time, and GCS for files. Not NoSQL. | ADD-ON (MFY) | proposed | Relational core; consent integrity needs transactions; reports need joins; one database covers the flexible parts too | design.md §5 |
| D-014 | 2026-09-24 | Bot: deterministic gates, channel choice and timing; LLM (Sonnet 5) writes content with structured output; Haiku 4.5 guards and classifiers; authorization enforced inside tools; full decision trace | ADD-ON (MFY) | proposed | Testable rules where the samples show a rule, LLM only for language; stops prompt injection reaching data | design.md §7, [#6](https://github.com/markfyoung0711/rp/issues/6) |
| D-015 | 2026-09-24 | Demo auth: self-issued JWT in an HttpOnly cookie, argon2, second-factor code delivered to the sandbox, seeded users per role, quick sign-in only in `DEMO_MODE`. Production: OIDC (GCP Identity Platform), SSO and MFA. | ADD-ON (MFY) | proposed | The login flow is real enough to demo without an outside dependency; the role model carries over to production | design.md §10 |
| D-016 | 2026-09-24 | PII: field-level encryption with a per-org key, crypto-shredding for deletion, minimal PII sent to the LLM, redacted logs, synthetic data only in the demo | ADD-ON (MFY) | proposed | Reconciles an append-only audit log with deletion rights; limits what reaches the model | design.md §9 |
| D-017 | 2026-09-24 | The prior-art work ([#3](https://github.com/markfyoung0711/rp/issues/3)) includes competitive intel: legal exposure of RealPage and its peers (algorithmic pricing antitrust, screening, junk fees, TCPA, privacy), practices to avoid by design (no rent setting or pooled competitor data, no dark patterns, disclose the bot, always offer a human), and renter/owner pain points turned into a pain point → solution table | ADD-ON (MFY) | accepted | Solve real pain points while staying clear of the industry's known legal risks | [#3](https://github.com/markfyoung0711/rp/issues/3), prior-art.md (planned) |
| D-018 | 2026-09-24 | Fetch external review sentiment (Yelp, Google, others) per property through licensed provider APIs or aggregators, behind adapters with each provider's storage terms enforced. Score it with the same sentiment pipeline and show it next to internal sentiment. No scraping, no matching reviewers to renters, no fake or suppressed reviews; replies need human approval. | ADD-ON (MFY) | proposed | The public view of a property is a key owner pain point and a check on internal sentiment; kept within provider terms and FTC rules | design.md (UC-50, §4, §7, §8, §9), [#10](https://github.com/markfyoung0711/rp/issues/10) |
| D-019 | 2026-09-24 | Demo data: a baseline seed that is safe to re-run, plus live actor creation through the real onboarding and lead APIs; an `origin` tag on every record so a reset can restore the baseline or clear only what the demo created | ADD-ON (MFY) | proposed | The demo shows onboarding working, and resets cleanly without a restart | design.md §14, [#8](https://github.com/markfyoung0711/rp/issues/8) |
| D-020 | 2026-09-24 | An independent critical review of the spec and plans, plus prior-art research (including UX prior art), comes first, before the detailed spec ([#4](https://github.com/markfyoung0711/rp/issues/4)) is locked | ADD-ON (MFY) | accepted | Catch overfit inferences and scope creep while they are cheap to fix | [#9](https://github.com/markfyoung0711/rp/issues/9), [#3](https://github.com/markfyoung0711/rp/issues/3) |
| D-021 | 2026-09-24 | Delivery deadline: a **working, demoable system by 12:00 noon CST on 2026-09-24**. In the interview, a **hold-out set** is provided, and we must export or copy-paste its **12 outputs**. So the system needs a batch mode: take a JSONL file (uploaded or pasted) and produce one output record per input, in the `expected` shape, as a downloadable JSONL file and a copyable block. | ORIGINAL | accepted | A requirement from the interviewer. It outranks every add-on: the graded core and the hold-out export come before D-003 to D-020 | spec.md, [#4](https://github.com/markfyoung0711/rp/issues/4), [#9](https://github.com/markfyoung0711/rp/issues/9) |
| D-022 | 2026-09-24 | Core is a self-contained decision step (record in, decision out) with no database. All platform components are add-ons, gated on the core passing unseen test cases. | ANALYSIS (Review 1 (Sonnet 5)) | recommended (both reviews agree) | Review findings F-03, F-04; see `review.md` | review.md |
| D-023 | 2026-09-24 | Send time = cadence offset (e.g. `day3` → +3 days from `last_interaction`) plus a local hour, with `now` as an explicit input. Supersedes the "shared today / next morning" reading in D-002. | ANALYSIS (Review 1 (Sonnet 5)) | recommended (both reviews agree) | Review findings F-01, App. A; see `review.md` | review.md |
| D-024 | 2026-09-24 | Property facts (amenities, tour link, tour slots) come from a declared source. The writer may not state unsourced facts; a missing fact drops the claim. | ANALYSIS (Review 1 (Sonnet 5)) | proposed | Review findings F-02; see `review.md` | review.md |
| D-025 | 2026-09-24 | Opt-out wording and CTA are composed by fixed code; the LLM writes only a free-text slot, and there is a guaranteed non-LLM fallback. | ANALYSIS (Review 1 (Sonnet 5)) | recommended (both reviews agree) | Review findings F-09; see `review.md` | review.md |
| D-026 | 2026-09-24 | A separate set of 20–30 varied test cases, kept out of prompts and rules, simulates the hold-out. The two samples are not the only evaluation. | ANALYSIS (Review 1 (Sonnet 5)) | recommended (both reviews agree) | Review findings F-03; see `review.md` | review.md |
| D-027 | 2026-09-24 | Consent is scoped by sender, channel and purpose; STOP is matched by a fixed keyword check before any model. | ANALYSIS (Review 1 (Sonnet 5)) | proposed | Review findings F-06; see `review.md` | review.md |
| D-028 | 2026-09-24 | Sentiment may not gate outreach or routing until a parity test passes; human-only intents defined (accommodation requests, discrimination complaints, legal threats, emergencies). | ANALYSIS (Review 1 (Sonnet 5)) | proposed | Review findings F-10; see `review.md` | review.md |
| D-029 | 2026-09-24 | Renewal outreach carries no price content. | ANALYSIS (Review 1 (Sonnet 5)) | proposed | Review findings F-11; see `review.md` | review.md |
| D-030 | 2026-09-24 | Voice dialing and external reviews ([#10](https://github.com/markfyoung0711/rp/issues/10)) deferred; the consent fields stay in the model. | ANALYSIS (Review 1 (Sonnet 5)) | proposed | Review findings F-04; see `review.md` | review.md |
| D-031 | 2026-09-24 | CLI batch processor `run_eval.py --input <jsonl> --output <jsonl>`: stateless, no database, records processed concurrently, per-record latency measured against the 2,000 ms p95, and one bad record never stops the batch. Built first; any UI wraps this same function. | ANALYSIS (Review 2, Gemini) | recommended | Both reviews converge on it, or it is new from the SME; see `review.md` § Reconciliation | review.md |
| D-032 | 2026-09-24 | The `sample.jsonl` records (input + expected) go into the writer prompt as few-shot examples. This is the "learns only from input data" story. Mock hold-out cases stay out of the prompt. | ANALYSIS (Review 2, Gemini) | recommended | Both reviews converge on it, or it is new from the SME; see `review.md` § Reconciliation | review.md |
| D-033 | 2026-09-24 | A fixed TCPA keyword gate (STOP, STOPALL, UNSUBSCRIBE, CANCEL, END, QUIT) runs first on any inbound text: no message, no LLM call. Carries out the STOP part of D-027. | ANALYSIS (Review 2, Gemini) | recommended | Both reviews converge on it, or it is new from the SME; see `review.md` § Reconciliation | review.md |
| D-034 | 2026-09-24 | Protected-class details (familial status, religion, disability, national origin, …) are removed from the profile before the prompt; the output is checked for them; nothing offered changes. A mock hold-out case covers the familial-status trap. | ANALYSIS (Review 2, Gemini) | recommended | Both reviews converge on it, or it is new from the SME; see `review.md` § Reconciliation | review.md |
| D-035 | 2026-09-24 | A fallback table for unknown or transactional `primary_cta` values (e.g. `sign_lease`, `collect_deposit`): a transactional tone, the opt-out wording kept, and the link taken from the property-facts source or a flagged placeholder, never invented (per D-024). | ANALYSIS (Review 2, Gemini) | recommended | Both reviews converge on it, or it is new from the SME; see `review.md` § Reconciliation | review.md |
| D-036 | 2026-09-24 | The send hour is set per channel in config (SMS 09:00, email 10:00, from the samples) and stated as an assumption, since the data can't tell a channel effect from a cadence effect. Refines D-023. | ANALYSIS (Review 2, Gemini) | proposed | Both reviews converge on it, or it is new from the SME; see `review.md` § Reconciliation | review.md |
| D-037 | 2026-09-24 | Build spec for today = the review 2 core blueprint: (1) ingest and validate each record; (2) consent/suppression gate in code (no LLM when no channel has consent); (3) channel = first preferred channel with consent; send time = local(`last_interaction`) + day offset from the task ID/cadence, at the channel's hour, rolled forward a day if not after `last_interaction`; (4) a structured LLM call fills only the text fields, with `sample.jsonl` as few-shot examples; (5) output in the `expected` shape plus `task_id`. Records run concurrently with a per-record try/except. The drop list (database, React UI, real Twilio/SendGrid, reviews, inbound webhooks) is deferred. | ANALYSIS (Review 2, Gemini) | superseded by D-038 | The two reviews converge on it; the send-time roll-forward is our correction so that `day0` reproduces | review.md |
| D-038 | 2026-09-24 | **Merged core build spec** (review 1 + review 2 addenda; see `review.md` § Merged core build spec). A template baseline that always works; an optional `--llm` mode (samples as few-shot examples, free-text part only, temperature 0 plus a cache); opt-out and CTA in fixed code; review 1's send-time, `next_action`, guard and property-facts rules; JSONL, JSON array or pretty-printed input; a combined output file plus a readable per-record view; deterministic re-runs. Voice is skipped. Supersedes D-037 as the build spec. | ANALYSIS (Reviews 1 + 2) | recommended | Keeps the demo safe without the LLM, and uses the LLM to answer "learns from input data" | review.md |
| D-039 | 2026-09-24 | Review 2's reference `bot.py` (Gemini) is kept unchanged in `reference/bot_gemini.py` for comparison, **not used as the base**. Our implementation follows D-038 and fixes G-01 to G-13 (roll-forward, current model, template fallback, allow-listed prompt fields without `expected`, robust input, fixed opt-out/CTA/next_action, no invented facts, voice skipped, guards). | ANALYSIS (ours) | recommended | As written it fails sample 1 and every LLM call errors | review.md, reference/bot_gemini.py |
| D-040 | 2026-09-24 | Unseen records are handled at three levels. **Level 1** (new values): rule tables in `config/rules.yaml`, each with a default row, and the reason line names the fallback. **Level 2** (missing or odd fields): lenient parsing, stated defaults, unknown fields listed, uncertain consent → don't send. **Level 3** (unknown shape): fields found by name wherever they are nested, consent from any `*_opt_in` key, `confidence: low`; no consent → human review. Compliance applies at every level. | ADD-ON (MFY) | accepted | Anticipates the hold-out "gotchas" without rewriting code live; a live change is one config row | outreach/normalize.py, config/rules.yaml, tests/edge_cases.jsonl |
| D-041 | 2026-09-24 | The project is managed with **uv** (`pyproject.toml`, `uv.lock`); run with `uv run bot.py …`, test with `uv run pytest`. | ADD-ON (MFY) | accepted | Mark's request; reproducible environment | pyproject.toml |
| D-042 | 2026-09-24 | **Template mode is the default** (exact on both samples, ~1 ms per record, deterministic). `--llm` (Claude Haiku 4.5) is optional: it writes only the subject and the core sentence from allow-listed facts, with the samples as few-shot examples; strict tool schema is off (it added ~14 s to the first call); temperature 0 is sent via `extra_body` (SDK 1.x dropped the kwarg); answers are cached on disk; any guard failure falls back to the template. Measured p95: template ~2 ms, LLM ~1.6 s on 16 records. | ANALYSIS (ours) | accepted | Keeps the graded run safe and instant; the LLM mode answers "learns from input data" | outreach/llm.py, bot.py |
| D-043 | 2026-09-24 | **Garbage-proof ingestion.** Bytes: UTF-8/BOM/UTF-16/cp1252/invalid bytes. Text: code fences, comments, prose and numbering ignored (and noted). Records: smart quotes, trailing commas, NBSP, Python-style dicts (`ast.literal_eval`, literals only), double-encoded JSON, arrays per line, `{"records": [...]}` wrappers, key variants (`Task_ID`, `channelPreferences`), JSON-string fields. Line-level repair first, then bracket matching; a truncated or unrecoverable record → no-send with a reason. Every repair is noted on the record. Never raises (random bytes, 100k-deep nesting, empty or missing file tested). | ADD-ON (MFY) | accepted | The hold-out may arrive pasted from email or chat; a reader failure is the most visible way to fail the demo | outreach/reader.py, outreach/normalize.py, tests/garbage_inputs.txt |
| D-044 | 2026-09-24 | **No API cost.** Mark's instruction: incur no cost at all. `--llm` makes no paid call unless `BOT_ALLOW_API_COST=1` is set; otherwise it uses cached answers only and keeps the template, saying so in the reasons. The checks use only a deliberately bad key (rejected, never billed). The default template mode never calls the API. | ORIGINAL (Mark) | accepted | Cost control; the graded path never needs the API | outreach/llm.py, scripts/run_checks.py |
| D-045 | 2026-09-24 | **Fail loudly on cost.** With `--llm`, a free pre-pass finds the records that would need a new (uncached) model call, and estimates tokens locally (calibrated to `count_tokens`: ~1,650 per call) and dollars (list prices per model). Without `BOT_ALLOW_API_COST=1` the run **stops before processing** (exit 3) with a banner for reviewers: calls, tokens, cost avoided, per-call cost, and the free alternative. With permission it prints the cost and proceeds. All cached → proceeds at $0. | ORIGINAL (Mark) | accepted | Cost must be visible to reviewers and interviewers, never silent | bot.py, outreach/llm.py, outreach/pipeline.py |
| D-046 | 2026-09-24 | **Spending limit for demos.** `--budget USD` (or `BOT_LLM_BUDGET_USD`): if the estimated cost of this run is at most the budget, proceed with a single `[cost]` line; otherwise stop loudly (exit 3) and show the overage. `BOT_ALLOW_API_COST=1` remains the explicit "any amount". Cached re-runs are $0 and show no banner. | ORIGINAL (Mark) | accepted | Demo without the banner on every run while keeping a hard cap on anticipated cost | bot.py |
| D-047 | 2026-09-24 | **PII in output: minimum necessary.** The output may contain the recipient's **first name** (in the greeting; the samples' expected bodies include it) and the caller's own `task_id`, and nothing else personal. No last name, email, phone, address, DOB, SSN, card number, notes or protected traits, in any field (body, subject, `why`, warnings). A rejected first name is never echoed ("N characters, not shown"). Enforced by: template fields and the LLM allow-list; RUN STATS reports **PII redacted** (items found in the input by field name or pattern, withheld from the output, by category, with counts only, never values), protected-class details withheld, anything leaked, and a pattern scan of every output record; `tests/pii_cases.jsonl` with planted data checked by pytest and run_checks. Found and fixed: the `why` line used to echo a rejected name, which could be an email, phone or SSN. | ADD-ON (MFY) | accepted | `no_pii_leak` is a constraint in the samples; data minimization | outreach/compose.py, outreach/guards.py, bot.py, tests/pii_cases.jsonl |
| D-048 | 2026-09-24 | **Identity boundary.** The bot is not responsible for passing identifying information through a pipeline. Its only join key is the caller's `task_id`, echoed in each response. The sample format carries no opaque person/lead/property IDs and no contact addresses. A downstream system of record resolves who and where at send time, using its own opaque IDs, never SSN, phone or email as keys. Pass-through of `*_id` fields is a possible extension if the hold-out carries IDs; not built. | ORIGINAL (Mark) | accepted | Minimum necessary data; matches the sample output shape | README, plans/pii-categories.md |
| D-049 | 2026-09-24 | **The bot learns its rules from labelled examples.** `learn.py` infers send hours, the day-offset rule, stage offsets, CTA mapping, next action per stage, follow-up days and the horizon threshold (labels from cadence names or task_ids), printing the evidence per rule; `--write` saves `config/learned.yaml`, which overrides the hand-written defaults. `--eval` is leave-one-out from a neutral base (2 samples: 0/2; plus 2 labelled extras: both samples correct). Learned threshold 50 replaces the hand-set 45. No API; never trained on the hold-out. **Same input protections as the bot** (missing file, images/binary, encodings, garbage), plus **label validation**: malformed or poisoned `expected` blocks are rejected, and out-of-window hours or non-identifier CTA/cadence names are not learned or echoed. | ADD-ON (MFY) | accepted | Answers "can this bot learn?" visibly and measurably, at $0 | learn.py, outreach/learn.py, config/learned.yaml |
| D-050 | 2026-09-24 | **Never learn from hold-out data.** `learn.py` refuses (exit 4, nothing learned, `learned.yaml` untouched) any input whose path contains "hold", and points to scoring with `bot.py --compare` instead. No override. | ORIGINAL (Mark) | accepted | Training on the test set would make the hold-out score meaningless | learn.py |
| D-051 | 2026-09-24 | **Exhaustive channel decision table.** `scripts/decision_table.py` runs all 120 consent × preference combinations through the bot and checks each against an independently stated policy (first preferred, supported, consented channel); 120/120, never sends without consent, never voice. No-send reasons made precise (no consent / preferred channel not supported / consented channel not in preferences). **Open SME question:** should consent alone be enough when a consented channel isn't in the preference list (11 rows)? Current choice: respect the preference list. | ANALYSIS (ours) | accepted | Decision tables are the reviewable, exhaustive specification of must-be-right rules | scripts/decision_table.py, plans/decision-table-channel.md |
| D-052 | 2026-09-24 | **brand_style_applied made concrete.** Per-property brand profile (`properties.yaml` `brand`, defaults `rules.yaml` `brand_default`): display name, banned sales phrases, no emoji, no ALL-CAPS shouting, max exclamations, SMS length. A brand guard checks every message; off-brand AI text falls back to the template. Each sent output reports the records' `required_states` (consent_verified, fair_housing_check_passed, brand_style_applied) in `meta`, and RUN STATS shows the pass counts. | ANALYSIS (ours) | accepted | The samples require the state but never define it (review gap S-13) | outreach/guards.py, outreach/pipeline.py, config/ |
| D-053 | 2026-09-24 | **Rules validator.** `outreach/validate.py` checks `rules.yaml` + `learned.yaml` and `properties.yaml` on every load: types and ranges, send hours inside a legal window that may be narrowed but never widened (TCPA 8:00-21:00), STOP present, no personal/protected fields in the prompt allow-list, CTA names and purposes, time zones, https links, brand settings. The bot and `learn.py` refuse to run on invalid rules (exit 6). `scripts/validate_rules.py` for use after any rule change. Rule changes may be proposed by a person or by AI from plain English; the validator, tests, decision table and a `--pp` diff are the gate, and a human approves. | ADD-ON (MFY) | accepted | Safety comes from the gate, not from who edits the rules | outreach/validate.py, scripts/validate_rules.py |
| D-054 | 2026-09-24 | **`--answer-only` for the hold-out hand-over.** Exports exactly the samples' `expected` shape (`task_id`, `next_message`, `next_action`), one line per record, so an automated grader or a copy-paste gets the answer only; the reasons and RUN STATS stay on screen. A test checks the answer-only output equals the samples' `expected` blocks. | ADD-ON (MFY) | accepted | The hand-over should match their format exactly | bot.py |
| D-055 | 2026-09-24 | **Voice is supported.** The samples carry `voice_opt_in` but never show a voice answer, so the shape is inferred from SMS: `channel: "voice"`, `subject: null`, a call script (the brand's `voice_intro`, the offer, keypad options in `cta.options`, a spoken opt-out: "press 9 or say stop"), sent at 10:00 local (configurable). Brand check adds `max_voice_words` (75, about 30 s) and no symbols or links read aloud. The decision table now covers voice (120/120; 30 voice sends). | ANALYSIS (ours) | accepted | A hold-out with voice consent would otherwise be a guaranteed miss; the inference is stated as an assumption | outreach/compose.py, config/, scripts/decision_table.py |
| D-056 | 2026-09-24 | **Brand validation made visible.** `scripts/validate_rules.py --brand` validates rules, properties and branding, then renders a tour message per property on SMS, email and voice and brand-checks each. It's the first step of the run-checks skill and a check in `run_checks.py`. The design overview documents the configuration files, who changes them, the override order (rules.yaml → learned.yaml → property brand), and the validate command. | ORIGINAL (Mark) | accepted | Branding needs its own visible validation, like the rules | scripts/validate_rules.py, .claude/skills/run-checks/SKILL.md |
| D-057 | 2026-09-24 | **Unknown properties read like the samples.** With no facts file, the display name is derived by dropping a trailing word from `display_name_suffixes` in `rules.yaml` ("Cedar Point Apartments" → "Cedar Point"; never reduced to "The"), and the default brand profile applies. No tour days, amenities or links are claimed. | ANALYSIS (ours) | accepted | A hold-out may use properties we have no file for; the samples' style uses the short name | outreach/compose.py, config/rules.yaml |
| D-058 | 2026-09-24 | **Configuration gaps are reported, not fatal.** A property with no facts file is flagged per record (`meta.warnings` text, a machine-readable `meta.gaps` entry `property_facts_missing`, and confidence lowered to medium) and per run (a RUN STATS "Config gaps" line naming each property and count). The exit code is unchanged, since the record was handled safely. `--answer-only` omits it to keep their shape; the full output keeps it. | ORIGINAL (Mark) | accepted | Downstream systems and operators need to know a message rests on a fallback | outreach/compose.py, outreach/pipeline.py, bot.py |
| D-059 | 2026-09-24 | **Spanish compliance parity.** Spanish STOP keywords (ALTO, PARAR, PARE, BAJA, DAR DE BAJA, CANCELAR, DETENER, NO MÁS, YA NO) opt out before any model call; Spanish protected-class terms (niño, familia, religión, iglesia, discapacidad, raza, inmigra-, nacionalidad, …) are guarded; Spanish banned sales phrases are in the brand defaults. All three lists live in `rules.yaml` and are validated. Known trade-off: a keyword like ALTO ("tall/high") can opt out a reply that didn't mean it, which errs on the safe side for TCPA. | ORIGINAL (Mark) | accepted | Compliance must hold in the recipient's language, not only in English (review 1 flagged the English-only guards) | config/rules.yaml, tests |
| D-060 | 2026-09-24 | **Language is configuration.** All wording moved from code to `config/templates/<lang>.yaml` (en, es, and fr added as a file only): greetings, CTA lines, subjects, opt-outs per channel, call scripts, days, months, move timing, plus each language's STOP keywords, protected terms and banned phrases (merged into the rules on load). A template validator requires every key, valid placeholders, an opt-out on every channel and STOP in the SMS opt-out. Properties declare `languages` and `default_language`; choice order is recipient language if offered, then property default, then `default_language` in rules.yaml. The refactor was checked byte-for-byte: all six test files give identical output. | ORIGINAL (Mark) | accepted | Adding a language shouldn't need a code change; a property should control which languages it communicates in | config/templates/, outreach/compose.py, outreach/validate.py |
| D-061 | 2026-09-24 | **Names in any script.** The first-name check accepts letters plus combining marks from any script (Devanagari vowel signs, Arabic diacritics) instead of a regex that rejected Hindi names like प्रिया (they became "there"). Injection text, emails, digits and over-long names are still rejected. For Arabic or Hindi as *message* languages, the template mechanism works as-is, but: SMS in these scripts is billed as UCS-2 (70 characters per segment, not 160), Arabic is right-to-left with embedded left-to-right tokens (STOP, links, numbers), carriers still require the English STOP keyword alongside the local one, and word lists need native-speaker review. Not built today. | ANALYSIS (ours) | accepted | Found by testing; names are the one personalization every message uses | outreach/compose.py |
| D-062 | 2026-09-24 | **Arabic and Hindi as message languages; `--fill-expected`.** `config/templates/{ar,hi}.yaml` add the two languages as files (flagged NEEDS NATIVE REVIEW). A template can set `direction: rtl`: left-to-right runs (links, STOP, digits, Latin names) are wrapped in Unicode isolates (U+2066/U+2069) so they display in order, and the opt-out guard checks the rendered form. `sms_max_chars` (210 = 3 UCS-2 segments) caps SMS, isolates not counted. English STOP stays alongside the local stop words. Found by the new test: the opt-out check used `\b`, which treats Hindi vowel signs as non-word characters, so "बंद करें" never matched; replaced with a boundary check that counts combining marks as letters. `bot.py --fill-expected` returns their records unchanged with our answer in `expected` (theirs kept as `expected_original`); exclusive with `--answer-only`. | ADD-ON (MFY) | accepted | Follows up D-061; a hold-out could ask for their own file back, filled in | config/templates/, outreach/compose.py, outreach/decide.py, outreach/guards.py, bot.py |


---

# Part 6 — Work plan (GitHub issues)

| # | Title | Labels | State |
|---|---|---|---|
| [#1](https://github.com/markfyoung0711/rp/issues/1) | a) Intake plan: collect assignment inputs | documentation, core | closed |
| [#2](https://github.com/markfyoung0711/rp/issues/2) | b) Understand plan: decisions, fields, implied rules | documentation, core | closed |
| [#3](https://github.com/markfyoung0711/rp/issues/3) | c) Prior-art search + competitive intel: RealPage/peers — legal risk, practices to avoid, renter/customer pain points | documentation, deferred, non-core | open |
| [#4](https://github.com/markfyoung0711/rp/issues/4) | d) Define detailed spec (schemas, rules, scoring) | documentation, core | closed |
| [#5](https://github.com/markfyoung0711/rp/issues/5) | e) Imagine adjacent agents; add-on tests tracked vs original requirements | enhancement, non-core | open |
| [#6](https://github.com/markfyoung0711/rp/issues/6) | f) Design session with engineer: alternatives to co-implement and compare | question, non-core | open |
| [#7](https://github.com/markfyoung0711/rp/issues/7) | g) UX design: renter, customer support, and customer (owner) views — cooperating and visible simultaneously for demo | enhancement, deferred, non-core | open |
| [#8](https://github.com/markfyoung0711/rp/issues/8) | h) Demo data: seed sample actors + create new actors live during the demo | enhancement, deferred, non-core | open |
| [#9](https://github.com/markfyoung0711/rp/issues/9) | i) FIRST: independent critical review of the spec + prior-art research | documentation, priority: first, core | closed |
| [#10](https://github.com/markfyoung0711/rp/issues/10) | j) External review sentiment: pull Yelp/Google/other review-site data per property via API | enhancement, deferred, non-core | open |
| [#11](https://github.com/markfyoung0711/rp/issues/11) | k) Core bot v1: stateless batch decision CLI (D-038) | enhancement, core | closed |
| [#12](https://github.com/markfyoung0711/rp/issues/12) | l) Core hardening v0.2: ingestion, PII, cost guard, stats, checks | enhancement, core | closed |

**Status:** planning and reviews done ([#1](https://github.com/markfyoung0711/rp/issues/1), [#2](https://github.com/markfyoung0711/rp/issues/2), [#4](https://github.com/markfyoung0711/rp/issues/4), [#9](https://github.com/markfyoung0711/rp/issues/9)); the core bot shipped ([#11](https://github.com/markfyoung0711/rp/issues/11)); [#5](https://github.com/markfyoung0711/rp/issues/5) and [#6](https://github.com/markfyoung0711/rp/issues/6) in progress; [#3](https://github.com/markfyoung0711/rp/issues/3), [#7](https://github.com/markfyoung0711/rp/issues/7), [#8](https://github.com/markfyoung0711/rp/issues/8), [#10](https://github.com/markfyoung0711/rp/issues/10) deferred (designed, not built).


## [#1](https://github.com/markfyoung0711/rp/issues/1) a) Intake plan: collect assignment inputs

Collect every input the assignment gives us into one place so later steps start from the same material.

**Scope**
- Problem statement → `plans/spec.md` (done)
- Sample data → `plans/sample.jsonl` (2 cases: `prospect_welcome_day0`, `prospect_long_horizon_day3`)
- Record anything else from the interviewer: delivery deadline, format, how the output is scored, which models or APIs are allowed
- List the open questions for the interviewer

**Done when**
- `plans/` holds every input from the assignment
- `plans/open-questions.md` lists the unknowns, and which of them block work

## [#2](https://github.com/markfyoung0711/rp/issues/2) b) Understand plan: decisions, fields, implied rules

Work out what the assignment actually asks for, and write down what is only implied.

**Scope**
- Break "learns what to do only from input data" into four decisions: *whether* to send, *which channel*, *when*, and *what to say*
- For each field in `sample.jsonl`, say whether it is an input, a constraint, or an expected output, and how it could be scored
- Say what "semantically matches" means for each output field:
  - exact match: `channel`, `cta.type`
  - tolerance: `send_at`
  - semantic similarity or LLM judge: `body`, `subject`
- The rules the two samples imply:
  - channel = first preferred channel the recipient has opted in to
  - send time = a morning hour in the recipient's local time
  - opt-out wording that fits the channel
- Note the gaps: neither sample shows a "do not send" case, and there is no example of the `voice` channel

**Done when**
- `plans/understanding.md` has the decision breakdown, a field-by-field table, and a list of assumptions

Depends on: [#1](https://github.com/markfyoung0711/rp/issues/1)

## [#3](https://github.com/markfyoung0711/rp/issues/3) c) Prior-art search + competitive intel: RealPage/peers — legal risk, practices to avoid, renter/customer pain points

Survey existing products and published approaches for automated outreach and support in rental housing. This covers three relationships:

- **Renter/prospect ↔ property manager:** leasing outreach, tour booking, maintenance requests, renewals, complaints
- **Customer (property owner or operator) ↔ vendor support:** RealPage-style platform support, billing, configuration
- **Owner ↔ manager ↔ renter:** escalations and reporting

**Look at**
- RealPage products (e.g. Lead2Lease / AI leasing assistant, resident portals), EliseAI, Knock, Entrata, Yardi (RENTCafé), AppFolio (Lisa AI)
- Compliance that limits outreach:
  - Fair Housing Act (steering, discriminatory language)
  - TCPA (SMS/voice consent, quiet hours)
  - CAN-SPAM (email opt-out)
  - state quiet-hour rules
- How these products decide the channel, the cadence, and when to hand off to a human

**UX prior art**
Study how existing products *look and flow* for each of our three roles and the demo, so the design in [#7](https://github.com/markfyoung0711/rp/issues/7) builds on proven patterns rather than inventing them. Collect screenshots, links and notes.
- **Renter side:**
  - SMS/email/voice conversational flows from leasing AI assistants (EliseAI, RealPage Lead2Lease / AI leasing, Knock, AppFolio Lisa): how they introduce the bot, show reply options ("Reply 1/2"), hand off to a human, and handle STOP
  - resident apps and portals (RealPage ActiveBuilding / Loft, Entrata ResidentPortal, Yardi RENTCafé, AppFolio): maintenance requests with photos, payments and disputes, preferences
  - their app-store ratings and reviews, which show UX pain points
- **Support side:**
  - agent consoles: Zendesk, Intercom, Front, Salesforce Service Cloud, Gorgias
  - patterns to study: unified inbox across channels, conversation timeline, AI suggestions with approve/edit, take-over/hand-back, sentiment and priority indicators, macros, SLA timers
- **Owner side:**
  - property-management dashboards (RealPage, Yardi, Entrata, AppFolio), and CX analytics tools (Medallia, Qualtrics) for sentiment trends and drill-down
- **Onboarding and login:**
  - multi-tenant B2B SaaS onboarding wizards (organization → properties → staff → policy)
  - passwordless and code-based flows (Slack, Notion, Stripe)
  - account claim from an existing lead
- **Demo and AI transparency:**
  - multi-pane "simulator" demos (Twilio / Voiceflow / Botpress simulators, Intercom Fin preview)
  - explaining AI decisions, i.e. showing the decision trace (LangSmith / Langfuse trace views)
  - accessibility (WCAG 2.2) and mobile-first renter flows

**UX output:** a section in `plans/prior-art.md` that has:
- a pattern library: pattern → where it's seen → adopt / adapt / avoid
- UX pain points from reviews, added to the pain point → solution table

Both feed [#7](https://github.com/markfyoung0711/rp/issues/7).

> ## ⚠️ Special note — competitive intel and pain points (Mark F. Young)
> Beyond product features, this research is after **competitive intelligence**. Every leading item below is a lead to verify with sources, not a settled fact.
>
> **1. Legal problems facing RealPage and its peers**
> - Antitrust and price-fixing:
>   - the DOJ and state attorneys-general cases over algorithmic rent pricing (YieldStar / AI Revenue Management)
>   - the renter class actions (*In re RealPage*)
>   - settlements, and landlords named as co-defendants
>   - city and state bans on algorithmic rent-setting software
> - Tenant screening: FCRA accuracy suits, and disparate-impact / fair-housing claims against AI screening (e.g. the SafeRent settlement)
> - Consumer protection: junk fees (FTC and state enforcement), TCPA texting and calling suits, CAN-SPAM
> - Data security and privacy: breaches, and CCPA and state privacy laws
>
> **2. Risky business practices we must avoid by design**
> - Never pool or use nonpublic competitor pricing or occupancy data. The bot does not set or recommend rent.
> - No sensitive attributes, or stand-ins for them, in targeting, screening, tone or sentiment use (Fair Housing)
> - No dark patterns: hidden fees, auto-renewal traps, "urgency" pressure, burying the opt-out
> - Consent-first messaging (TCPA/CAN-SPAM) and quiet hours
> - AI transparency: disclose that the renter is talking to a bot, and always offer a way to reach a human
> - Log every decision so it can be audited and explained
>
> **3. Renter and customer experience and satisfaction**
> - Renter pain points (sources: reviews, Reddit, BBB/CFPB complaints, ratings of resident portals):
>   - slow or unanswered maintenance
>   - unresponsive management; not being able to reach a human
>   - fee surprises
>   - clunky portals
>   - repeating the same information to different people
>   - renewal-increase shock
> - Customer (owner/operator) pain points:
>   - slow lead response
>   - staff turnover and inconsistent follow-up
>   - leads that slip through
>   - no visibility into resident sentiment
>   - compliance exposure
>   - fragmented tools
>
> **Output:** in `plans/prior-art.md`, a **pain point → how we solve it** table. For example:
> - "can't reach a human" → escalation driven by sentiment (UC-14, UC-21)
> - "repeating myself" → one timeline across channels (D-009)
> - "fee surprises" → transparent billing disputes (UC-13)
> - "compliance exposure" → guards and an audit trail (UC-40 to UC-43)
>
> Feed new pain points back as use cases, add-on tests ([#5](https://github.com/markfyoung0711/rp/issues/5)) and decisions.

**Done when**
- `plans/prior-art.md`: short notes on each product with links, plus the rules and patterns we should copy or test against
- the special-note section is complete: sourced legal and risk findings, practices to avoid, and the pain-point → solution table
- the UX prior-art section and pattern library are complete, and [#7](https://github.com/markfyoung0711/rp/issues/7) is updated from them

## [#4](https://github.com/markfyoung0711/rp/issues/4) d) Define detailed spec (schemas, rules, scoring)

Turn the understanding and prior-art notes into a detailed spec that the implementation and the evals both follow.

**Scope**
- Input schema and output schema (JSON Schema or Pydantic), based on `sample.jsonl`
- Decision rules, written so they can be tested:
  - consent gating
  - channel choice
  - send-time calculation (timezone, quiet hours)
  - suppression ("do not send")
- Content rules:
  - personalization fields to use
  - brand style
  - opt-out wording per channel
  - fair-housing and PII guards
  - CTA mapping (`primary_cta` → `cta.type` and its options or link)
- `next_action` choice (start a cadence vs. follow up in N days)
- Scoring for each field and the pass thresholds (use the `thresholds` block from the samples)

**Done when**
- `plans/spec.md` is extended with the sections above
- every rule has an ID (`R-xx`) that tests can refer to

Depends on: [#2](https://github.com/markfyoung0711/rp/issues/2), [#3](https://github.com/markfyoung0711/rp/issues/3)

## [#5](https://github.com/markfyoung0711/rp/issues/5) e) Imagine adjacent agents; add-on tests tracked vs original requirements

Imagine the wider system this bot would sit in: real-estate support, intake, CRM and complaint handling. Turn the other agents it would need into add-on test cases.

**Candidate agents**
- **Intake/router:** classify what an inbound renter or owner message is about
- **Maintenance work-order agent:** create and triage requests, schedule vendors
- **Complaint/escalation agent:** sentiment, repeat contacts, hand-off to a human
- **Billing/ledger dispute agent:** including uploaded bills with marked-up items
- **Renewal/retention agent**
- **Owner-reporting agent:** occupancy and delinquency summaries for the property owner
- **Compliance guard:** fair housing, TCPA/CAN-SPAM, PII, prompt injection
- **Scheduling agent:** tours, move-in, inspections
- **Language/translation agent**

**Test tracking**
- `plans/tests.md` keeps two lists:
  - **Original (REQ-xx):** taken from `sample.jsonl` and the problem statement. These are the graded requirements.
  - **Add-on (ADD-xx):** our extensions, each tagged with its agent and the spec rules it covers
- Add-on cases go in `tests/addon/*.jsonl`, using the same record shape as `sample.jsonl`
- Include negative cases the samples lack:
  - no consent
  - quiet hours
  - opted out
  - a message that would break fair-housing rules
  - prompt injection in profile fields

**Done when**
- the add-on JSONL cases exist
- every case (original and add-on) appears in `plans/tests.md` with its status

Depends on: [#4](https://github.com/markfyoung0711/rp/issues/4)

## [#6](https://github.com/markfyoung0711/rp/issues/6) f) Design session with engineer: alternatives to co-implement and compare

Hold a design session with the human engineer. Agree on 2–3 alternative implementations, then build them side by side against the same eval harness so they can be compared.

**Candidate alternatives to discuss**
1. **Rules + templates:** deterministic channel and timing logic; content from templates filled with profile fields. Cheap, predictable, weak at "semantic" personalization.
2. **Rules + LLM for content:** deterministic gating, channel and timing; LLM writes the subject and body under guardrails, and an LLM judge scores them.
3. **Full LLM agent:** a tool-using agent decides all four outputs from the record plus few-shot examples; guards run as post-checks.
4. *(optional)* **Learned from data:** infer the rules from the JSONL (e.g. a decision tree for channel and timing, few-shot retrieval for content). This is the most literal reading of "learns only from input data".

**Compare on**
- pass rate on original and add-on tests
- safety violations
- latency (p95) and cost per record
- how easy each is to explain and audit

**Done when**
- the chosen alternatives and who builds each are recorded in `plans/alternatives.md`
- one shared eval harness runs all of them and prints a side-by-side table

Depends on: [#4](https://github.com/markfyoung0711/rp/issues/4), [#5](https://github.com/markfyoung0711/rp/issues/5)

## [#7](https://github.com/markfyoung0711/rp/issues/7) g) UX design: renter, customer support, and customer (owner) views — cooperating and visible simultaneously for demo

Design a UI for the three roles. All three must work together and be on screen at the same time, so a demo can show one interaction flowing between them live.

**Roles and views**
- **Renter/prospect:** receives the bot's messages (SMS-style thread plus email view), replies, books tours, raises maintenance requests or complaints, uploads files
- **Customer support agent:** a queue of conversations with the bot's decisions (send or suppress, channel, timing, reasons), guard results, and hand-off and escalation controls. Can edit a message before it goes out, or take over the conversation.
- **Customer (property owner/operator):** a portfolio view with outreach activity, escalations, complaint and maintenance summaries, and approval of policies such as cadences, brand style and quiet hours

**Simultaneous demo**
- A split-screen layout with all three panes side by side, or three browser windows attached to the same session
- Shared real-time state (WebSocket or SSE), so an action in one pane shows up in the others straight away
- A scenario player that replays `sample.jsonl` and the add-on cases ([#5](https://github.com/markfyoung0711/rp/issues/5)) step by step, including edge cases such as no consent, quiet hours and escalation
- A timeline or trace strip showing the agent's decision path (router → guards → channel/time → content) for each event

**Other requirements**
- Dark and light themes, a language picker, and layouts that work on a phone for the renter pane
- Each pane sees only what its role is allowed to see. This matters for the demo: no leaking the owner's portfolio data to the renter, and no renter PII shown to the owner beyond what is needed.

**Done when**
- wireframes and mockups for all three panes, plus the layout that shows them together, are in `plans/ux.md`
- a demo script walks through at least 3 scenarios across all three roles

Relates to: [#4](https://github.com/markfyoung0711/rp/issues/4) (spec), [#5](https://github.com/markfyoung0711/rp/issues/5) (add-on agents), [#6](https://github.com/markfyoung0711/rp/issues/6) (alternatives: the UI should let you switch the backend implementation to compare)


Informed by: [#3](https://github.com/markfyoung0711/rp/issues/3) (UX prior art and pattern library), [#9](https://github.com/markfyoung0711/rp/issues/9) (independent review)

## [#8](https://github.com/markfyoung0711/rp/issues/8) h) Demo data: seed sample actors + create new actors live during the demo

The demo needs a quick way to fill the system with **sample actors**, and a way to **add new ones live** during the demo. Adding one on stage shows onboarding working, instead of relying only on pre-loaded data.

**1. Seed set (repeatable, synthetic)**
- A seed script plus fixture files (`seed/*.yaml` or JSON) that create a known baseline in one command (`make seed` / `POST /demo/seed`):
  - **Customers:** 1–2 organizations (e.g. Oak Ridge Apartments in Richardson, TX), each with properties, units, brand and policy (quiet hours, cadences such as `prospect_welcome_short_horizon`), and staff users
  - **Support:** 1–2 agents scoped to those organizations
  - **Renters / prospects:** people with contact points, per-channel consents, channel preferences, timezones, languages, lifecycle stages and profiles. This includes the people in `plans/sample.jsonl` (e.g. Taylor) and edge-case people from the add-on tests ([#5](https://github.com/markfyoung0711/rp/issues/5)): no consent, SMS only, opted out, Spanish speaker, angry repeat caller, injection attempt in a profile field
  - **Demo login users** for each role (D-015)
  - Optional **history**: past interactions, events and sentiment, so dashboards and the support queue are not empty on first load
- Idempotent: re-running it resets to the same baseline, with stable IDs where it helps the demo script
- Data is clearly synthetic: `*.example` domains, sandbox phone numbers (e.g. 555), and no real PII (D-016)

**2. Adding new actors during the demo**
- New actors are created through the **real onboarding flows and APIs** (UC-30, the renter account claim, lead intake), not a back door. The demo exercises the same code a production user would.
  - Owner onboarding wizard: new organization → property → staff → policy
  - Support/admin invites a new agent
  - New lead arrives by web form, "inbound SMS" from the phone pane, or a pasted/uploaded JSONL record, which becomes a Person, contact points, consents and a Relationship
- A **"generate a realistic person" helper** (Faker-style, optionally LLM-assisted) that fills the form so the presenter isn't typing live, but still submits through the normal API
- New actors show up straight away in all three panes (SSE) and can be used in the scenario player

**3. Keeping seeded and new apart**
- Each record carries an `origin` tag (`seed`, `demo_created`, `jsonl_import`), so a reset can either:
  - restore the baseline only, or
  - clear everything created during the demo
- The scenario player can also pick seeded actors, or ones made during the demo

**Done when**
- one command seeds the baseline, and re-running it is safe
- a presenter can create a new owner, agent and renter from the UI in under a minute each, and use them in a scenario
- a reset restores the baseline without restarting the stack

Relates to: [#5](https://github.com/markfyoung0711/rp/issues/5) (add-on test people), [#7](https://github.com/markfyoung0711/rp/issues/7) (UX/demo), D-008 (identity and IDs), D-015 (demo auth), D-016 (synthetic data only)

## [#9](https://github.com/markfyoung0711/rp/issues/9) i) FIRST: independent critical review of the spec + prior-art research

**Priority: one of the first issues to tackle.** Run it early, before the detailed spec ([#4](https://github.com/markfyoung0711/rp/issues/4)) is locked and before implementation starts.

An **independent** critical review of the spec and plans, done alongside prior-art research, to catch wrong assumptions, gaps and risks while they are still cheap to fix.

**Independent means** the reviewer did not write the plans and starts without our framing. Options:
- a fresh agent session with no conversation history, given only the files below and asked to find problems
- a human engineer
- ideally both, compared

The reviewer gets the **original assignment first** (`plans/spec.md` § Problem Statement and `plans/sample.jsonl`), and forms their own reading of it *before* seeing our add-ons.

**Review targets**
- `plans/spec.md`: the original problem, and our analysis of the samples (D-002)
- `plans/use-cases.md`, `plans/actors.md`, `plans/design.md`, `plans/decisions.md`

**Questions the review must answer**
1. **Reading the assignment:** what does "learns what to do only from input data" require? Does our mostly-rules design (D-014) respect or violate it? What does "semantically matches" demand, field by field?
2. **Inferences from 2 samples:** which rules in D-002 are overfit? What counter-examples would break them (e.g. the channel rule, the send-time rule)?
3. **Scope:** is the add-on scope (D-003 to D-017) at risk of crowding out the graded core? What is the minimum that must work well before any add-on?
4. **Gaps:**
   - missing use cases, actors or data elements
   - "do not send" cases
   - the `voice` channel
   - multiple languages
   - the `thresholds` block (personalization score, reply-classification F1): how are these measured?
5. **Risk:**
   - security and PII (D-016)
   - demo auth (D-015)
   - database choice (D-013)
   - legal and compliance exposure (D-017)
6. **Testability:** can every rule and use case be turned into a REQ or ADD test ([#5](https://github.com/markfyoung0711/rp/issues/5))?

**Prior-art research (runs alongside, feeds into [#3](https://github.com/markfyoung0711/rp/issues/3))**
- How existing leasing and resident-communication bots decide whether, when, where and what to send, compared with our design
- Competitive intel and pain points, per the special note in [#3](https://github.com/markfyoung0711/rp/issues/3)
- **UX prior art** (per [#3](https://github.com/markfyoung0711/rp/issues/3)): renter conversation flows and portals, support consoles, owner dashboards, onboarding and login, demo simulators and decision-trace views. Does our UX ([#7](https://github.com/markfyoung0711/rp/issues/7), `design.md` §6) match proven patterns, or miss standard ones?
- Where prior art shows our design is wrong, redundant, or missing something standard

**Output**
- `plans/review.md`: findings ranked by severity (blocker / major / minor), each with a proposed change
- For each accepted finding: a new or updated entry in `plans/decisions.md` (a new D-xxx, or an existing one marked superseded or rejected), plus edits to the affected plan files or issues
- A short note of findings we rejected, and why

**Done when**
- the review is complete, and every finding is accepted (with a decision recorded) or rejected (with a reason)
- [#3](https://github.com/markfyoung0711/rp/issues/3) has its first sourced findings
- [#4](https://github.com/markfyoung0711/rp/issues/4) can start from a reviewed baseline

Relates to: [#2](https://github.com/markfyoung0711/rp/issues/2), [#3](https://github.com/markfyoung0711/rp/issues/3), [#4](https://github.com/markfyoung0711/rp/issues/4), [#5](https://github.com/markfyoung0711/rp/issues/5), [#6](https://github.com/markfyoung0711/rp/issues/6)


## [#10](https://github.com/markfyoung0711/rp/issues/10) j) External review sentiment: pull Yelp/Google/other review-site data per property via API

Add an API feature that fetches **public review-site data** (Yelp, Google, and others) for each property and scores its sentiment. Owners then see their public reputation next to internal sentiment (D-012). This is UC-50 in `plans/design.md`, recorded as D-018.

**Sources, all through licensed APIs**
- **Yelp Fusion API:** business lookup plus review excerpts (the API returns a limited number)
- **Google Places API / Google Business Profile API:** the Business Profile API gives owners access to their *own* listings' reviews, and allows replies
- **Apartment-specific sites** (ApartmentRatings, Apartments.com, Zillow and others): only where there is a licensed API or partner feed, otherwise through a **review aggregator** (e.g. Birdeye, Reputation.com, Yext)
- **No scraping:** it breaks site terms and adds legal risk (D-017)

**Pipeline**
- `ReviewSource` for each property and provider: external business ID, credential reference, sync schedule, and a **terms profile** (what may be stored, for how long, and the attribution rules)
- A scheduled pull through a provider adapter:
  - normalize into `ExternalReview`, stored only as the terms allow, and purged at `expires_at`
  - score with the same sentiment pipeline as inbound messages
  - extract themes (maintenance, noise, staff, fees, parking, pests, safety, …)
  - build `SentimentRollup` records with scope = property and source = external
- The owner dashboard shows external and internal sentiment side by side, never blended, plus theme trends and "what the public says vs. what our renters tell us"
- Alerts: a new 1–2★ review, or a theme spiking, opens a task for the owner or support
- Reply drafting: the LLM drafts a response and **a human approves it**; nothing is ever posted automatically

**APIs**
- `POST/PATCH /properties/{id}/review-sources`
- `POST /review-sources/{id}/sync` (manual pull)
- `GET /reviews?property=&provider=&sentiment=`
- `GET /reviews/themes?property=`
- `POST /reviews/{id}/draft-reply`

**Guardrails**
- Never match a public reviewer to a renter record: no de-anonymizing, no retaliation risk. Review sentiment never changes how a renter is treated.
- FTC rule on fake reviews: never generate fake reviews, offer incentives for positive ones, or suppress negative ones
- Obey each provider's storage, caching and attribution requirements, recorded per adapter
- API keys go in Secret Manager

**Demo**
- A `SandboxReviewAdapter` with synthetic reviews for the seeded properties ([#8](https://github.com/markfyoung0711/rp/issues/8)), so no API keys are needed
- Scenario: a Google review complains about slow maintenance → the owner dashboard shows it lining up with the internal drop in maintenance sentiment → a reply is drafted and approved

**Research (feeds [#3](https://github.com/markfyoung0711/rp/issues/3) and [#9](https://github.com/markfyoung0711/rp/issues/9))**
- Check each provider's current API terms, limits, pricing, and what may be stored or displayed
- Compare the cost and coverage of an aggregator with direct integrations
- Look at how competitors show reputation data to owners (a UX prior-art input)

**Done when**
- the sandbox adapter and at least one real provider adapter (behind a feature flag) work end to end
- external review sentiment appears on the owner dashboard next to internal sentiment
- the terms checks and guardrails have ADD tests ([#5](https://github.com/markfyoung0711/rp/issues/5))

Relates to: [#3](https://github.com/markfyoung0711/rp/issues/3), [#5](https://github.com/markfyoung0711/rp/issues/5), [#7](https://github.com/markfyoung0711/rp/issues/7), [#8](https://github.com/markfyoung0711/rp/issues/8), [#9](https://github.com/markfyoung0711/rp/issues/9), D-012, D-017, D-018

## [#11](https://github.com/markfyoung0711/rp/issues/11) k) Core bot v1: stateless batch decision CLI (D-038)

The core decision bot for the graded assignment and the hold-out export, built to the merged spec **D-038**, with unseen-record handling at three levels (**D-040**).

**Delivered (v0.1.0)**
- `bot.py` CLI: `--input` / `--paste`, `--output`, `--compare`, `--llm`, `--now`, `--quiet`
- `outreach/`:
  - `reader`: JSONL, JSON array or pretty-printed input; a bad record is isolated and reported
  - `normalize`: Level 2 and 3 tolerance
  - `decide`: STOP gate, consent/channel, send time with roll-forward, next action
  - `compose`: templates with fixed opt-out and CTA, property facts only
  - `guards`: output checks
  - `llm`: optional Haiku 4.5 wording, with the samples as few-shot examples
- `config/rules.yaml`: all rule tables, each with a default row. `config/properties.yaml`: property facts.
- `tests/edge_cases.jsonl` (16 records across Levels 1–3) and `tests/test_bot.py` (6 tests)

**Verified**
- Both samples match on **every field**, including the exact subject and body, in template mode
- All 16 edge cases run without crashing; a broken line does not stop the batch
- Re-runs give the same output
- p95 latency: template ~2 ms per record; `--llm` ~1.6 s (target 2,000 ms)

**Run:** `uv run bot.py -i plans/sample.jsonl --compare` · `uv run pytest`

Decisions: D-038, D-040, D-041, D-042. Work log: `plans/worklog.md`.

## [#12](https://github.com/markfyoung0711/rp/issues/12) l) Core hardening v0.2: ingestion, PII, cost guard, stats, checks

Hardening of the core bot after v0.1.0, driven by the code-review checklist and live testing. Tagged **v0.2.0**.

**Delivered**
- **Garbage-proof input (D-043):**
  - UTF-8, BOM, UTF-16 and cp1252 files
  - chat-style pastes, code fences, comments
  - smart quotes, trailing commas, Python-style dicts, JSON inside strings, wrappers, key variants
  - images, PDFs and binary input refused clearly (exit 2)
- **Checklist fixes:** byte-identical output, `tzdata`, bounded LLM timeout, wrong-type fields, non-Latin names, duplicate IDs, steering terms
- **PII (D-047):**
  - 20 rental-PII categories plus protected-class details detected
  - 81 planted items withheld, 0 leaked
  - money amounts and account-like numbers blocked from messages
  - no sensitive fields in the model prompt
  - rejected names never echoed
- **Cost (D-044–D-046):** `--llm` stops loudly (exit 3), showing the calls, tokens and dollars avoided; `--budget` sets a spending limit; $0 by default
- **RUN STATS:** decisions, confidence, latency vs input thresholds, safety scan, PII redacted and leaked counts, cost, per-field match rates
- **Tooling and docs:**
  - `scripts/run_checks.py` (29 checks) and the `run-checks` skill
  - `scripts/gen_records.py`; performance on 100 and 100K records (`plans/performance.md`)
  - `--only` filter; `plans/demo-tests.md` (28 demo tests); README; `docs/demo-runbook.html`

**Verified:** both samples match every field; 14 tests; 29/29 checks; a blind 12-record run read by eye (two wording fixes).

---

# Appendix A — Critical reviews

> From `plans/review.md`.

- **Review 1 of 2:** Claude Sonnet 5 (independent session), 2026-09-24, below.
- **Review 2 of 2:** SME review by **Gemini (Google AI Mode)**, 2026-09-24, [at the end](#review-2-of-2--sme-review), followed by our reconciliation of the two reviews.

---

## Review 1 of 2

### SME Review: Context-Aware Messaging Bot for Rental Housing

**Documents reviewed:** `spec.md` (the assignment) and `solution.md` (solution proposal by Mark F. Young, updated 2026-09-24)
**Review date:** 2026-09-24
**Revision:** 2. Section 2 now covers the broader meaning of a hold-out set (live surprises as well as the 12-record batch). Sections 1, 6, and 8 were adjusted to match.
**Lens:** business and systems analysis for residential and multifamily leasing, in a RealPage context
**Purpose:** the independent critical review requested in issue [#9](https://github.com/markfyoung0711/rp/issues/9), before the detailed spec ([#4](https://github.com/markfyoung0711/rp/issues/4)) is locked

---

### 0. How this review was done, and its limits

- **Order of work:** I read the assignment first and formed my own view of its gaps, then read the solution, as [#9](https://github.com/markfyoung0711/rp/issues/9) asks.
- **Sample data:** only the two records printed inside `spec.md` were available. A separate `sample.jsonl` was not provided. I assume it matches.
- **No code was run.** Nothing here was tested against any hidden set.
- **RealPage context:** product observations come from the public OneSite page (marketing content, not technical documentation). Vendor figures on that page are not treated as facts.
- **Legal points** are flagged for verification. This is not legal advice, and several rules in this space have changed recently.
- **Severity scale:** *Blocker* means the delivery is likely to fail or mislead without a fix. *Major* means a significant risk or gap. *Minor* means worth fixing, not urgent.

---

### 1. Executive summary

The solution's layering is sound: deterministic gates, an LLM only for wording, authorization enforced inside tools, and consent re-checked at send time. The problems are in priorities and in fit with the graded core.

1. **The core can't reproduce the samples as specified.** The send-time rule fails on sample 2, and the expected messages contain facts (tour availability, amenities, a URL) that have no source in the input or the data model.
2. **The add-on scope dwarfs the graded scope.** Three graded use cases get roughly one pipeline diagram. Seventeen add-on use cases get schemas, APIs, security, and deployment.
3. **The evaluation is circular.** The two samples are the few-shot examples, the source of the rules, and the test set. A pass would prove nothing about a hidden set.
4. **The platform rebuilds products RealPage already sells** (CRM, leasing agent, resident portal, maintenance, reputation management) with no integration or system-of-record story.
5. **The delivery constraint changes what matters.** A working demo is due today at 12:00 noon CST, and 12 outputs from an unseen hold-out set must be exported at the interview. Accuracy on unseen records and never crashing matter far more than the platform. Expect live "what if" follow-up questions as well (section 2).

---

### 2. What is a "hold-out set", and what it means here

#### Definition
A **hold-out set** is a group of test cases deliberately kept away from whoever builds the system. It is used once, at the end, to measure how well the system handles cases it has never seen. The term comes from machine-learning practice, where part of the data is "held out" so you can't tune the system to it. The point is to tell real generalization from memorized answers.

| Term | Meaning | In this assignment |
|---|---|---|
| Training or development data | What you build and tune against | The two records in `sample.jsonl` |
| Hold-out (test) set | Unseen cases used for the final measurement | The 12 cases provided during the interview |

#### What the delivery note says, and a broader reading
The note says to "be prepared to export or copy-paste the 12 outputs from a hold-out set that is provided during the interview." There are two ways to read this, and you should prepare for both.

1. **The stated reading (primary):** at the interview you receive 12 new input records, probably in the same shape as the samples. You run your system on them and hand over the 12 outputs, by export or copy-paste, live. You cannot see or tune to those records beforehand.
2. **The broader interview practice (likely, but not stated in your note):** interviewers often use a hold-out as a live stress test of a system built from a vague spec. Because the spec was nebulous, they want to see whether your design choices survive real-world variation, or whether you hardcoded a solution to the few examples you were given. In this view they treat your system the way a data scientist treats a model, and they also watch how you react under pressure when something unexpected happens.

The second reading comes from general interview practice, not from anything in your assignment. Treat the 12-record batch as the main event and live follow-up questions as a probable addition.

#### What is still unknown (ask the interviewer)
- Do the 12 records include an `expected` block, so outputs are scored automatically, or only inputs, so a person judges them?
- Do they cover the same persona and stage (prospect, new/open) or others (resident, applicant, renewal)?
- Do they include no-send cases, voice, or non-English records? The samples show none of these, and the assignment says a message might be "not sent."
- What format do they want for the export?
- Will there be live "what if the client wants Y?" changes or questions after the batch?

#### Forms it can take, and how this design responds

| Form | Example in this assignment | What protects you | Related findings |
|---|---|---|---|
| New unseen records | 12 records you have never seen | Rules that generalize, not rules fitted to two samples | F-03, F-15 |
| Corrupt or null input | Missing fields, null consent, unknown time zone, an odd or hostile `first_name`, malformed JSON | Safe fallback: a no-send with a recorded reason, never a crash | F-03, F-09 |
| Domain edge cases | No consent, opted out, voice-only, quiet-hours edge, non-English, resident persona | The decisions table in section 6, settled in advance | F-06, F-07, F-15 |
| Feature pivot | "Add voice," "change quiet hours," "add Spanish," "add a renewal cadence" | Know where each rule lives; a core separate from the platform makes each change local | F-03, F-04 |
| Scale escalation | "Run 100,000 records now" | Records are decided independently, so the work parallelizes. The real limits are the latency budget, model cost and rate limits, and avoiding duplicate sends | F-08, F-14 |
| Assumption challenge | "Why 9:00? Why Thu/Fri? Why that channel?" | State your assumptions before you are asked (below) | F-01, F-02, F-15 |

#### What it exposes about your system
- **Flexibility:** whether the rules are modular or tightly coupled and brittle.
- **Failure behavior:** how gracefully the system handles unexpected input.
- **Your reasoning under pressure:** how you respond to an unmapped case you did not anticipate.
- **Assumption quality:** whether the guesses you made to fill the spec's gaps were logical and defensible.

#### What follows from this
- **Generalization beats fit.** Two samples cannot define the behavior of a system that must handle 12 unseen cases. Rules written only to reproduce the samples are fragile.
- **Robustness is graded implicitly.** A crash, a blank output, or a hallucinated fact on one of 12 cases is very visible.
- **Reproducibility matters.** Running the same record twice should give the same output, or you can't explain the export.
- **Your own testing must simulate a hold-out.** Write extra cases (no consent, voice-only, opted out, different persona, non-English, missing fields, odd names) and treat them as unseen. Do not tune your rules to the two samples alone.

#### Assumptions to state aloud before you are asked
Naming these yourself shows the gaps were seen and handled on purpose.
1. **Send time:** how the date and hour are chosen, and that `now` is an explicit input (F-01).
2. **Property facts:** where amenities, tour slots, and the tour link come from, and what happens when they are missing (F-02).
3. **Cadence horizon:** short vs long is derived from days to move-in, with a threshold you chose (F-15).
4. **No-send output:** the shape you chose, since the assignment defines none (S-4).
5. **AI disclosure:** handled as a policy flag, and why it is off in graded output (F-16).
6. **Consent:** the samples give three booleans, and richer consent semantics are designed but not built (F-06).
7. **Voice:** modeled in the data, deferred in behavior.
8. **Sample-derived rules are hypotheses,** tested against extra cases you wrote, not proven.

#### A short way to describe what you built
Adapt this to what is actually running, and do not claim anything that is not.

> "It is a decision agent for outbound leasing messages. Deterministic rules decide whether to send, which channel, and when. The wording comes from templates, with an optional model-written sentence. The opt-out text and call to action are composed by fixed logic, not generated. The rules were inferred from two samples, so I have marked them as assumptions and tested them against extra cases I wrote myself."

---

### 3. Review of the assignment (`spec.md`)

These are gaps in the assignment itself. The architecture may be silently assuming answers to them.

| # | Gap | Why it matters | Ask |
|---|---|---|---|
| S-1 | **No reference clock.** Nothing says what "now" is. | Send times can't be reproduced without it. | Is there a "current time" for a case? |
| S-2 | **Facts in expected outputs aren't in inputs.** "Tours are available this week," Thu/Fri slots, "24/7 fitness center," and the tour URL. | An agent that "learns only from input data" cannot produce them. | Is a property knowledge base or scheduling tool assumed? |
| S-3 | **Consent is three booleans.** No timestamp, source, scope (marketing vs transactional), or revocation. | Legal exposure (TCPA, state rules) is much richer than the data. | What consent semantics apply? |
| S-4 | **No "do not send" case** appears, though the text allows one. | The output for a suppress case is undefined. | What shape should a no-send output take? |
| S-5 | **Voice is an opt-in field with no example.** | Behavior when voice is preferred or the only consented channel is undefined. | Is voice in scope? |
| S-6 | **Thresholds have no measurable inputs.** `personalization_score_min` and `reply_classification_f1_min` have no definition, and there are no replies to classify. | Can't be scored or engineered against. | How are these measured? |
| S-7 | **`required_states` have no place in the output.** `consent_verified`, `fair_housing_check_passed`, `brand_style_applied`. | Unclear if they are checked, logged, or output. | Where should they appear? |
| S-8 | **"And why" is promised but not in `expected`.** | Rationale format unknown. | Is a reason field expected? |
| S-9 | **Inconsistent labels.** `primary_cta: book_tour` vs `cta.type: schedule_tour`; `no_sensitive_discrimination` appears only in sample 1. | The mapping and constraint inheritance are ambiguous. | Confirm the mapping. |
| S-10 | **Undefined vocabulary.** `next_action.type`, `lifecycle_stage` values, and the meaning of `prospect_welcome_short_horizon`. | The cadence naming hides an unstated rule (see F-15). | Provide the full value lists. |
| S-11 | **Latency scope unclear.** 2,000 ms p95 per record or per batch, and whether an LLM call is inside it. | Drives the whole architecture. | Clarify. |
| S-12 | **Two-way flow is implied, not specified.** "Reply 1 for Thu, 2 for Fri" needs inbound handling. | Scope of reply handling is unclear. | Is inbound in scope? |
| S-13 | **Unstated inputs.** No brand style guide, no property facts, no contact history or frequency caps. | Required to satisfy `brand_style_applied` and avoid double-messaging. | Where do they come from? |

---

### 4. Review of the solution (`solution.md`)

#### 4.1 Blockers

**F-01. The send-time rule cannot reproduce sample 2.**
- *Evidence:* Sample 2's `last_interaction` is 2025-12-06T11:30Z, which is 05:30 local on a Saturday. "Next allowed morning slot" from that gives Dec 6 or Dec 8, not the expected Dec 9. See Appendix A.
- The simplest fit is `last_interaction` plus N days, where N comes from the `day3` in the task_id, and it agrees with `follow_up_in_days: 3`. Sample 1 (`day0`) also fits: 09:00 had already passed at 09:04 local, so it rolls to the next morning.
- Your analysis guesses a shared "today," but no `now` exists in the input. The 09:00 vs 10:00 difference is unexplained.
- *Change:* make `now` an explicit input. Model send time as cadence offset plus a local hour. State which reading you chose and why. Confirm with the interviewer.

**F-02. The expected outputs contain facts the design has no source for.**
- *Evidence:* the data model has no amenities, tour URL, or tour availability. The writer is given only first name, property name, and interests (§9 minimizes fields).
- No guard checks factual claims. Invented availability or amenities in leasing copy is an advertising-accuracy risk.
- Observation: sample 1 sends on a Tuesday, and "Thu or Fri" is send date +2 and +3 days, so the slots may be computed.
- *Change:* add a property-facts source (amenities, tour link, tour slots). Restrict the writer to facts in context, add a grounding check, and decide what happens when a fact is missing: drop the claim, never invent it.

**F-03. The core cannot run without the platform, and the evaluation is circular.**
- *Evidence:* context loading requires the database. Raw JSONL appears only as a parenthetical in §7, so there are effectively two code paths.
- The samples serve as few-shot examples, the source of the rules, and the eval set. With two samples this makes any pass rate meaningless.
- The alternatives comparison ([#6](https://github.com/markfyoung0711/rp/issues/6)), your answer to "learns only from input data," is last in the work plan.
- *Change:* define the core as a self-contained decision step (record in, decision out) with no database. Build a held-out set of 20 to 30 varied cases, including no-send cases, kept out of prompts. Move [#6](https://github.com/markfyoung0711/rp/issues/6) to the front.

**F-04. The add-on scope crowds out the core.**
- *Evidence:* voice, external review ingestion ([#10](https://github.com/markfyoung0711/rp/issues/10)), sentiment rollups, row-level security with crypto-shredding, and the three-pane UI carry no graded value and most of the legal risk.
- *Change:* gate all add-ons on the core passing held-out cases. Cut [#10](https://github.com/markfyoung0711/rp/issues/10) and voice dialing. Keep one thin slice (UC-10 reply handling plus STOP), which demonstrates compliance well.

**F-05. Overlap with RealPage's catalogue, and no system-of-record answer.**
- *Evidence:* RealPage's own catalogue lists Knock CRM, an AI Leasing Agent, Online Leasing, the LOFT resident portal, Facilities Management with an AI Facilities Agent, Reputation Management, Lumina agents, and RPX as the integration marketplace.
- The design re-creates Person, Lease, Ticket, tour booking, a resident portal, and review reputation, and defers integrations to "later."
- *Change:* state who owns the resident, lease, and consent records. Position the bot as a decision service fed through integrations. Treat Person, Consent, and Relationship as synced read models. Demote Ticket, Attachment, and reviews to adapters, or cut them.

#### 4.2 Major

**F-06. Consent is modeled too narrowly.**
- Consent is keyed by contact point and channel, not by sending organization or property, and not by purpose (marketing vs transactional).
- There is no provenance: consent captured by a listing site or other third party may not cover this sender.
- Evidence retention (proof of consent, kept for years) conflicts with the deletion rights in §9.
- UC-11 contradicts itself: Part 2 revokes one channel, Part 4 says every channel.
- STOP is routed through the Haiku classifier. STOP handling must be a deterministic keyword match ahead of any model.
- *Change:* resolve the open question in §12 in favor of per-organization contact records. Key consent on (org, contact, channel, purpose). Verify the current revocation rules.

**F-07. Owner-editable quiet hours can fall below the legal floor.**
- Federal and state windows differ by recipient location, and the design assumes the input `timezone` is the recipient's. DST edge cases are not handled.
- *Change:* enforce a non-overridable legal window in the system, let owners only narrow it, and define how the recipient's time zone is derived.

**F-08. Live-channel operations are missing.**
- Outbound sends have no idempotency key, and at-least-once schedulers can double-send. Duplicate texts carry per-message exposure. Re-running a decision on the same record could also duplicate a send.
- There is no frequency cap or contact-history gate.
- Missing setup for live use: US SMS sender registration (A2P 10DLC or toll-free) for a multi-org sender, SPF/DKIM/DMARC per owner sending domain, and one-click unsubscribe headers.

**F-09. Compliance text is generated, then checked.**
- The LLM writes the opt-out wording and CTA, and a weaker model verifies them, against a `safety_violations_max: 0` threshold that a probabilistic guard cannot guarantee.
- *Change:* have the LLM write only a free-text slot. Deterministic composition appends the opt-out footer and CTA block, and the guard becomes a backstop.
- Allow-list the `profile` fields the writer may see, since arbitrary attributes could be protected-class proxies. Your regex guard is English-centric, but `language` is an input.

**F-10. Sentiment (D-012) creates fair-housing exposure through treatment, not content.**
- Sentiment pauses cadences, changes routing, and diverts renewals to a human. Sentiment models can misread dialect, non-native English, and disability-related phrasing. The mitigation is one policy sentence.
- *Change:* require a parity test (error gaps by language and dialect) before sentiment may gate anything. Never let sentiment block a person's path to a human.
- Add human-only intents: reasonable-accommodation requests, discrimination complaints, legal threats, and safety emergencies.

**F-11. UC-12 (maintenance) and UC-15 (renewal) have real-world gaps.**
- Maintenance has no after-hours emergency path (gas smell, flooding, no heat). The bot acknowledges and pauses into a support queue.
- A renewal offer is price communication, which contradicts §13's "never discusses rent pricing." Renewal notices are also often legally timed or worded.
- *Change:* limit renewals to a non-price nudge plus a human hand-off, or explicitly source prices from the property system.

**F-12. The role model collapses owner and operator.**
- "Customer = owner/operator" merges the property owner, the management company that operates and legally sends messages, and the platform.
- Missing: multiple owners per property, delegated authority, and who counts as the legal sender.
- A lease has several parties (roommates, guarantors, students leasing by the bed), but the Person-to-Relationship link is 1:1.

**F-13. The data and security design has internal contradictions.**
- §9 says both a per-org key and a per-person key enable crypto-shredding. Only a per-person key deletes one data subject.
- Decision input snapshots, event payloads, and sentiment signals hold PII outside the field encryption.
- Encrypted phone numbers need a blind index for inbound matching.
- The single `svc_bot` identity is a cross-org confused deputy unless scoped per invocation.
- `DEMO_MODE` quick sign-in should fail closed, with a startup check that refuses to run it outside demo.

**F-14. Metrics and latency are undefined.**
- There is no method for the personalization score or reply-classification F1, and no labeled replies. The intent taxonomy is invented.
- The judge model is the same family as the writer.
- Sequential write, guard, rewrite, and re-guard calls against a 2 s p95 need an explicit budget.

**F-15. D-002 is both overfit and incomplete.**
- The samples imply a rule you don't list: `short_horizon` vs `long_horizon` cadences, which matches about 32 vs 68 days from send date to move date. The threshold is unknown.
- `next_action` maps two data points to two branches.
- Channel selection ignores a missing, unverified, or bounced contact point.

**F-16. AI disclosure conflicts with the graded output.**
- §13 says the bot discloses that it is a bot, but the expected bodies do not. Decide where the disclosure goes and whether graded output includes it.
- Text-to-speech calls are likely "artificial voice" for consent purposes. Verify the current rules before any voice work.

#### 4.3 Minor

- D-017 is marked accepted while its findings are unverified, and [#9](https://github.com/markfyoung0711/rp/issues/9) refers to "D-003 to D-017" though the register runs to D-020.
- Suppress and needs-review outcomes have no defined output schema.
- The sample file has no trailing newline (`wc -l` reports 1), so use a proper JSONL reader.
- LISTEN/NOTIFY breaks behind transaction poolers, and payloads are capped at about 8 KB.
- CAN-SPAM requires a postal address, which the Organization entity lacks.
- Add explicit non-goals: screening, pricing, collections, and legal notices, which have required delivery methods that SMS does not satisfy.

---

### 5. What is solid

- Deterministic rules where the samples show a rule, LLM only for language. This is testable and auditable.
- Authorization enforced inside tools, not in the prompt, so an injection cannot reach other data.
- Consent and quiet hours re-checked when a send fires, not just at scheduling.
- Append-only consent history and a decision trace with the policy version.
- Explicit exclusion of rent pricing and screening, and an origin tag on every record.
- The document's own labeling (ORIGINAL / ANALYSIS / ADD-ON) keeps graded scope visible.

---

### 6. Recommended priorities for today's delivery

These are recommendations for the author, not implementation.

#### Must work
1. A self-contained decision step that reads a JSONL file and produces one output per record, and never crashes. Accept JSONL, a JSON array, or pretty-printed objects. A malformed record yields a safe suppress with an error reason.
2. A defined send-time rule (F-01) with `now` as an explicit input, stated as an assumption.
3. Deterministic composition of opt-out wording and CTA (F-09), with the LLM optional and a guaranteed non-LLM fallback.
4. A single, visible source for property facts (F-02). Decide what to do for a property with no facts.
5. Constraint handling driven by the record itself (`primary_cta`, opt-out, no PII leak) rather than hardcoded to Oak Ridge.

#### Cut from the demo and label "designed, not built"
Database, authentication, row-level security, the three-pane UI, sentiment, external reviews, voice, and findings F-05 through F-13. The document becomes a roadmap and design rationale, which is its real value here.

#### Decisions to settle before the hold-out set arrives

| Situation | Suggested behavior |
|---|---|
| No consent on any channel | Suppress, with a reason |
| Voice preferred and opted in (not built) | Skip to the next consented channel and log why; if it is the only channel, suppress with `unsupported_channel` |
| Suppress output shape | No message, and a `none` next action with a reason; confirm the shape |
| Persona or stage not in the samples | Small persona-by-stage table with a generic fallback |
| `next_action` | Start a cadence when stage is `new`, otherwise follow up in 3 days |
| Cadence name | Derive short vs long horizon from days to move (threshold near 45), and disclose it |
| AI disclosure | A policy flag, off in graded output, stated openly |
| Non-English `language` | Write in that language if the LLM is enabled; otherwise flag the English fallback |

#### Demo-day checklist
- Diff every field of both samples before presenting.
- Write 8 to 10 extra test cases of your own and treat them as unseen: no consent, SMS-only, voice-only, opted out, quiet-hours edge, Spanish, resident persona, missing fields, malformed record, odd name.
- Pre-run everything and keep the outputs. Have an offline path in case the network or API key fails.
- Make the export copy-paste friendly: one combined file plus a readable per-record view (channel, send time, subject, body, reason).
- Prepare a one-sentence answer for each likely pivot: add voice, change quiet hours, add Spanish, add a persona, run at scale. Each answer should name the place where that rule lives.
- Rehearse the assumptions in section 2 out loud. Say them before you are asked.
- Put a **"built vs designed"** table at the top of the solution. Interviewers probe claims, and overclaiming costs more than a small scope.

---

### 7. Answers to the author's five questions

1. **Does the design respect "learns only from input data"?** Partly. A hand-written rule set plus a model for wording is a defensible reading, but two samples cannot support any learning, and using the samples for rules, examples, and evaluation at once is circular (F-03). Present it honestly as rules inferred from data, and show the alternatives comparison ([#6](https://github.com/markfyoung0711/rp/issues/6)) earlier.
2. **Which rules are overfit?** The send-time rule (F-01), `next_action` from two data points, and channel choice (F-15). The horizon rule is missing entirely.
3. **Is the add-on scope a risk?** Yes (F-04). Gate it on core performance against held-out cases.
4. **Gaps and risks:** F-06 through F-14 cover PII and security, demo auth, consent, compliance, and metrics. On the database choice: Postgres is a reasonable choice, but it is not needed for the graded core, and the row-level security and encryption details need the fixes in F-13.
5. **Anything missing from use cases, actors, data?** Property facts (F-02), the owner/operator split and multi-party leases (F-12), human-only intents and emergency paths (F-10, F-11), and frequency caps and idempotency (F-08).

---

### 8. Questions to ask the interviewer or spec owner

1. Do the 12 hold-out records include `expected`, or only inputs? Is scoring automatic or by a person?
2. What is the reference "now" for send times, and how is the day offset in cases like `day3` defined?
3. Is a property-facts source (amenities, tour slots, tour link) assumed? If not, how should missing facts be handled?
4. What should a no-send output look like?
5. Is voice in scope, and is inbound reply handling in scope?
6. How are `personalization_score` and `reply_classification_f1` measured?
7. Which personas and stages will the hold-out contain beyond prospect new/open?
8. Is the output for the hold-out expected to include the reason ("why")?
9. Is this system meant to replace or extend existing RealPage products, or to stand alone?
10. After the 12-record batch, should I expect live "what if" changes or scale questions?

---

### 9. Proposed decision-register entries

| ID | Proposed decision | Status |
|---|---|---|
| D-021 | Core is a self-contained decision step with no database. All platform components are add-ons gated on core results. (F-03, F-04) | Proposed |
| D-022 | Send time = cadence offset plus local hour, with an explicit `now`; supersedes the "next morning slot" rule in D-002. (F-01) | Proposed |
| D-023 | Property facts come from a declared source; the writer may not state unsourced facts. (F-02) | Proposed |
| D-024 | Opt-out and CTA text are composed deterministically; the model writes only a free-text slot. (F-09) | Proposed |
| D-025 | Held-out evaluation set is kept separate from the samples used for rules and examples. (F-03) | Proposed |
| D-026 | Consent is scoped by sender, channel, and purpose; STOP is matched deterministically. (F-06) | Proposed |
| D-027 | Sentiment cannot gate outreach or routing until a parity test passes; human-only intents defined. (F-10) | Proposed |
| D-028 | Renewal outreach carries no price content. (F-11) | Proposed |
| D-029 | Voice dialing and external reviews are deferred; consent fields remain modeled. (F-04) | Proposed |

---

### Appendix A: send-time arithmetic

| | Sample 1 (`day0`) | Sample 2 (`day3`) |
|---|---|---|
| `last_interaction` (UTC) | 2025-12-08 15:04 | 2025-12-06 11:30 |
| Local time (America/Chicago, UTC-6) | Mon Dec 8, 09:04 | Sat Dec 6, 05:30 |
| Expected `send_at` | Tue Dec 9, 09:00 | Tue Dec 9, 10:00 |
| Offset from last interaction | +1 day (09:00 already passed at 09:04, so next morning) | +3 days |
| "Next morning slot" from last interaction | Dec 9 09:00 (matches) | Dec 6 or 8 (does not match) |
| `last_interaction` + N days (N from task_id) | Dec 8 09:00, already passed, rolls to Dec 9 (matches) | Dec 9 (matches) |
| Days from send date to `move_date_target` | 32 | 68 |

Sample 1 sends on a Tuesday, and the expected "Thursday or Friday" is send date +2 and +3 days.

### Appendix B: traceability, spec requirement to solution

| Requirement | Coverage | Note |
|---|---|---|
| Decide whether to communicate | Partial | Gates defined, but no-send output shape and cases missing |
| Choose channel | Partial | Rule from D-002; voice and contact-point checks missing (F-15) |
| Choose send time | Conflict | Rule fails on sample 2 (F-01) |
| Write message | Partial | Facts have no source (F-02) |
| Opt-out instructions | Covered, weakly | Generated then checked (F-09) |
| `primary_cta` mapping | Covered | Options and link data source missing (F-02) |
| `fair_housing_check_passed` | Partial | Content guard only; treatment risk (F-10) |
| `no_pii_leak` | Partial | Field minimization; storage gaps (F-13) |
| `brand_style_applied` | Gap | No brand style source on the graded path |
| p95 latency 2,000 ms | Gap | No budget (F-14) |
| `personalization_score_min` | Gap | Metric undefined (F-14) |
| `reply_classification_f1_min` | Gap | No labeled replies (F-14) |
| `safety_violations_max: 0` | Partial | Probabilistic guard (F-09) |
| "And why" | Partial | Decision reasons exist; not in output shape |
| `next_action` | Partial | Two data points; horizon rule missing (F-15) |
| Export of 12 hold-out outputs | Gap | No export path or format defined |


### Review 1 addendum — core functionality focus

> Pasted word for word, 2026-09-24.

Build a single decision step that turns one input record into one output. Everything else in the solution document should be presented as "designed, not built." I don't know how much time you have left or what already exists, so this is in priority order. Stop when the time runs out, and don't skip ahead.

**Must work, in this order**

1. **Read input without crashing.** Accept JSONL, a JSON array, or pretty-printed objects. Return one output per record, and turn a bad record into a safe no-send with a reason.
2. **Consent and channel.** Pick the first preferred channel the person has opted in to. Skip voice, since it isn't built. If nothing qualifies, don't send and record why.
3. **Send time.** Use `last_interaction` plus the day number from the task_id (`day3` means +3). If there is no day number, use a stage default. Send at 9:00 local for SMS and 10:00 for email. If that moment has already passed, roll to the next day. Take `now` as an explicit input and state your rule out loud.
4. **Message content.**
   - Greet by first name and use the property name.
   - Personalize from amenity interests and move date.
   - Map `book_tour` to `schedule_tour`, with reply options for SMS and a link for email.
   - Add the opt-out line for the channel with fixed wording, not model-generated.
   - Use templates first. A model-written sentence is optional, and the templates must work without it.
5. **Next action.** For a new lead, start a cadence, with the short or long horizon name based on days to move-in (threshold around 45). For anyone else, follow up in 3 days.
6. **Light guards.** Check that the opt-out is present, no phone or email leaks into the body, no protected-class words appear, and a suspicious first name gets replaced with "there."
7. **Property facts in one place.** Keep amenities, tour days, and tour link in one small file. If a property has no facts, send a generic message with no specific claims.
8. **Export.** Write a combined output file plus a readable per-record view showing channel, send time, subject, body, and reason.

**Done when**
- Both samples match on every field you can control, including channel, send time, call to action, and next action. The body should match closely.
- You have written 8 to 10 extra cases and none crash. Cover no consent, opted out, voice-only, SMS-only, Spanish, a resident persona, missing fields, and an odd name.
- Running the same input twice gives identical output.

**Skip today**
Database, login, the three-pane UI, sentiment, reviews, voice, and inbound reply handling. Show them as "designed, not built."

**Demo flow**
1. Run the two samples.
2. Show the reasoning behind each field.
3. Run two or three edge cases live.
4. Export, then state your assumptions.

If you tell me how many hours remain and whether any code exists, I can trim this list to fit. If you want, I can also draft a rehearsal script for the demo. Neither involves writing code.

---

## Review 2 of 2 — SME review (Gemini, Google AI Mode)

> Pasted verbatim, 2026-09-24.

### 🚨 SME Critical Review & Red Flag Analysis
Mark, you are in immediate danger of failing this interview demo at 12:00 Noon today.
As a property management Subject Matter Expert (SME), I can tell you that your architecture document is incredibly thorough, but your focus is dangerously misplaced for a noon delivery. You have succumbed to extreme scope creep. You are spending critical hours designing complex database schemas, CRM dashboards, multi-tenant RBAC logic, and external Yelp/Google review pipelines.
The interviewer gave you one explicit, unbending directive: "Be prepared to ‘export’ or ‘copy-paste’ the 12 outputs from a hold-out set that is provided during the interview".
If your core script cannot process a raw JSONL file, evaluate the 12 lines within 2 seconds per line, and spit out structurally perfect JSON matching the expected schema, you will fail.. It will not matter that your React front end looks like Zendesk.
------------------------------
### 1. Direct Answers to Your Challenge Questions## 1. "Does the design respect 'learns what to do only from input data'?" [2]
No, but your implementation strategy is still correct. Pure machine learning where the code learns dynamically on the fly from two records is impossible. Your approach—using deterministic python code for execution rules and an LLM for copy generation—is the only way to build a stable system by noon.

* The "Learn Only" Fix: To truly claim your bot "learns from input data," you must feed the existing sample.jsonl file directly into your LLM prompt as Few-Shot Examples. Let the LLM read the input and expected blocks of the samples to "learn" the semantic translation, while your Python wrapper handles strict gates like channel consent.

### 2. "Which rules inferred from only 2 samples are overfit?" [2]

* The Send-Time Rule: Your assumption that "all messages send on 2025-12-09 in the morning" is highly overfit. Look closely at the task_id fields. prospect_welcome_day0 was sent exactly 1 day after the last_interaction (12-08 to 12-09). prospect_long_horizon_day3 was sent exactly 3 days after its last_interaction (12-06 to 12-09). The send_at date is calculated by adding the day offset implied in the lifecycle cadence to the last_interaction timestamp.
* The Morning-Hour Rule: The 09:00 vs 10:00 send times aren't random. Notice that the email target is 10:00 and the SMS is 09:00. This implies property management compliance: texting earlier to grab attention, delaying emails slightly so they don't get lost in a morning inbox sweep.

### 3. "Is the add-on scope at risk of crowding out the graded core?" [2]
Yes, completely. You have designated 13 use cases to "Add-on Scope". None of them matter at 12:00 PM. If you spend time writing an attachment scanner for billing disputes or an integration for Yelp APIs before the 12-line batch processor is bulletproof, you are tanking the demo.
### 4. "Gaps and risks: database choice, legal, security" [2]
For the noon demo, the database choice is irrelevant because you shouldn't use one.. Your pipeline must be stateless: JSONL String In ➡️ Process ➡️ JSONL String Out.
------------------------------
### 2. The Real Estate SME Risk Matrix: The True "Hold-Out" Traps
Your hold-out set table is accurate, but you missed the most lethal real estate specific edge-cases that an industry interviewer will use to break your bot:

| Hold-Out Scenario | The Real Estate SME Operational Risk | What Your Bot Must Do |
|---|---|---|
| The Familial Status Trap | A prospect's profile text says: "Moving with my 4 kids, need a place near a daycare." [2] | Fair Housing Violation (FHA). The LLM must never mention the children, comment on the family size, or limit property options to ground floors or specific blocks ("steering"). It must treat them identically to a solo applicant. |
| The Absolute Silencer (STOP) | Inbound text contains standard TCPA keywords: "STOP", "QUIT", "UNSUBSCRIBE". | Immediate Suppression. Hardcode a regex router at the very front of your script. If these keywords hit, set next_message to null and do not invoke the LLM. Do not risk an LLM ignoring or hallucinating a compliance command. |
| The Over-the-Line CTA | The primary_cta is passed as collect_deposit or sign_lease instead of book_tour. | Fallback Logic. The system must map this to a secure link schema (https://property.example) and change body text from welcoming to transactional, while retaining opt-out copy. |

------------------------------
### 3. Immediate Triage Action Plan (Next 8 Hours)
Stop working on the web interface, the Docker configuration, and the database migrations. Do this instead:

   1. Build a Pure CLI Batch Processor (run_eval.py):
   Create a script that accepts an arbitrary file path (python run_eval.py --input holdout.jsonl), loops through every line, executes your bot logic concurrently to respect the p95_latency_ms: 2000 threshold, and writes an output JSONL file.
   2. Hardcode the Structural Mappings:
   Do not let the LLM guess the JSON structure. Use Pydantic with response_format={"type": "json_object"} to guarantee your output explicitly mirrors the expected block: channel, send_at, subject, body, and cta.
   3. Draft Your Mock Hold-Out Dataset Now:
   Generate 12 lines of fake test cases right now based on your variations table. Run them through your CLI. If your script crashes on a missing profile field or a non-Chicago timezone, fix the exception handling immediately.

To ensure your script doesn't throw a validation error during the live run, tell me:

* Have you already written the Pydantic schema for the output object?
* What Python framework are you using to manage your LLM calls (e.g., raw OpenAI/Anthropic SDK, LangChain, Instructor)?

I can provide the clean wrapper code to ensure your processing stays under the 2-second timeout window.

### Review 2 addendum — core functionality blueprint

> Pasted word for word, 2026-09-24.

Yes, I have defined it. To guarantee you pass the interview demo at noon today, core functionality must be stripped of all software engineering platform overhead (databases, UIs, webhooks) and defined strictly as a stateless, CLI-driven batch processing pipeline.
Here is the exact blueprint of the core functionality you must target and lock down over the next few hours to handle the 12 surprise hold-out records:
### 1. The Core Execution Pipeline (Stateless)
Your script must implement this exact 5-step loop for each line in the incoming JSONL file:

* Ingestion: Read a line from the input file and parse it into an internal Python dictionary or Pydantic model.
* Consent & Suppression Gate (Hardcoded Code): If consent flags for all listed channel_preferences are false, immediately short-circuit. Set next_message to null, set next_action to a suppression status, and record the reason. Do not call the LLM for this record to save latency and ensure compliance.
* Channel & Timing Derivation (Hardcoded Code):
* Select the first channel in channel_preferences where consent is true.
   * Parse input.last_interaction and add the day offset implied by the lifecycle_stage or task_id (e.g., day0 = +0 days, day3 = +3 days). Map this to the target local timezone and output a perfectly formatted ISO 8601 string with the correct UTC offset.
* Content Generation (Structured LLM Call): Pass the input profile fields, the chosen channel, the target CTA, and the sample.jsonl data (as few-shot context) to the LLM. Enforce a JSON schema constraint so the LLM only fills out the text fields (subject, body, cta.link/options).
* Output Construction & Aggregation: Package the decisions back into the exact structural shape of the expected block from the spec, ensuring it includes the record's original task_id.

### 2. Performance & Operational Benchmarks

* The 2-Second Timeout: The spec explicitly demands p95_latency_ms: 2000. You cannot process 12 items sequentially if each LLM call takes 1.5 seconds. Core functionality must use Python's asyncio or concurrent.futures to fire all 12 API calls to Anthropic/OpenAI in parallel.
* Fault-Tolerant Loop: If record [#4](https://github.com/markfyoung0711/rp/issues/4) has a malformed timezone or missing name field, your script must not crash. Core functionality includes wrapping each row's execution in a try/except block, logging the error for row [#4](https://github.com/markfyoung0711/rp/issues/4), and continuing to generate valid outputs for the remaining 11 rows.
* One-Click Export: You must be able to run a terminal command like python bot.py --input holdout.jsonl --output results.jsonl and have it instantly available to copy-paste or upload.

### 3. Defer Everything Else (The "Drop" List)
To hit your noon deadline, you must completely drop the following features from your active build list:

* ❌ PostgreSQL database migrations and row-level security setup.
* ❌ React split-pane frontend interfaces.
* ❌ Real Twilio / SendGrid API integrations (use the sandbox text-only format).
* ❌ Yelp and Google review scraping or ingestion pipelines.
* ❌ Inbound webhook routers for handling inbound maintenance text messages.

To ensure this core pipeline works seamlessly, tell me:

* Do you want me to write the complete, async Python script (bot.py) that handles this exact ingestion, parallel LLM execution, and JSONL output mapping?
* Which LLM provider and model (e.g., Anthropic Claude Sonnet 3.5, OpenAI GPT-4o) do you have API keys ready for right now?

---

## Reconciliation of reviews 1 and 2

> **ANALYSIS — ours.** Where the two reviews agree, where they differ, and what we are adopting.

**Both agree:**
- the add-on scope must be cut for today
- no database; a stateless batch process: JSONL in → one output per record → JSONL out
- fixed code handles gates, consent, STOP and the output structure; the LLM writes only the wording
- `send_at` = `last_interaction` + the cadence day offset, not a shared "today". This replaces D-002's reading.
- build our own mock hold-out set now and harden against missing fields and other timezones

**Where review 2 needs correcting or qualifying:**

| Claim in review 2 | Our assessment |
|---|---|
| `day0` was sent "exactly 1 day after" last interaction | That contradicts its own offset rule (day0 = +0 days). Review 1's explanation fits better: at +0 days the 09:00 slot had already passed (last interaction was 09:04 local), so the send rolls to the next day's 09:00. |
| SMS goes at 09:00 and email at 10:00, as a rule | Plausible, but only one data point per channel, and the channel *and* the cadence both differ between the two samples. Keep the send hour in config (per channel), state it as an assumption, and don't claim it as a compliance rule. |
| `response_format={"type": "json_object"}` | That is OpenAI's API. With Claude, use structured outputs (tool/JSON schema) validated by Pydantic. Better still, the model returns only the text slots (subject and body) and code assembles the rest (D-025). |
| Map `collect_deposit` / `sign_lease` to `https://property.example` | Agree with the transactional tone and keeping the opt-out wording. But a made-up link is an unsourced fact (D-024): use a link from the declared property-facts source, or a clearly marked placeholder, and flag it. |
| Feed `sample.jsonl` into the prompt as few-shot examples | Adopt. This is our best answer to "learns only from input data". Keep the mock hold-out cases *out* of the prompt so the evaluation stays honest (D-026). |

**New from review 2 (adopted):**
- **Familial-status trap:** protected-class details in the profile (children, religion, disability, national origin, …) must never appear in the message or change what is offered. Remove them before the prompt and check the output. Add a mock hold-out case for this.
- **STOP keywords:** a fixed keyword gate (STOP, STOPALL, UNSUBSCRIBE, CANCEL, END, QUIT) at the very front, before any model call. If any inbound text field matches: no message, and the LLM is not called.
- **Unknown or transactional `primary_cta`:** a fallback CTA table, with a transactional tone and the opt-out wording kept.
- **CLI first:** `run_eval.py --input <file> --output <file>`, with records processed concurrently and latency measured against the 2,000 ms p95.

**The review 2 addendum (core blueprint) is adopted as the build spec for today,** with one correction: it restates "day0 = +0 days", but the expected `send_at` for `prospect_welcome_day0` is the *next* day at 09:00. The base time plus the offset (09:04 local) is already past the 09:00 send hour, so the send rolls to the next day. The rule is: `candidate = local(last_interaction) + offset days`, set to the send hour; if that is not after `last_interaction`, add one day. This reproduces both samples.

Its closing questions (which provider and model) are answered by D-014: Anthropic Claude, with Haiku 4.5 for speed under the 2 s p95, and Sonnet 5 as an option.

### Merged core build spec (review 1 addendum + review 2 addendum)

The two blueprints agree on the pipeline: ingest → consent/channel gate → send time → content → output. They differ on one point: **how the text is written.**

| | Review 1 | Review 2 | Merged |
|---|---|---|---|
| Body text | Templates first; a model sentence is optional | LLM with the samples as few-shot examples | **A template baseline that always works**, plus an optional LLM mode (`--llm`) with the samples as few-shot examples. The LLM writes only the free-text part; the opt-out and CTA are fixed code in both modes. |
| Determinism | The same input twice gives identical output | Not addressed | Template mode is deterministic. LLM mode uses temperature 0 plus a response cache keyed by the record, so a re-run is identical. |
| Input formats | JSONL, a JSON array, or pretty-printed objects | JSONL | All three |
| Send time | `last_interaction` + day N from `task_id`, else a stage default; SMS 09:00, email 10:00; roll forward if passed; explicit `now` | `last_interaction` + offset, to local ISO 8601 | Review 1's rule (the most complete); `now` is optional and used only for the "has it passed" check |
| `next_action` | New lead → start a cadence (short/long horizon, threshold ~45 days to move-in); otherwise follow up in 3 days | Not specified | Review 1's rule |
| Guards | Opt-out present, no phone/email in the body, no protected-class words, suspicious name → "there" | Protected-class details removed; fixed STOP gate first | Both |
| Property facts | One small file; no facts → a generic message with no claims | Not specified | Review 1's rule (`data/properties.yaml`) |
| Concurrency | Not specified | asyncio, all records in parallel | asyncio in LLM mode (template mode is instant) |
| Export | Combined output file plus a readable per-record view | `--output results.jsonl` | Both |
| Done when | Both samples match on the controllable fields; 8–10 extra cases, no crash; deterministic | No crashes on bad rows | Review 1's criteria |

---

## Review 2 reference implementation: `bot.py` (Gemini)

> Saved unchanged as [`reference/bot_gemini.py`](../reference/bot_gemini.py). Our code review, 2026-09-24. The send-time results below come from running its functions against `sample.jsonl`.

**What it gets right:** a stateless async batch; a consent gate that short-circuits before the LLM; channel = first preferred channel with consent; send time from `last_interaction` plus the `dayN` offset in local time; SMS 09:00 / email 10:00; per-record try/except around the LLM; temperature 0; the samples as few-shot examples.

**Problems, by severity:**

| # | Severity | Problem | Evidence / effect |
|---|---|---|---|
| G-01 | Blocker | **Fails sample 1's `send_at`:** no roll-forward, so `day0` gives `2025-12-08T09:00`, which is before the 09:04 last interaction | Ran it: `prospect_welcome_day0` → `2025-12-08T09:00:00-06:00`, expected `2025-12-09T09:00:00-06:00`. Sample 2 matches. |
| G-02 | Blocker | **Model `claude-3-5-sonnet-20241022` is retired:** every LLM call errors, so every record that should get a message comes out as an `error` | Use Haiku 4.5 (speed) or Sonnet 5 |
| G-03 | Blocker | **No template fallback:** with no key, a network failure or an API error, the record returns `error` with no message | D-038 needs a template baseline that always works |
| G-04 | Blocker | **The whole record goes into the prompt, including `expected`** if the hold-out records carry it. The model can copy the answer (contaminating the evaluation), and every profile field is sent (PII, protected-class details) | Send only allow-listed fields; strip `expected` |
| G-05 | Major | **One malformed JSONL line crashes the whole batch:** `json.loads` in `main()` is outside any try. Only JSONL is accepted (not a JSON array or pretty-printed objects) | D-038 input rule |
| G-06 | Major | **Opt-out wording, CTA and `next_action` are written by the LLM:** not deterministic, and not guaranteed | D-025 / D-038: fixed code. `next_action` should follow the new → cadence (short/long by 45 days) rule, otherwise follow-up 3 |
| G-07 | Major | **Invented facts:** falls back to `https://<property>.example/tour`, and the SMS options default to `["Thu","Fri"]` | D-024: take them from the property-facts file, or send a generic message |
| G-08 | Major | **Voice can be selected** (if `voice_opt_in` is true and first in preferences), then gets an email-style link CTA | Skip voice (D-038) |
| G-09 | Major | **No STOP keyword gate, and no guards on the output:** fair housing is left to prompt wording only; no check for opt-out present, PII or protected-class words | D-033, D-034 |
| G-10 | Minor | Send-time parse fails on fractional seconds and silently returns the raw UTC string as `send_at` | `...15:04:00.123Z` → returned unchanged |
| G-11 | Minor | A missing `last_interaction` defaults to `utcnow()`, so the output isn't reproducible; `utcnow` is deprecated | Use an explicit `--now` |
| G-12 | Minor | JSON is parsed out of free text, not through structured output (tool/JSON schema) | Fragile |
| G-13 | Minor | No `--output` file, no per-record readable view, no latency measurement; the output key is named `expected` | D-038 export rules |

**Verdict:** a useful sketch that confirms the pipeline shape, but **not a safe base for the demo**. As written it fails sample 1, and every LLM call fails on the retired model. We build our own to D-038 and borrow its structure (the async gather, the consent loop, the few-shot block).

---

# Appendix B — Code-review results

> From `plans/code-review-results.md`.

| # | Sev | Finding | Reproduction | Expected → actual | Fix | Status |
|---|---|---|---|---|---|---|
| 1 | P0 | Output file not byte-identical across runs | Run the samples twice with `-o`, then `cmp` | identical → differed (`latency_ms`) | Timing removed from the export (still shown on screen) | Fixed, auto |
| 2 | P0 | No README; the claims and commands can't be checked | `ls README*` | a README → none | README with commands, output shape, built vs designed, assumptions | Fixed |
| 3 | P0 | Time-zone data may be missing on the demo machine (Windows) | Dependency review | `tzdata` pinned → absent | Added `tzdata` dependency | Fixed, auto |
| 4 | P0 | LLM timeout too long: 20 s × 3 attempts = up to 60 s per record if the network hangs | Code read (`AsyncAnthropic(timeout=20, max_retries=2)`) | bounded → up to 60 s | 8 s, 1 retry, then the template | Fixed, auto |
| 5 | P1 | `channel_preferences` of the wrong type → internal error → human review | `channel_preferences: 5` | handled with a warning → TypeError | Non-list values ignored with a warning; default order used | Fixed, auto |
| 6 | P1 | Names in non-Latin scripts replaced by "there" | `first_name: "李"` | "Hi 李" → "Hi there" | Name check accepts letters from any script | Fixed, auto |
| 7 | P1 | Duplicate `task_id` not flagged | The same record twice | a warning → none | Batch-level warning on each duplicate | Fixed, auto |
| 8 | P1 | Steering word list incomplete ("families", "adults only", "no kids", …) | Word-list review | blocked → not in the list | Terms added to `protected_terms` | Fixed, auto |
| 9 | P1 | Lint/type: ruff reports style only in our code (plus the Gemini reference file); mypy reports 5 typing-only issues (Optional narrowing, SDK overload typing) | `uv run ruff check outreach bot.py tests`, `uv run mypy outreach bot.py` | — | Intentional broad `except` blocks annotated; typing left as is | Accepted, no behavior impact |

**Checks that passed without changes:** no sample literals in code (Oak Ridge appears only in `config/properties.yaml` as property facts); channel matrix (voice first → SMS, with the skipped channel logged); no consent / null / "maybe" consent → no send; DST boundary (−05:00 after Mar 8); invalid time zone → the property's; horizon edge (45 → short, 46 → long); past or missing move date → short; resident/renewal → no tour push, no price; injection in the name or profile not repeated; unknown property → no specific claims; no PII in outputs; protected profile fields (`has_children`, `religion`) not used; bad key in `--llm` → template fallback, both samples still match; clean clone + `uv sync` → samples match; send hours inside 08:00–21:00.

**Open for a human decision:** none that blocks the demo. A missing `last_interaction` uses the current time (flagged as not reproducible); `--now` makes it reproducible.

### Automated re-run

2026-09-24, `scripts/run_checks.py --full` (after the fixes above): **24/24 passed, 0 P0 failures.** The `run-checks` skill (`.claude/skills/run-checks/SKILL.md`) repeats this run.

---

# Appendix C — Performance

> From `plans/performance.md`.

Input: `tests/perf_100.jsonl`, 100 varied synthetic records from `scripts/gen_records.py 100` (seed 42). It mixes personas, stages, channels, consent, time zones (including missing ones and "Central"), Spanish, and fair-housing trap notes. Target from the samples: `p95_latency_ms: 2000` per record.

**p95** = the 95th-percentile latency: 95% of records finish within this time. With 12 records it is effectively the slowest one.

| Run | Records needing a model call | Wall time (whole batch) | p95 per record | Model failures |
|---|---|---|---|---|
| Template mode (default) | 0 | 0.17 s | 0.6 ms | — |
| `--llm`, cold cache, 16 parallel calls | 78 | 7.95 s | 6,322 ms ❌ (queueing) | 0 |
| `--llm`, cold cache, 64 parallel calls | 78 | 4.34 s | 2,918 ms | 0 |
| `--llm`, warm cache (re-run) | 0 new | 0.18 s | 0.9 ms | — |
| `--llm`, cold, first 12 records (the hold-out size), 2 runs | 7 | 2.4–2.6 s | ~2,055 ms (borderline) | 0 |

**Also verified on the 100 records:**
- the opt-out is present on every sent message
- no trap words ("kids", "church") leak through
- `--llm` decisions (channel, send time, next action) are identical to template mode: 100/100
- a `--llm` re-run is byte-identical, from the cache
- 22 no-sends, all "no channel with consent"
- memory stays around 37 MB

**Conclusions**
- **Template mode meets the target by three orders of magnitude.** Use it for the graded hold-out run.
- `--llm` is limited by the model's response time (~1.2–2 s per call) and by how many calls run at once. The concurrency is now 64 (`BOT_LLM_CONCURRENCY`). At the hold-out size of 12 it sits right at the 2 s target, so present it as the optional "learns the wording from the samples" mode, not the graded run.
- At scale, throughput is governed by the API rate limit, not by the bot. Records are independent, so a queue plus workers scales out.

### 100K records

**Template mode, measured:** 100,000 generated records (55 MB) processed in **52 s** (~0.5 ms per record), with **~1.2 GB peak memory**, because the whole batch is held in memory. $0 in API cost. Streaming the file in chunks would cut the memory; not needed at hold-out size.

**`--llm` mode, estimated** from measured token counts (`count_tokens`: ~1,670 input tokens per call; ~100 output tokens). Only records that will be sent need a call; that was ~78% in the generated mix.

| Model / API | Calls | Input cost | Output cost | Total |
|---|---|---|---|---|
| Haiku 4.5, real time ($1 / $5 per M tokens) | ~78,000 | ~$130 | ~$39 | **~$170** (all 100K: ~$220) |
| Haiku 4.5, Batch API (50% off, results within 24 h) | ~78,000 | ~$65 | ~$20 | **~$85** |
| Sonnet 5, real time ($2 / $10) | ~78,000 | ~$260 | ~$78 | **~$340** |

Time for `--llm` at 100K is set by the account's rate limit, not the bot: at 64 parallel calls of ~1.5 s each, about 40 calls/s, so **~30 min**, if the tier allows ~2,500 requests per minute. A lower tier would need throttling or the Batch API. Prompt caching wouldn't help much: the shared prefix (~1,500 tokens) is below Haiku's minimum cacheable length.

---

# Appendix D — PII categories and handling

> From `plans/pii-categories.md`.

| Tier | Category (as reported in RUN STATS) | Examples planted |
|---|---|---|
| Highest | government ID (SSN/ITIN/license/passport) | SSN, ITIN, driver's license, passport; SSN typed into the first-name field |
| Highest | bank / payment card | bank account, routing number, card number, disbursement account |
| Highest | credit / screening / eviction | credit score, background check, eviction history, adverse action |
| Highest | income / employment | income, employer, pay stubs, tax returns |
| Highest | health / disability / accommodation | medical note, accommodation request, assistance animal; health words in free text |
| Highest | immigration / domestic-violence status | immigration status, VAWA; "domestic violence" in free text |
| Highest | household members (occupants, children) | occupants with DOB, children's names |
| Direct | email, phone, date of birth, address (current/former), last/full name | profile fields, top-level fields, inside notes |
| Direct | signature / photo / ID image | signature data, photo URL, ID scan |
| Direct | emergency contact / guarantor / co-signer | nested contact and guarantor objects |
| Context | unit / lease data | unit number, lease dates, rent amount, move-out date |
| Context | payment / ledger / delinquency | ledger, balance, past due, payment history |
| Context | access / device / vehicle / recordings | access code, smart-lock log, plate, vehicle, voicemail, IP, device ID |
| Context | derived scores / inferences | sentiment score, risk score |
| Owner/vendor | owner / vendor tax ID (EIN, TIN, W-9) | EIN, tax ID, W-9 |
| Owner/vendor | owner identity (LLC / trust members) | beneficial owners, trustee |
| Related | protected-class details (counted separately, fair housing) | race, religion, familial status, has_children, national origin, marital status, age, veteran |

**How the bot applies "minimum necessary"**
- **Output:** only the first name (in the greeting, as in the samples) and the caller's `task_id`. Every other category above stays out of the body, subject, `why` and warnings. A rejected first name is never echoed.
- **Weak channels (SMS/email):** messages never carry money amounts, balances, lease terms, or account- or ID-like numbers. A guard blocks `$`, decimal amounts and 8+ digit runs. The rent reminder says "your payment", not the amount.
- **Model prompts (`--llm`):** only allow-listed fields (first name, property, interests, move timing, CTA type). A test checks that none of the planted data reaches the prompt.
- **Wrong-number risk:** a reassigned number would still receive the greeting and the property name, which is inherent in the expected outputs. Messages carry no case details beyond that.
- **Storage:** the bot keeps no logs of records. Output files contain only the fields above. The `--llm` cache stores only model answers, keyed by a hash.
- **Identity boundary (D-048):** the bot echoes only the caller's `task_id` as its join key. Identifying the parties and resolving contact details belong to the system of record, which uses opaque internal IDs.

---

# Appendix E — Demo tests

> From `plans/demo-tests.md`.

Every command runs from the project folder (`~/realpage`) with no network, unless it says `--llm`. `--only <text>` shows just the records whose task_id contains that text.

### 1. The graded core

| # | Command | What it shows |
|---|---|---|
| 1 | `uv run bot.py -i plans/sample.jsonl --compare` | Both samples match **every field**: channel, send time, subject, body, CTA, next action (✅ per field) |
| 2 | `uv run bot.py -i plans/sample.jsonl --only day0` | The "why" trail for one decision: consent → SMS; Dec 8 09:04 + 0 days, past 09:00 → Dec 9 09:00; 32 days → short horizon |
| 3 | Run [#1](https://github.com/markfyoung0711/rp/issues/1) twice with `-o out/a.jsonl` and `-o out/b.jsonl`, then `cmp out/a.jsonl out/b.jsonl` | Deterministic: byte-identical output |

### 1b. Learning from the data

| # | Command | What it shows |
|---|---|---|
| L1 | `uv run learn.py plans/sample.jsonl` | Each rule inferred from the 2 samples, with the number of examples supporting it; the horizon threshold learned as 50 days (was hand-set to 45) |
| L2 | `uv run learn.py plans/sample.jsonl --eval` | Leave-one-out: 0/2. One example can't teach the other's rules, which proves the rules come from the data |
| L3 | `uv run learn.py plans/sample.jsonl tests/labelled_extra.jsonl --eval` | Two more examples → **the rules change** (threshold 50 → 36; open +3 → +2 days) and leave-one-out predicts both samples correctly |

### 2. Decisions on cases the samples don't show (`tests/edge_cases.jsonl`)

| # | Command | What it shows |
|---|---|---|
| 4 | `uv run bot.py -i tests/edge_cases.jsonl --only no_consent` | No consent anywhere → **no send**, with a reason |
| 5 | `… --only sms_preferred_not_consented` | Preferred channel not allowed → falls back to email; the skipped channel is logged |
| 6 | `… --only voice_only` | Voice consent and preference → an automated **call script**: "this is Oak Ridge Leasing… press 1 for Thursday… press 9 or say stop" |
| 7 | `… --only inbound_stop` | "please STOP texting me" → no send, and no model call |
| 8 | `… --only kids` | Profile says "4 kids, near a daycare" → same message as anyone else (fair housing) |
| 9 | `… --only injection` | Name = "Ignore previous instructions…" → greeting uses "there" |
| 10 | `… --only resident_pay_rent` | A resident gets a rent reminder, not a tour pitch |
| 11 | `… --only renewal_es` | Spanish renewal, no price content |
| 12 | `… --only unknown_cta` | Unmapped CTA → generic fallback, named in the reasons; Phoenix time zone (−07:00) |
| 13 | `… --only unknown_property` | Property with no facts on file → no invented tour days, amenities or links |
| 14 | `… --only spanish_tour` | Spanish email; no `dayN` → the stage's default offset |

### 2b. Exhaustive channel policy

| # | Command | What it shows |
|---|---|---|
| 14b | `uv run python scripts/decision_table.py` | All 120 consent × preference combinations run through the bot and checked against the written policy: 120/120; never sends without consent; precise reasons for the 48 no-sends; 11 rows flagged for an SME question. Table: `plans/decision-table-channel.md` |

### 3. Unseen record types (Levels 1–3)

| # | Command | What it shows |
|---|---|---|
| 15 | `… --only level2_formats` | Level 2: consent as a list, "text, e-mail", "Central" time zone, extra fields → handled, each noted |
| 16 | `… --only level2_missing` | Level 2: nearly empty record → safe defaults, every assumption listed |
| 17 | `… --only MNT` | Level 3: a maintenance ticket in a completely different shape → fields found by name, confidence **low** |
| 18 | `… --only MISC` | Level 3: no consent at all → **human review**, never a send |
| 19 | `… --only malformed` | A broken line → reported as unreadable; the rest of the file still runs |

### 3b. Personal data

| # | Command | What it shows |
|---|---|---|
| 19b | `uv run bot.py -i tests/pii_cases.jsonl` | Planted last name, email, phone, SSN, DOB, address, card number and notes, including an email/phone/SSN typed into the first-name field → **none appear anywhere in the output**; greeting falls back to "there"; RUN STATS shows `PII scan … PASS` |

### 4. Messy input (`tests/garbage_inputs.txt` and others)

| # | Command | What it shows |
|---|---|---|
| 20 | `uv run bot.py -i tests/garbage_inputs.txt` | A chat-style paste: prose, numbering, code fences, comments, smart quotes, trailing commas, a Python-style dict, JSON inside a string, an array on one line, `Task_ID` key variants, `input` as a string → **13 of 14 recovered**, each repair noted; the truncated one reported |
| 21 | `uv run bot.py -i tests/garbage_utf16.jsonl` | A Windows UTF-16 export → decoded |
| 22 | `uv run bot.py -i tests/not_records.png` | An image instead of records → a clear refusal, exit code 2, no fake records |
| 23 | `uv run bot.py --paste` (paste anything, then Ctrl+D) | Live paste from the interviewer's chat or email |

### 5. Scale and the AI option

| # | Command | What it shows |
|---|---|---|
| 24 | `uv run bot.py -i tests/perf_100.jsonl` | 100 varied records in ~0.2 s; p95 well under 2,000 ms |
| 25 | `uv run bot.py -i tests/edge_cases.jsonl --llm` | Cost guard: **stops loudly** (exit 3) before any API call and says how many paid calls, tokens and **dollars were avoided**; points to the free template mode |
| 25b | `BOT_LLM_BUDGET_USD=0.10 uv run bot.py -i plans/sample.jsonl --llm --compare` | Spending limit: within the budget → one `[cost]` line and the run proceeds; over it (e.g. `--budget 0.001`) → stops loudly with the overage. Re-runs are cached, so they cost $0 and show no banner |
| 26 | `BOT_ALLOW_API_COST=1 ANTHROPIC_API_KEY=bad uv run bot.py -i plans/sample.jsonl --llm --compare` | API unavailable (the bad key is rejected, never billed) → template fallback; both samples still match |

### 6. Whole-system checks

| # | Command | What it shows |
|---|---|---|
| 27 | `uv run pytest` | Unit tests: samples, edge cases, determinism, input formats, garbage, binary refusal |
| 28 | `uv run python scripts/run_checks.py --full` | The code-review checklist, automated: 34 checks, including a clean-clone install and the cost guard |

**Suggested live order (about 6 minutes):** 1 → L1 → L3 → 2 → 8 → 4 → 17 → 20 → 22 → 24, then the hold-out itself.

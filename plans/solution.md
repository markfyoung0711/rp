# Solution: Context-Aware Messaging Bot for Rental Housing

**Author:** Mark F. Young · **Updated:** 2026-09-24 · **Status:** draft for SME review

This one document combines the original assignment, our analysis of the sample data, the solution design, the actor walkthroughs, the use cases, the decision register and the work plan (GitHub issues). It is generated from the files in `plans/` by `plans/build_solution.py`.

## For the reviewer

**How to read the labels**

| Label | Meaning |
|---|---|
| **ORIGINAL** | Copied word for word from the assignment. This is the graded scope (use cases UC-01 to UC-03). |
| **ANALYSIS** | Our inference from the assignment's data (only 2 sample records). A hypothesis. |
| **ADD-ON (MFY)** | Mark F. Young's extension beyond the assignment. |

**What I'd most like challenged**
1. Does the design respect "learns what to do only from input data"? It is mostly deterministic rules plus an LLM for the wording (D-014, Part 2 §7).
2. Which rules inferred from only 2 samples are overfit (D-002)?
3. Is the add-on scope (D-003 to D-020) at risk of crowding out the graded core?
4. Gaps and risks: security and PII (§9), demo auth (§10), database choice (§5), and legal and competitive exposure (§13).
5. Anything missing from the use cases, actors or data elements.

The same questions drive the independent review in [#9](https://github.com/markfyoung0711/rp/issues/9). Findings will be recorded as new entries in the decision register (Part 5).

**Contents**
1. The original assignment
2. Solution design
3. Actor walkthroughs
4. Use-case traceability
5. Decision register
6. Work plan (GitHub issues)

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
| D-031 | 2026-09-24 | CLI batch processor `run_eval.py --input <jsonl> --output <jsonl>`: stateless, no database, records processed concurrently, per-record latency measured against the 2,000 ms p95, and one bad record never stops the batch. Built first; any UI wraps this same function. | ANALYSIS (Review 2, SME) | recommended | Both reviews converge on it, or it is new from the SME; see `review.md` § Reconciliation | review.md |
| D-032 | 2026-09-24 | The `sample.jsonl` records (input + expected) go into the writer prompt as few-shot examples. This is the "learns only from input data" story. Mock hold-out cases stay out of the prompt. | ANALYSIS (Review 2, SME) | recommended | Both reviews converge on it, or it is new from the SME; see `review.md` § Reconciliation | review.md |
| D-033 | 2026-09-24 | A fixed TCPA keyword gate (STOP, STOPALL, UNSUBSCRIBE, CANCEL, END, QUIT) runs first on any inbound text: no message, no LLM call. Carries out the STOP part of D-027. | ANALYSIS (Review 2, SME) | recommended | Both reviews converge on it, or it is new from the SME; see `review.md` § Reconciliation | review.md |
| D-034 | 2026-09-24 | Protected-class details (familial status, religion, disability, national origin, …) are removed from the profile before the prompt; the output is checked for them; nothing offered changes. A mock hold-out case covers the familial-status trap. | ANALYSIS (Review 2, SME) | recommended | Both reviews converge on it, or it is new from the SME; see `review.md` § Reconciliation | review.md |
| D-035 | 2026-09-24 | A fallback table for unknown or transactional `primary_cta` values (e.g. `sign_lease`, `collect_deposit`): a transactional tone, the opt-out wording kept, and the link taken from the property-facts source or a flagged placeholder, never invented (per D-024). | ANALYSIS (Review 2, SME) | recommended | Both reviews converge on it, or it is new from the SME; see `review.md` § Reconciliation | review.md |
| D-036 | 2026-09-24 | The send hour is set per channel in config (SMS 09:00, email 10:00, from the samples) and stated as an assumption, since the data can't tell a channel effect from a cadence effect. Refines D-023. | ANALYSIS (Review 2, SME) | proposed | Both reviews converge on it, or it is new from the SME; see `review.md` § Reconciliation | review.md |
| D-037 | 2026-09-24 | Build spec for today = the review 2 core blueprint: (1) ingest and validate each record; (2) consent/suppression gate in code (no LLM when no channel has consent); (3) channel = first preferred channel with consent; send time = local(`last_interaction`) + day offset from the task ID/cadence, at the channel's hour, rolled forward a day if not after `last_interaction`; (4) a structured LLM call fills only the text fields, with `sample.jsonl` as few-shot examples; (5) output in the `expected` shape plus `task_id`. Records run concurrently with a per-record try/except. The drop list (database, React UI, real Twilio/SendGrid, reviews, inbound webhooks) is deferred. | ANALYSIS (Review 2, SME) | superseded by D-038 | The two reviews converge on it; the send-time roll-forward is our correction so that `day0` reproduces | review.md |
| D-038 | 2026-09-24 | **Merged core build spec** (review 1 + review 2 addenda; see `review.md` § Merged core build spec). A template baseline that always works; an optional `--llm` mode (samples as few-shot examples, free-text part only, temperature 0 plus a cache); opt-out and CTA in fixed code; review 1's send-time, `next_action`, guard and property-facts rules; JSONL, JSON array or pretty-printed input; a combined output file plus a readable per-record view; deterministic re-runs. Voice is skipped. Supersedes D-037 as the build spec. | ANALYSIS (Reviews 1 + 2) | recommended | Keeps the demo safe without the LLM, and uses the LLM to answer "learns from input data" | review.md |


---

# Part 6 — Work plan (GitHub issues)

| # | Title | Labels | State |
|---|---|---|---|
| [#1](https://github.com/markfyoung0711/rp/issues/1) | a) Intake plan: collect assignment inputs | documentation | open |
| [#2](https://github.com/markfyoung0711/rp/issues/2) | b) Understand plan: decisions, fields, implied rules | documentation | open |
| [#3](https://github.com/markfyoung0711/rp/issues/3) | c) Prior-art search + competitive intel: RealPage/peers — legal risk, practices to avoid, renter/customer pain points | documentation, priority: first | open |
| [#4](https://github.com/markfyoung0711/rp/issues/4) | d) Define detailed spec (schemas, rules, scoring) | documentation | open |
| [#5](https://github.com/markfyoung0711/rp/issues/5) | e) Imagine adjacent agents; add-on tests tracked vs original requirements | enhancement | open |
| [#6](https://github.com/markfyoung0711/rp/issues/6) | f) Design session with engineer: alternatives to co-implement and compare | question | open |
| [#7](https://github.com/markfyoung0711/rp/issues/7) | g) UX design: renter, customer support, and customer (owner) views — cooperating and visible simultaneously for demo | enhancement | open |
| [#8](https://github.com/markfyoung0711/rp/issues/8) | h) Demo data: seed sample actors + create new actors live during the demo | enhancement | open |
| [#9](https://github.com/markfyoung0711/rp/issues/9) | i) FIRST: independent critical review of the spec + prior-art research | documentation, priority: first | open |
| [#10](https://github.com/markfyoung0711/rp/issues/10) | j) External review sentiment: pull Yelp/Google/other review-site data per property via API | enhancement | open |

**Order:** [#9](https://github.com/markfyoung0711/rp/issues/9) and [#3](https://github.com/markfyoung0711/rp/issues/3) first (review and prior art) → [#1](https://github.com/markfyoung0711/rp/issues/1), [#2](https://github.com/markfyoung0711/rp/issues/2) → [#4](https://github.com/markfyoung0711/rp/issues/4) → [#5](https://github.com/markfyoung0711/rp/issues/5), [#7](https://github.com/markfyoung0711/rp/issues/7), [#8](https://github.com/markfyoung0711/rp/issues/8), [#10](https://github.com/markfyoung0711/rp/issues/10) → [#6](https://github.com/markfyoung0711/rp/issues/6).


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

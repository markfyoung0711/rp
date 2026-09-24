# Design

> **ADD-ON — Mark F. Young (author).** The graded scope is only the original assignment ([`spec.md`](spec.md) § Problem Statement and [`sample.jsonl`](sample.jsonl)), which covers use cases UC-01 to UC-03. Everything else in this document is an extension. Each design choice is logged in [`decisions.md`](decisions.md). Detail lives in [`use-cases.md`](use-cases.md) and [`actors.md`](actors.md); this document brings it together.

**Status:** draft for independent review (#9) before the detailed spec (#4) is locked. Issue map: intake #1 · understanding #2 · prior art, competitive intel and UX prior art #3 · spec #4 · add-on agents and tests #5 · alternatives #6 · UX #7 · demo data #8 · independent review #9 · external reviews #10.

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
- **external reputation:** public review-site sentiment (Yelp, Google, …) per property, shown next to internal sentiment (#10)

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
| **EvalRun / EvalResult** | implementation variant, case ID (REQ or ADD), per-field scores, pass/fail | Side-by-side comparison of alternatives (#6) |

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

| **Demo control** | Presenter | Seed/reset, create an actor live with a "generate realistic person" helper, scenario player, implementation switch (#8) |

Common to all: dark/light theme, language picker (remembered; default en-US), accessible forms, and no data outside the viewer's role.

The UX builds on patterns from the UX prior-art study (#3): support consoles such as Zendesk, Intercom and Front; resident apps; owner dashboards; and decision-trace views. Each pattern is marked adopt, adapt or avoid.

### Demo layout

The screen splits into three live panes: **Owner | Support | Renter (phone + inbox)**. Each pane is signed in as a different demo user, and all three read the same event stream over SSE. An action in one pane shows up in the others within about a second. Across the bottom:

- **Scenario player:** loads `sample.jsonl` and the add-on cases and steps through them, including edge cases (no consent, quiet hours, STOP, angry complaint, injection attempt)
- **Trace strip:** for the selected event, shows the bot's path: gates → decision → content → guards → schedule, with the model, latency and cost
- **Implementation switch:** runs the same case through the alternative implementations in #6 and shows the results side by side

### Demo flow

1. Owner approves quiet hours and the welcome cadence (UC-30).
2. The player loads `prospect_welcome_day0`. The bot sends an SMS for 09:00 local time, and it appears on the phone pane (UC-01 to UC-03). Support sees the trace (UC-20).
3. Renter taps "1" → tour booked → confirmation. The owner's dashboard counter goes up (UC-10, UC-31).
4. Renter sends an angry maintenance message. Sentiment drops, the conversation jumps up the support queue, and the bot acknowledges and pauses (UC-12, UC-14). Support takes over (UC-21).
5. Renter tries a prompt injection or asks for another resident's data → refused, and the guard shows in the trace (UC-41, UC-42).
6. Renter replies STOP → consent revoked, pending sends cancelled (UC-11).
7. Presenter creates a new renter live (lead form or inbound SMS). They appear in all three panes and are run through the player (#8).
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
  The alternative readings (templates only, a full LLM agent, rules learned by a model) are in #6.
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

The handlers are the "adjacent agents" from #5:
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
- **Terms stored for each provider:** each adapter declares what may be stored, for how long, and how it must be displayed. For example, Yelp's API returns only a few review excerpts, and both Yelp and Google limit caching and require attribution. Verify these in #3. Reviews past `expires_at` are purged, and only our derived scores and themes are kept, where the terms allow that.
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

It reports the pass rate against the `thresholds` block, plus p95 latency and cost. Results are stored in EvalRun/EvalResult and shown side by side (#6).

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
  - FTC rule on fake reviews: no fake, incentivized or suppressed reviews (#10)
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
- Which alternatives from #6 do we build, and who builds each?
- Which review sites are in scope, and through which licensed API or aggregator? Is an aggregator worth the cost compared with direct Yelp and Google integration? (#10)
- What will the independent review (#9) overturn? Record the answers in `decisions.md`.

## 13. Competitive and legal guardrails

These come from the competitive-intel work in #3 (D-017). The findings are still to be checked against sources.

| Industry risk | Our design stance |
|---|---|
| Algorithmic rent pricing / antitrust (the cases against RealPage and landlords) | The bot never sets, recommends or discusses rent pricing, and never uses pooled or nonpublic competitor data. Pricing is out of scope. |
| Tenant-screening accuracy and disparate impact | No screening. Protected traits and stand-ins for them are never used in targeting, tone or sentiment use (UC-40). |
| Junk fees, dark patterns | Fees shown transparently, billing disputes handled (UC-13); no fake urgency, no auto-renewal traps, opt-out never buried. |
| TCPA / CAN-SPAM suits | Consent per channel, quiet hours, STOP, re-check at send time (UC-11, UC-43). |
| Fake or suppressed reviews (FTC) | Review replies need human approval; we never solicit or suppress reviews (UC-50). |
| Data breaches, privacy suits | §9 controls; synthetic data only in the demo. |
| AI transparency / "can't reach a human" | The bot says it is a bot, and a human is always reachable (UC-14, UC-21). |

The pain points from #3 (renter: maintenance delays, unresponsive management, repeating themselves, fee surprises; owner: slow lead response, leads slipping through, no view of sentiment) map onto the use cases in §3. The full pain point → solution table lives in `plans/prior-art.md`.

## 14. Demo data and seeding

(#8)

- **Baseline seed:**
  - one command, safe to re-run (`make seed` / `POST /demo/seed`)
  - creates organizations, properties, policy, staff, support agents and renters, including the people in `sample.jsonl` and the edge-case people from #5
  - also demo login users (§10), sandbox review sources with synthetic reviews, and optional history so the dashboards aren't empty
- **Live creation:** new actors are created through the real onboarding and lead APIs, not a back door. A "generate realistic person" helper fills the form.
- **Origin tag** on every record (`seed`, `demo_created`, `jsonl_import`, `sandbox_review`). A reset either restores the baseline or clears only what was created during the demo, without a restart.
- **Synthetic only:** `*.example` domains, 555 numbers, no real PII (D-016).

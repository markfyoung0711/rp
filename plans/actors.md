# How the System Works, Actor by Actor

> **ADD-ON — Mark F. Young (author).** This is not part of the original assignment ([`spec.md`](spec.md)). It extends [`use-cases.md`](use-cases.md) and is recorded as D-008 to D-012 and D-018 in [`decisions.md`](decisions.md).

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
- **public reputation:** Yelp, Google and other review-site ratings, sentiment and themes for each property, shown *next to* internal sentiment (never blended). Drafted replies to reviews wait for the owner's approval (#10).

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

**External reviews** (#10) go through the same scorer. They are pulled per property from licensed review-site APIs and kept as their own source, never mixed with renter sentiment. We never try to work out which renter wrote a public review.

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

## UX surfaces

- **Login and account screens:**
  - owner/staff sign-up
  - support sign-in (with a second factor)
  - renter account claim (magic link or SMS code)
  - profile and contact-point editing
  - consent management
- **Owner app:** organization, properties, staff, brand/policy editor, dashboard, reports
- **Support console:** queue, interaction timeline, decision trace, compose/approve/take-over, click-to-call, log off-system contact
- **Renter:** mostly *their own phone* (SMS thread, calls) and *their own inbox*, plus a light, mobile-first portal. In the demo this shows as a phone mock-up pane with an inbox view.
- **Demo layout:** the owner, support and renter panes side by side, updating live from the same event stream (#7)

---

## What this means for persistence

A first cut of the persisted entities, each with create/read/update APIs. Deletes are soft deletes; records are marked retired rather than removed.

| Entity | Key fields | Notes |
|---|---|---|
| Organization | name, brand, billing contact, sending domain | The customer |
| Property | org, name, address, timezone, SMS number, tracking number | |
| Unit | property, label, floor plan | |
| User | login identity, role (owner, staff, support, renter, admin), second-factor settings | Links to a Person for renters |
| Person | name, preferred language, profile attributes | Exists before any login |
| ContactPoint | person, type (email/phone), value, verified | One person, many contact points |
| Consent | contact point, channel, status, when, how, wording | Versioned; revocation is a new record |
| ChannelPreference | person, ordered channels, quiet hours | |
| Relationship (Lead / Lease) | person, property/unit, stage, move date, lease dates | `lifecycle_stage` in the samples |
| Policy | org, version, quiet hours, cadences, brand style, review-required flag | Versioned; decisions record the version they used |
| Cadence / Template | org, name, steps, channel variants | e.g. `prospect_welcome_short_horizon` |
| Interaction | parties, property, topic, status (open, waiting, escalated, closed), assignee, current sentiment and trend | The conversation or case |
| InteractionEvent | interaction, actor, channel, direction, source, payload, timestamps | Append-only |
| SentimentScore | event or external review, polarity, label, emotion/intensity, topic, signals, confidence, model/version, human correction | One per scored event; corrections are new records |
| SentimentRollup | scope (interaction, person, property, org), source (internal/external), window, current score, trend | Recomputed from the scores; drives queue priority and dashboards |
| ReviewSource | property, provider, external ID, credential ref, sync schedule, terms profile | #10 |
| ExternalReview | source, provider review ID, rating, text/excerpt, posted_at, expires_at | Stored only as the provider's terms allow |
| Decision | interaction, inputs snapshot, output (send/suppress, channel, send time, content), reasons, guard results, model, policy version | The bot's trace |
| ScheduledSend | decision, send time, status | Consent and quiet hours re-checked when it fires |
| Ticket | interaction, type (maintenance, billing dispute, complaint), status | |
| Attachment | owner entity, file, type, scan result | Uploads such as disputed bills and maintenance photos |
| AuditLog | who, what, before/after, when | Every create or update above |

**API pattern:**
- `POST /orgs`, `PATCH /orgs/{id}`, `POST /properties`, `POST /persons`, `POST /persons/{id}/contact-points`, `POST /contact-points/{id}/consents`, `POST /interactions/{id}/events`, and so on for each entity
- action endpoints: `POST /interactions/{id}/takeover`, `POST /decisions/{id}/approve`
- provider webhooks: `/webhooks/sms`, `/webhooks/email`, `/webhooks/voice`

Every write checks the caller's role and scope (which organization and property) and appends to the audit log.

## Open questions

- Score sentiment on every inbound event with a cheap model (e.g. Haiku), or only when a cheap first pass flags it?
- Which sentiment thresholds trigger escalation, and does the owner configure them in their policy?

- Does a renter who leases at two properties belonging to two different owners have one Person record or two? This affects privacy between owners.
- Do we record calls, or only log metadata? Consent rules for recording vary by state.
- How strict does the manual off-system log need to be (free text vs. structured outcome) for owner reporting to be trustworthy?

# Field Guide: What Every Field in the Records Means

> Plain English, using sample 1 (Taylor, Oak Ridge) as the running example. For each field: what it is, what it means in leasing terms, and what the bot does with it.

## The big picture

Each line of the JSONL file is **one person at one moment**: a lead or resident the property might contact next. A record has three parts:

| Part | What it is | Example |
|---|---|---|
| **Input** | Who the person is, what they allow, and their situation | Taylor, a new prospect, opted in to SMS and email, moving mid-January |
| **Rules to follow** | Conditions the message must meet | Include opt-out wording, don't leak personal data, pass fair housing |
| **Expected** (the answer key) | What the right next message would be | An SMS at 9:00 the next morning offering Thursday or Friday tours |

The bot reads the first two parts and produces its own version of the third. The hold-out records may not include the answer key.

---

## 1. Identity and situation

| Field | Example | Plain meaning | What the bot does with it |
|---|---|---|---|
| `task_id` | `prospect_welcome_day0` | A label for this test case: the scenario (a prospect welcome), plus **day0**, meaning the step of the sequence (day 0 = the first message) | Echoes it in the output so results can be matched to inputs. Reads the **dayN** to set the send day. |
| `persona` | `prospect` | **Who** the person is to the property. A *prospect* is someone thinking of renting; a *resident* already lives there; an *applicant* has applied | Chooses the kind of message: a prospect gets a tour invitation, a resident a rent or renewal reminder |
| `lifecycle_stage` | `new` | **Where** they are in the process. *new* = just became a lead; *open* = an active lead who's been contacted before | A new lead starts a welcome sequence; anyone else gets a follow-up |

## 2. Permission and preferences

| Field | Example | Plain meaning | What the bot does with it |
|---|---|---|---|
| `consent.sms_opt_in` | `true` | Did they agree to receive **texts**? | Never texts without it (the law requires consent) |
| `consent.email_opt_in` | `true` | Did they agree to receive **emails**? | Never emails without it |
| `consent.voice_opt_in` | `false` | Did they agree to **phone calls**? | Never calls without it. With consent and voice preferred, the bot writes an automated **call script** with keypad options ("press 1 for Thursday") and a spoken opt-out ("press 9 or say stop") |
| `channel_preferences` | `["sms", "email"]` | The order they'd like to hear from you: here, text first, then email | Takes the **first channel in this list that has consent** |

## 3. The situation (`input`)

| Field | Example | Plain meaning | What the bot does with it |
|---|---|---|---|
| `property_name` | `Oak Ridge Apartments` | The apartment community they're interested in | Looks up its details (short name, tour days, links, brand) in `config/properties.yaml` |
| `move_date_target` | `2026-01-10` | When they want to move in | Measures **days to move-in**: under 50 → a short sequence, over → a long one. Emails mention it ("mid-January move") |
| `last_interaction` | `2025-12-08T15:04:00Z` | When they last got in touch, in UTC (the "Z") | The starting point for the send time |
| `timezone` | `America/Chicago` | Their local time zone | Converts times so messages go out at 9 or 10 a.m. **their** time |
| `language` | `en` | Their language (a locale like `es-MX` counts as `es`) | Picks the message templates in `config/templates/<lang>.yaml` (English, Spanish and French today), if the property offers that language; otherwise the property's `default_language`, with a note. Spanish opt-out replies (ALTO, BAJA, PARAR, CANCELAR, NO MÁS) stop messages, and Spanish fair-housing terms and banned sales phrases are checked too |
| `profile.first_name` | `Taylor` | Their first name | Used in the greeting ("Hi Taylor"). The only personal detail that goes in a message |
| `profile.amenity_interest` | `["pool", "fitness"]` | Features they asked about | Mentioned in the email ("our pool and 24/7 fitness center") |
| `profile.city_interest` | `Richardson, TX` | The area they're looking in | Not used in the message |

## 4. Rules the message must follow (`assertions`)

| Field | Example | Plain meaning | What the bot does with it |
|---|---|---|---|
| `required_states` | `consent_verified`, `fair_housing_check_passed`, `brand_style_applied` | Three checks that must have passed before sending | Checks all three and reports them on every message |
| `constraints.no_pii_leak` | `true` | Don't reveal personal data | Only the first name ever appears; tested with planted data |
| `constraints.no_sensitive_discrimination` | `true` | Don't treat people differently by protected traits (fair housing) | Protected details are never used or mentioned |
| `constraints.include_opt_out_instructions` | `true` | Tell them how to stop messages | Always adds "Reply STOP to opt out." (fixed text, never AI-written) |
| `constraints.primary_cta` | `book_tour` | **The main thing you want them to do** (see CTA below) | Chooses the call to action |

## 5. Targets (`thresholds`)

| Field | Example | Plain meaning | Status |
|---|---|---|---|
| `p95_latency_ms` | `2000` | 95% of records must be processed within 2 seconds | Checked in RUN STATS: about 1 ms per record (p95 ≈ 10 ms on the samples, while it warms up) |
| `safety_violations_max` | `0` | No unsafe messages allowed | Checked: 0 |
| `personalization_score_min` | `0.85` | How personal the message must be, scored 0–1 | Not measured: the assignment doesn't say how to score it |
| `reply_classification_f1_min` | `0.9` | Accuracy when sorting replies (for example, "1" means Thursday) | Not measured: there are no replies in the data |

## 6. The answer key (`expected`), which is also the bot's output

| Field | Example | Plain meaning |
|---|---|---|
| `next_message.channel` | `sms` | How to reach them |
| `next_message.send_at` | `2025-12-09T09:00:00-06:00` | When to send: 9:00 on Dec 9, Chicago time. The `-06:00` is Chicago's offset from UTC in winter |
| `next_message.subject` | `null` | The email subject line. Texts have none, so it's `null` |
| `next_message.body` | "Hi Taylor—welcome to Oak Ridge! …" | The message itself |
| `next_message.cta` | `{"type": "schedule_tour", "options": ["Thu", "Fri"]}` | **The call to action** (see below) |
| `next_action` | `{"type": "start_cadence", "name": "prospect_welcome_short_horizon"}` | What happens **after** this message (see below) |

If the bot decides not to send, `next_message` is `null` and `next_action` says why, e.g. `{"type": "suppress", "reason": "no channel with consent"}`.

---

## Terms that come up

**CTA (call to action):** the one thing the message asks the person to do. In marketing, every message should have one clear CTA.
- `primary_cta: book_tour` in the input says what we *want*: a tour booked.
- `cta` in the output says *how the message asks for it*:
  - **SMS:** `{"type": "schedule_tour", "options": ["Thu", "Fri"]}`, with reply options ("Reply 1 for Thu, 2 for Fri").
  - **Email:** `{"type": "schedule_tour", "link": "https://oakridge.example/tour"}`, with a link to click.
- Other CTAs the bot knows: apply now, sign lease, pay rent, pay deposit, renew lease, schedule maintenance. Anything unknown becomes a general "contact us".

**Cadence:** a planned **series of messages** over time, like a drip campaign. `start_cadence` means "begin the series named …".
- `prospect_welcome_short_horizon` is the welcome series for someone moving **soon** (short horizon: about 32 days away in the sample).
- `…_long_horizon` is for someone moving **later** (e.g. 68 days away), so the series paces out more slowly.
- **Horizon** is simply how far away the move-in is.

**Follow-up:** `{"type": "follow_up_in_days", "value": 3}` means "check back with this person in 3 days". It's used for leads already in progress (`open`).

**Opt-out:** how someone stops messages. By law, texts must offer "Reply STOP", and marketing emails must include an unsubscribe option.

**Lead:** a potential renter who has shown interest. A **prospect** is a lead.

**UTC and offsets:** `Z` means UTC (the world reference clock). `-06:00` means 6 hours behind UTC (Chicago in winter), and `-05:00` means Chicago in summer or New York in winter.

**Persona vs stage:** persona is *who* they are (prospect, resident); stage is *where* they are (new, open, renewal).

---

## Fields the bot adds to its output

| Field | Meaning |
|---|---|
| `task_id` | Copied from the input, so each result can be matched to its record |
| `why` | One plain line per decision: consent, channel, send-time arithmetic, wording, guards, brand, next action |
| `meta.record_type` | `outreach` (the normal shape), `unknown` (an unfamiliar shape) or `unreadable` |
| `meta.confidence` | `high`, `medium` (something was assumed or repaired) or `low` (unfamiliar record shape) |
| `meta.mode` | `template` or `llm`: who wrote the wording |
| `meta.required_states` | The three required checks, each `true` when verified |
| `meta.warnings` | Anything repaired, assumed or ignored in the input |
| `meta.gaps` | Machine-readable configuration gaps, only when present. For example `{"code": "property_facts_missing", "property": "Maple Court"}`: the property has no facts file, so the message is generic and uses the default brand. RUN STATS lists them under **Config gaps** |

**For the hold-out hand-over,** `--answer-only` leaves out `why` and `meta`. Each line is then exactly the samples' `expected` shape: `task_id`, `next_message`, `next_action`. The reasons still show on screen.


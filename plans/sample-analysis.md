# Sample Data Analysis

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

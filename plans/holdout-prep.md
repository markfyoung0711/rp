# Hold-Out Set Preparation

> **ANALYSIS — ours.** The requirement comes from the interviewer (D-021): *"Be prepared to “export” or “copy-paste” the 12 outputs from a hold-out set that is provided during the interview."*

## What a hold-out set is

A surprise batch of test cases, kept hidden until the interview, used to check whether the system actually learned the task or just memorized the examples. The term comes from machine learning, where a hold-out set is data the model never sees during training and is used only for the final evaluation.

It tests:
- **Flexibility:** is the design modular, or brittle?
- **Edge cases:** does it fail gracefully, or adapt, when inputs are unexpected?
- **Assumptions:** were our guesses about the vague parts of the spec sensible, and do they generalize?
- **Us:** how we react live when something doesn't fit.

It can take several forms: new test data (possibly malformed), a feature change ("what if the client wants Y?"), or scale ("what about 100,000 records?").

## What we expect here

Most likely **12 new JSONL records in the same shape as `sample.jsonl`**, but without the `expected` block, or with it hidden. We run all 12 and produce 12 outputs to export or paste, and they compare them with their expected answers.

## Variations the hold-out probably includes

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

## Constraints in the data that matter

- `thresholds.p95_latency_ms: 2000`: 95% of records need an answer within 2 seconds. Keep the rules deterministic, use a fast model for writing (e.g. Haiku 4.5), or run the 12 in parallel. Measure it.
- `safety_violations_max: 0`: guards on every output (opt-out present, no PII leak, fair housing).
- `personalization_score_min`: use the profile fields (name, interests, move date) in the body.

## Checklist before the interview

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

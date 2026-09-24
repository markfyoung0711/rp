# Critical Reviews

- **Review 1 of 2:** Claude Sonnet 5 (independent session), 2026-09-24, below.
- **Review 2 of 2:** SME review by **Gemini (Google AI Mode)**, 2026-09-24, [at the end](#review-2-of-2--sme-review), followed by our reconciliation of the two reviews.

---

# Review 1 of 2

## SME Review: Context-Aware Messaging Bot for Rental Housing

**Documents reviewed:** `spec.md` (the assignment) and `solution.md` (solution proposal by Mark F. Young, updated 2026-09-24)
**Review date:** 2026-09-24
**Revision:** 2. Section 2 now covers the broader meaning of a hold-out set (live surprises as well as the 12-record batch). Sections 1, 6, and 8 were adjusted to match.
**Lens:** business and systems analysis for residential and multifamily leasing, in a RealPage context
**Purpose:** the independent critical review requested in issue #9, before the detailed spec (#4) is locked

---

## 0. How this review was done, and its limits

- **Order of work:** I read the assignment first and formed my own view of its gaps, then read the solution, as #9 asks.
- **Sample data:** only the two records printed inside `spec.md` were available. A separate `sample.jsonl` was not provided. I assume it matches.
- **No code was run.** Nothing here was tested against any hidden set.
- **RealPage context:** product observations come from the public OneSite page (marketing content, not technical documentation). Vendor figures on that page are not treated as facts.
- **Legal points** are flagged for verification. This is not legal advice, and several rules in this space have changed recently.
- **Severity scale:** *Blocker* means the delivery is likely to fail or mislead without a fix. *Major* means a significant risk or gap. *Minor* means worth fixing, not urgent.

---

## 1. Executive summary

The solution's layering is sound: deterministic gates, an LLM only for wording, authorization enforced inside tools, and consent re-checked at send time. The problems are in priorities and in fit with the graded core.

1. **The core can't reproduce the samples as specified.** The send-time rule fails on sample 2, and the expected messages contain facts (tour availability, amenities, a URL) that have no source in the input or the data model.
2. **The add-on scope dwarfs the graded scope.** Three graded use cases get roughly one pipeline diagram. Seventeen add-on use cases get schemas, APIs, security, and deployment.
3. **The evaluation is circular.** The two samples are the few-shot examples, the source of the rules, and the test set. A pass would prove nothing about a hidden set.
4. **The platform rebuilds products RealPage already sells** (CRM, leasing agent, resident portal, maintenance, reputation management) with no integration or system-of-record story.
5. **The delivery constraint changes what matters.** A working demo is due today at 12:00 noon CST, and 12 outputs from an unseen hold-out set must be exported at the interview. Accuracy on unseen records and never crashing matter far more than the platform. Expect live "what if" follow-up questions as well (section 2).

---

## 2. What is a "hold-out set", and what it means here

### Definition
A **hold-out set** is a group of test cases deliberately kept away from whoever builds the system. It is used once, at the end, to measure how well the system handles cases it has never seen. The term comes from machine-learning practice, where part of the data is "held out" so you can't tune the system to it. The point is to tell real generalization from memorized answers.

| Term | Meaning | In this assignment |
|---|---|---|
| Training or development data | What you build and tune against | The two records in `sample.jsonl` |
| Hold-out (test) set | Unseen cases used for the final measurement | The 12 cases provided during the interview |

### What the delivery note says, and a broader reading
The note says to "be prepared to export or copy-paste the 12 outputs from a hold-out set that is provided during the interview." There are two ways to read this, and you should prepare for both.

1. **The stated reading (primary):** at the interview you receive 12 new input records, probably in the same shape as the samples. You run your system on them and hand over the 12 outputs, by export or copy-paste, live. You cannot see or tune to those records beforehand.
2. **The broader interview practice (likely, but not stated in your note):** interviewers often use a hold-out as a live stress test of a system built from a vague spec. Because the spec was nebulous, they want to see whether your design choices survive real-world variation, or whether you hardcoded a solution to the few examples you were given. In this view they treat your system the way a data scientist treats a model, and they also watch how you react under pressure when something unexpected happens.

The second reading comes from general interview practice, not from anything in your assignment. Treat the 12-record batch as the main event and live follow-up questions as a probable addition.

### What is still unknown (ask the interviewer)
- Do the 12 records include an `expected` block, so outputs are scored automatically, or only inputs, so a person judges them?
- Do they cover the same persona and stage (prospect, new/open) or others (resident, applicant, renewal)?
- Do they include no-send cases, voice, or non-English records? The samples show none of these, and the assignment says a message might be "not sent."
- What format do they want for the export?
- Will there be live "what if the client wants Y?" changes or questions after the batch?

### Forms it can take, and how this design responds

| Form | Example in this assignment | What protects you | Related findings |
|---|---|---|---|
| New unseen records | 12 records you have never seen | Rules that generalize, not rules fitted to two samples | F-03, F-15 |
| Corrupt or null input | Missing fields, null consent, unknown time zone, an odd or hostile `first_name`, malformed JSON | Safe fallback: a no-send with a recorded reason, never a crash | F-03, F-09 |
| Domain edge cases | No consent, opted out, voice-only, quiet-hours edge, non-English, resident persona | The decisions table in section 6, settled in advance | F-06, F-07, F-15 |
| Feature pivot | "Add voice," "change quiet hours," "add Spanish," "add a renewal cadence" | Know where each rule lives; a core separate from the platform makes each change local | F-03, F-04 |
| Scale escalation | "Run 100,000 records now" | Records are decided independently, so the work parallelizes. The real limits are the latency budget, model cost and rate limits, and avoiding duplicate sends | F-08, F-14 |
| Assumption challenge | "Why 9:00? Why Thu/Fri? Why that channel?" | State your assumptions before you are asked (below) | F-01, F-02, F-15 |

### What it exposes about your system
- **Flexibility:** whether the rules are modular or tightly coupled and brittle.
- **Failure behavior:** how gracefully the system handles unexpected input.
- **Your reasoning under pressure:** how you respond to an unmapped case you did not anticipate.
- **Assumption quality:** whether the guesses you made to fill the spec's gaps were logical and defensible.

### What follows from this
- **Generalization beats fit.** Two samples cannot define the behavior of a system that must handle 12 unseen cases. Rules written only to reproduce the samples are fragile.
- **Robustness is graded implicitly.** A crash, a blank output, or a hallucinated fact on one of 12 cases is very visible.
- **Reproducibility matters.** Running the same record twice should give the same output, or you can't explain the export.
- **Your own testing must simulate a hold-out.** Write extra cases (no consent, voice-only, opted out, different persona, non-English, missing fields, odd names) and treat them as unseen. Do not tune your rules to the two samples alone.

### Assumptions to state aloud before you are asked
Naming these yourself shows the gaps were seen and handled on purpose.
1. **Send time:** how the date and hour are chosen, and that `now` is an explicit input (F-01).
2. **Property facts:** where amenities, tour slots, and the tour link come from, and what happens when they are missing (F-02).
3. **Cadence horizon:** short vs long is derived from days to move-in, with a threshold you chose (F-15).
4. **No-send output:** the shape you chose, since the assignment defines none (S-4).
5. **AI disclosure:** handled as a policy flag, and why it is off in graded output (F-16).
6. **Consent:** the samples give three booleans, and richer consent semantics are designed but not built (F-06).
7. **Voice:** modeled in the data, deferred in behavior.
8. **Sample-derived rules are hypotheses,** tested against extra cases you wrote, not proven.

### A short way to describe what you built
Adapt this to what is actually running, and do not claim anything that is not.

> "It is a decision agent for outbound leasing messages. Deterministic rules decide whether to send, which channel, and when. The wording comes from templates, with an optional model-written sentence. The opt-out text and call to action are composed by fixed logic, not generated. The rules were inferred from two samples, so I have marked them as assumptions and tested them against extra cases I wrote myself."

---

## 3. Review of the assignment (`spec.md`)

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

## 4. Review of the solution (`solution.md`)

### 4.1 Blockers

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
- The alternatives comparison (#6), your answer to "learns only from input data," is last in the work plan.
- *Change:* define the core as a self-contained decision step (record in, decision out) with no database. Build a held-out set of 20 to 30 varied cases, including no-send cases, kept out of prompts. Move #6 to the front.

**F-04. The add-on scope crowds out the core.**
- *Evidence:* voice, external review ingestion (#10), sentiment rollups, row-level security with crypto-shredding, and the three-pane UI carry no graded value and most of the legal risk.
- *Change:* gate all add-ons on the core passing held-out cases. Cut #10 and voice dialing. Keep one thin slice (UC-10 reply handling plus STOP), which demonstrates compliance well.

**F-05. Overlap with RealPage's catalogue, and no system-of-record answer.**
- *Evidence:* RealPage's own catalogue lists Knock CRM, an AI Leasing Agent, Online Leasing, the LOFT resident portal, Facilities Management with an AI Facilities Agent, Reputation Management, Lumina agents, and RPX as the integration marketplace.
- The design re-creates Person, Lease, Ticket, tour booking, a resident portal, and review reputation, and defers integrations to "later."
- *Change:* state who owns the resident, lease, and consent records. Position the bot as a decision service fed through integrations. Treat Person, Consent, and Relationship as synced read models. Demote Ticket, Attachment, and reviews to adapters, or cut them.

### 4.2 Major

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

### 4.3 Minor

- D-017 is marked accepted while its findings are unverified, and #9 refers to "D-003 to D-017" though the register runs to D-020.
- Suppress and needs-review outcomes have no defined output schema.
- The sample file has no trailing newline (`wc -l` reports 1), so use a proper JSONL reader.
- LISTEN/NOTIFY breaks behind transaction poolers, and payloads are capped at about 8 KB.
- CAN-SPAM requires a postal address, which the Organization entity lacks.
- Add explicit non-goals: screening, pricing, collections, and legal notices, which have required delivery methods that SMS does not satisfy.

---

## 5. What is solid

- Deterministic rules where the samples show a rule, LLM only for language. This is testable and auditable.
- Authorization enforced inside tools, not in the prompt, so an injection cannot reach other data.
- Consent and quiet hours re-checked when a send fires, not just at scheduling.
- Append-only consent history and a decision trace with the policy version.
- Explicit exclusion of rent pricing and screening, and an origin tag on every record.
- The document's own labeling (ORIGINAL / ANALYSIS / ADD-ON) keeps graded scope visible.

---

## 6. Recommended priorities for today's delivery

These are recommendations for the author, not implementation.

### Must work
1. A self-contained decision step that reads a JSONL file and produces one output per record, and never crashes. Accept JSONL, a JSON array, or pretty-printed objects. A malformed record yields a safe suppress with an error reason.
2. A defined send-time rule (F-01) with `now` as an explicit input, stated as an assumption.
3. Deterministic composition of opt-out wording and CTA (F-09), with the LLM optional and a guaranteed non-LLM fallback.
4. A single, visible source for property facts (F-02). Decide what to do for a property with no facts.
5. Constraint handling driven by the record itself (`primary_cta`, opt-out, no PII leak) rather than hardcoded to Oak Ridge.

### Cut from the demo and label "designed, not built"
Database, authentication, row-level security, the three-pane UI, sentiment, external reviews, voice, and findings F-05 through F-13. The document becomes a roadmap and design rationale, which is its real value here.

### Decisions to settle before the hold-out set arrives

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

### Demo-day checklist
- Diff every field of both samples before presenting.
- Write 8 to 10 extra test cases of your own and treat them as unseen: no consent, SMS-only, voice-only, opted out, quiet-hours edge, Spanish, resident persona, missing fields, malformed record, odd name.
- Pre-run everything and keep the outputs. Have an offline path in case the network or API key fails.
- Make the export copy-paste friendly: one combined file plus a readable per-record view (channel, send time, subject, body, reason).
- Prepare a one-sentence answer for each likely pivot: add voice, change quiet hours, add Spanish, add a persona, run at scale. Each answer should name the place where that rule lives.
- Rehearse the assumptions in section 2 out loud. Say them before you are asked.
- Put a **"built vs designed"** table at the top of the solution. Interviewers probe claims, and overclaiming costs more than a small scope.

---

## 7. Answers to the author's five questions

1. **Does the design respect "learns only from input data"?** Partly. A hand-written rule set plus a model for wording is a defensible reading, but two samples cannot support any learning, and using the samples for rules, examples, and evaluation at once is circular (F-03). Present it honestly as rules inferred from data, and show the alternatives comparison (#6) earlier.
2. **Which rules are overfit?** The send-time rule (F-01), `next_action` from two data points, and channel choice (F-15). The horizon rule is missing entirely.
3. **Is the add-on scope a risk?** Yes (F-04). Gate it on core performance against held-out cases.
4. **Gaps and risks:** F-06 through F-14 cover PII and security, demo auth, consent, compliance, and metrics. On the database choice: Postgres is a reasonable choice, but it is not needed for the graded core, and the row-level security and encryption details need the fixes in F-13.
5. **Anything missing from use cases, actors, data?** Property facts (F-02), the owner/operator split and multi-party leases (F-12), human-only intents and emergency paths (F-10, F-11), and frequency caps and idempotency (F-08).

---

## 8. Questions to ask the interviewer or spec owner

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

## 9. Proposed decision-register entries

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

## Appendix A: send-time arithmetic

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

## Appendix B: traceability, spec requirement to solution

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


## Review 1 addendum — core functionality focus

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

# Review 2 of 2 — SME review (Gemini, Google AI Mode)

> Pasted verbatim, 2026-09-24.

## 🚨 SME Critical Review & Red Flag Analysis
Mark, you are in immediate danger of failing this interview demo at 12:00 Noon today.
As a property management Subject Matter Expert (SME), I can tell you that your architecture document is incredibly thorough, but your focus is dangerously misplaced for a noon delivery. You have succumbed to extreme scope creep. You are spending critical hours designing complex database schemas, CRM dashboards, multi-tenant RBAC logic, and external Yelp/Google review pipelines.
The interviewer gave you one explicit, unbending directive: "Be prepared to ‘export’ or ‘copy-paste’ the 12 outputs from a hold-out set that is provided during the interview".
If your core script cannot process a raw JSONL file, evaluate the 12 lines within 2 seconds per line, and spit out structurally perfect JSON matching the expected schema, you will fail.. It will not matter that your React front end looks like Zendesk.
------------------------------
## 1. Direct Answers to Your Challenge Questions## 1. "Does the design respect 'learns what to do only from input data'?" [2]
No, but your implementation strategy is still correct. Pure machine learning where the code learns dynamically on the fly from two records is impossible. Your approach—using deterministic python code for execution rules and an LLM for copy generation—is the only way to build a stable system by noon.

* The "Learn Only" Fix: To truly claim your bot "learns from input data," you must feed the existing sample.jsonl file directly into your LLM prompt as Few-Shot Examples. Let the LLM read the input and expected blocks of the samples to "learn" the semantic translation, while your Python wrapper handles strict gates like channel consent.

## 2. "Which rules inferred from only 2 samples are overfit?" [2]

* The Send-Time Rule: Your assumption that "all messages send on 2025-12-09 in the morning" is highly overfit. Look closely at the task_id fields. prospect_welcome_day0 was sent exactly 1 day after the last_interaction (12-08 to 12-09). prospect_long_horizon_day3 was sent exactly 3 days after its last_interaction (12-06 to 12-09). The send_at date is calculated by adding the day offset implied in the lifecycle cadence to the last_interaction timestamp.
* The Morning-Hour Rule: The 09:00 vs 10:00 send times aren't random. Notice that the email target is 10:00 and the SMS is 09:00. This implies property management compliance: texting earlier to grab attention, delaying emails slightly so they don't get lost in a morning inbox sweep.

## 3. "Is the add-on scope at risk of crowding out the graded core?" [2]
Yes, completely. You have designated 13 use cases to "Add-on Scope". None of them matter at 12:00 PM. If you spend time writing an attachment scanner for billing disputes or an integration for Yelp APIs before the 12-line batch processor is bulletproof, you are tanking the demo.
## 4. "Gaps and risks: database choice, legal, security" [2]
For the noon demo, the database choice is irrelevant because you shouldn't use one.. Your pipeline must be stateless: JSONL String In ➡️ Process ➡️ JSONL String Out.
------------------------------
## 2. The Real Estate SME Risk Matrix: The True "Hold-Out" Traps
Your hold-out set table is accurate, but you missed the most lethal real estate specific edge-cases that an industry interviewer will use to break your bot:

| Hold-Out Scenario | The Real Estate SME Operational Risk | What Your Bot Must Do |
|---|---|---|
| The Familial Status Trap | A prospect's profile text says: "Moving with my 4 kids, need a place near a daycare." [2] | Fair Housing Violation (FHA). The LLM must never mention the children, comment on the family size, or limit property options to ground floors or specific blocks ("steering"). It must treat them identically to a solo applicant. |
| The Absolute Silencer (STOP) | Inbound text contains standard TCPA keywords: "STOP", "QUIT", "UNSUBSCRIBE". | Immediate Suppression. Hardcode a regex router at the very front of your script. If these keywords hit, set next_message to null and do not invoke the LLM. Do not risk an LLM ignoring or hallucinating a compliance command. |
| The Over-the-Line CTA | The primary_cta is passed as collect_deposit or sign_lease instead of book_tour. | Fallback Logic. The system must map this to a secure link schema (https://property.example) and change body text from welcoming to transactional, while retaining opt-out copy. |

------------------------------
## 3. Immediate Triage Action Plan (Next 8 Hours)
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

## Review 2 addendum — core functionality blueprint

> Pasted word for word, 2026-09-24.

Yes, I have defined it. To guarantee you pass the interview demo at noon today, core functionality must be stripped of all software engineering platform overhead (databases, UIs, webhooks) and defined strictly as a stateless, CLI-driven batch processing pipeline.
Here is the exact blueprint of the core functionality you must target and lock down over the next few hours to handle the 12 surprise hold-out records:
## 1. The Core Execution Pipeline (Stateless)
Your script must implement this exact 5-step loop for each line in the incoming JSONL file:

* Ingestion: Read a line from the input file and parse it into an internal Python dictionary or Pydantic model.
* Consent & Suppression Gate (Hardcoded Code): If consent flags for all listed channel_preferences are false, immediately short-circuit. Set next_message to null, set next_action to a suppression status, and record the reason. Do not call the LLM for this record to save latency and ensure compliance.
* Channel & Timing Derivation (Hardcoded Code):
* Select the first channel in channel_preferences where consent is true.
   * Parse input.last_interaction and add the day offset implied by the lifecycle_stage or task_id (e.g., day0 = +0 days, day3 = +3 days). Map this to the target local timezone and output a perfectly formatted ISO 8601 string with the correct UTC offset.
* Content Generation (Structured LLM Call): Pass the input profile fields, the chosen channel, the target CTA, and the sample.jsonl data (as few-shot context) to the LLM. Enforce a JSON schema constraint so the LLM only fills out the text fields (subject, body, cta.link/options).
* Output Construction & Aggregation: Package the decisions back into the exact structural shape of the expected block from the spec, ensuring it includes the record's original task_id.

## 2. Performance & Operational Benchmarks

* The 2-Second Timeout: The spec explicitly demands p95_latency_ms: 2000. You cannot process 12 items sequentially if each LLM call takes 1.5 seconds. Core functionality must use Python's asyncio or concurrent.futures to fire all 12 API calls to Anthropic/OpenAI in parallel.
* Fault-Tolerant Loop: If record #4 has a malformed timezone or missing name field, your script must not crash. Core functionality includes wrapping each row's execution in a try/except block, logging the error for row #4, and continuing to generate valid outputs for the remaining 11 rows.
* One-Click Export: You must be able to run a terminal command like python bot.py --input holdout.jsonl --output results.jsonl and have it instantly available to copy-paste or upload.

## 3. Defer Everything Else (The "Drop" List)
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

# Reconciliation of reviews 1 and 2

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

## Merged core build spec (review 1 addendum + review 2 addendum)

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

# Review 2 reference implementation: `bot.py` (Gemini)

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

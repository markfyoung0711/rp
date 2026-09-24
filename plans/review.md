# SME Review: Context-Aware Messaging Bot for Rental Housing

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

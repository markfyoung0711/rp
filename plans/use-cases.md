# Use Cases

> **ADD-ON — Mark F. Young (author).** This goes beyond the original assignment ([`spec.md`](spec.md)). The original asks only for UC-01 to UC-03, run against the JSONL records. Everything else here is my extension. See D-003 in [`decisions.md`](decisions.md).

## Actors

| Actor | Who | Wants |
|---|---|---|
| **Renter / prospect** | Someone leasing, or looking to lease | Useful, well-timed messages; easy tours, requests and answers |
| **Customer support** | The property-management platform's support staff (RealPage-side, or the operator's leasing/service team) | To see what the bot decided and why; step in, correct, escalate |
| **Customer** | The property owner/operator who pays for the platform | Occupancy, resident satisfaction, compliance, and visibility into outreach |
| **Bot** | The message-sending agent | To decide whether to send, the channel, the timing and the content, from the record alone |

## Original scope (from the assignment)

| ID | Use case | Primary actor | Source |
|---|---|---|---|
| UC-01 | Decide whether to contact the recipient (consent, suppression, timing) | Bot → Renter | spec.md |
| UC-02 | Choose the channel and send time (preferences, consent, timezone) | Bot → Renter | spec.md, sample.jsonl |
| UC-03 | Write a personalized, compliant message with a CTA and set the next action | Bot → Renter | spec.md, sample.jsonl |

## Add-on scope (Mark F. Young)

| ID | Use case | Primary actor | Also involved | Issue |
|---|---|---|---|---|
| UC-10 | Prospect replies (e.g. "1" for Thu) → tour booked → confirmation sent | Renter | Bot, Support | #5, #7 |
| UC-11 | Prospect replies STOP → opt-out applied on every channel, confirmation sent | Renter | Bot, Support | #5 |
| UC-12 | Renter submits a maintenance request (optionally with a photo) → work order → status updates | Renter | Bot, Support, Customer | #5 |
| UC-13 | Renter disputes a charge by uploading a bill with the item marked → dispute ticket | Renter | Support, Customer | #5 |
| UC-14 | Renter complains repeatedly or is angry → escalated to a human, with context | Renter | Support | #5 |
| UC-15 | Renewal outreach ahead of lease end → renewal offer or retention hand-off | Bot → Renter | Customer | #5 |
| UC-20 | Support reviews the bot's decisions (with reasons), edits or holds a message before it is sent | Support | Bot | #7 |
| UC-21 | Support takes over a conversation and hands it back to the bot | Support | Renter, Bot | #7 |
| UC-22 | Support handles a platform question from the customer (billing, configuration) | Customer | Support | #3 |
| UC-30 | Customer sets outreach policy (cadence, brand style, quiet hours) and approves templates | Customer | Support, Bot | #7 |
| UC-31 | Customer views a portfolio report (outreach, conversion, escalations, maintenance, complaints) | Customer | — | #5 |
| UC-40 | Guard: a fair-housing or discriminatory request is refused and logged | Bot | Support | #4, #5 |
| UC-41 | Guard: prompt injection in profile or reply text is ignored | Bot | Support | #5 |
| UC-42 | Guard: cross-account or PII request is refused; each role sees only what it is allowed to | Bot | All | #5, #7 |
| UC-43 | Guard: quiet hours / TCPA — the send is delayed to an allowed time | Bot | — | #4 |
| UC-50 | External review sentiment: pull Yelp, Google and other reviews per property, score them, and show them next to internal sentiment; draft replies for a human to approve | Customer | Support, Bot | #10 |

## Demo scenario (all three roles visible at once, #7)

1. **Customer** sets quiet hours and approves the welcome cadence (UC-30).
2. **Bot** processes `prospect_welcome_day0` and sends an SMS at 09:00 local time (UC-01 to UC-03). **Support** sees the decision trace (UC-20).
3. **Renter** replies "1" → the tour is booked (UC-10). **Customer**'s dashboard counts it (UC-31).
4. **Renter** sends an angry maintenance complaint → escalated (UC-12, UC-14). **Support** takes over (UC-21).
5. **Renter** tries prompt injection or asks for another resident's data → refused (UC-41, UC-42). The refusal shows up in the Support trace.

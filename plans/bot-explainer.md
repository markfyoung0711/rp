# What the Bot Is and What It Does

> **ANALYSIS — ours.** A plain-English explanation for Mark, to follow the build's progress and its architecture, and to use in the interview. The build spec is D-038 in [`decisions.md`](decisions.md).

## What a "bot" is

A **bot** is just a program that acts on its own: something comes in, it decides, it produces a response, with no human in between. The word says nothing about *how* it decides. A bot can be:

1. **Rule-based:** plain code with if/else logic. Predictable, and just as capable as the rules you write.
2. **AI-powered:** it asks a language model (an LLM, like Claude) to make the decision or write the text.
3. **A mix:** rules for the decisions that must be right, and AI for the parts that need judgement or natural language. **Ours is a mix.**

**REST analogy:** think of our bot as **one endpoint**. A JSON record goes in, a JSON decision comes out, and nothing is remembered between calls. Inside it, one step happens to call Claude's API, the way a service might call a third-party API.

## Bot vs "AI agent", and how to talk about it

| Term | What it means | Is ours one? |
|---|---|---|
| **LLM / model** | The AI that reads text and writes text (Claude Haiku, Sonnet) | We *use* one |
| **Prompt** | The instructions and data we send to the model | Yes |
| **Few-shot examples** | Worked examples placed in the prompt so the model copies the pattern. Here, the two samples | Yes. This is how it "learns from input data" |
| **Workflow / pipeline** | Fixed steps in a fixed order, which *we* chose; the AI is one step | **Yes, this is what we're building** |
| **Agent** | The AI chooses its own next step in a loop ("look something up, then decide, then look up more…") using tools we give it | No, deliberately not |
| **Guardrails** | Code checks that stop bad output: missing opt-out, leaked phone number, fair-housing words | Yes |
| **Deterministic** | The same input always gives the same output | Yes, for every decision |

**How to say it in the interview:**

> "It's an autonomous decision pipeline. It decides on its own with no human in the loop, but the compliance-critical decisions (consent, channel, timing, opt-out) are deterministic code. The model only writes the wording, guided by the samples as few-shot examples. I chose that over a free-roaming agent because consent and fair-housing rules have to be guaranteed, not just probable."

The assignment says "autonomous agent". That's a likely gotcha, and the answer above handles it. *Autonomous* means no human needs to approve each message. It doesn't require the AI to be in charge of everything.

## What our bot does, step by step

Using sample 1 (Taylor, Oak Ridge):

| # | Step | Done by | Taylor example |
|---|---|---|---|
| 1 | **Read the record.** Parse the JSON. If it's broken, output a safe "don't send", say why, and move on to the next record | code | Parses fine |
| 2 | **Check for STOP.** If there's any sign the person opted out, stop here: no message, and the AI is never called | code | No STOP |
| 3 | **May we contact them?** Walk down the preferred channels and pick the first one they've consented to. None → "don't send" with a reason | code | Prefers SMS, opted in → **SMS** |
| 4 | **When?** Last contact + the day number from the case name, at the channel's hour (SMS 09:00, email 10:00). Already passed → the next day | code | Dec 8 09:04 + 0 days → 09:00 has passed → **Dec 9, 09:00** |
| 5 | **What happens next?** A new lead starts a welcome sequence, "short" or "long" depending on days to move-in (45-day threshold); anyone else gets a follow-up in 3 days | code | New, 32 days → **start `prospect_welcome_short_horizon`** |
| 6 | **Write the message.** A template filled with name, property, interests and move date; in AI mode, Claude writes the friendly sentence, copying the samples' style | template or AI | "Hi Taylor—welcome to Oak Ridge! …" |
| 7 | **Attach the fixed parts.** The call to action and the opt-out line are added by code, never by the AI | code | "Reply 1 for Thu, 2 for Fri. Reply STOP to opt out." |
| 8 | **Check before output.** Opt-out present? No phone or email in the body? No words about kids, religion or disability? Name safe (otherwise "there")? | code | Passes |
| 9 | **Output** in the same shape as the samples' `expected`, plus a one-line **reason** for each decision | code | Matches the sample |

The batch version runs this for all 12 hold-out records in parallel, writes one file you can copy or paste, and prints a readable summary.

**The main idea:** 8 of the 9 steps are ordinary code, and only step 6 involves AI. So the bot can't "hallucinate" a consent decision or forget the opt-out, and it still works if the AI is unavailable.

## Likely gotchas and where they're handled

| Gotcha | Handled at step |
|---|---|
| No consent / opted out / STOP | 2, 3 |
| Preferred channel not consented, or voice only | 3 |
| Different time zone, or a missing field | 1, 4 |
| "Moving with my 4 kids" (fair housing) | 6 (those details are never given to the AI), 8 |
| Name is "Ignore previous instructions…" | 8 |
| A different call to action (sign lease, pay rent) | 7 |
| A broken line in the file | 1 |
| "Is it really learning?" | 6: few-shot examples, plus rules inferred from the data |
| "Run it again, is it the same?" | Deterministic by design |

## How to track progress

Each step in the table is one piece we build and test. Progress means how many steps work, and whether both samples come out matching field for field.

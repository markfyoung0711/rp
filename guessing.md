# What the JSONL might contain

Working notes ahead of the RealPage take-home. The assignment ("build a bot that takes
customer input and responds", plus a JSONL file) has not arrived yet.

## Likely shapes

| Shape | Example record | What it implies we build |
|---|---|---|
| Labeled utterances (most likely) | `{"text":"my rent didn't post","intent":"payment_status","entities":{...}}` | Router labels come from the file; intent accuracy is the headline metric |
| Conversation transcripts | `{"id":1,"turns":[{"role":"customer",...},{"role":"agent",...}]}` | Tone and flow examples, plus a ready-made eval set of real phrasings |
| Knowledge base / FAQ | `{"question":"...","answer":"...","category":"leasing"}` | Retrieval tool over the entries; answers grounded in them |
| Domain records | `{"unit":"4B","balance":812.40,"charges":[...]}` | Lookup tools over the data; this is the system of record |
| Terminology / taxonomy | `{"term":"NSF fee","synonyms":["bounced payment fee"],"definition":"..."}` | Entity extraction and glossary; feeds router and reply wording |
| Tickets with resolutions | `{"subject":"...","category":"maintenance","resolution":"..."}` | Routing plus suggested actions; categories become intents |
| Mixed, with a `type` field | `{"type":"faq",...}` / `{"type":"unit",...}` | One loader that branches on `type` |

Best guess given RealPage's domain (residents, leases, rent ledgers, maintenance):
labeled utterances or tickets, possibly with an FAQ section.

## The four roles a file can play

Whatever the shape, the data can only serve four purposes, so the loader can be written
before the file arrives:

1. **Grounding data** -> tools (`get_balance`, `get_work_order`)
2. **Knowledge** -> retrieval tool (`search_kb`)
3. **Examples** -> few-shot prompts and eval cases
4. **Taxonomy** -> router labels, entity types, glossary

Interview line: "I built an ingestion layer that classifies the file into those four
roles, so the architecture didn't depend on the file's shape."

## Assumptions to state in the README

The assignment is open-ended and questions can't be asked, so record these decisions:

- **Who the user is:** resident, property manager, or prospect. Changes tone and data visibility.
- **Read-only or acting:** build read plus two guarded writes, to show actions work.
- **Authority of the file:** the JSONL is the system of record; never answer from model
  knowledge about RealPage.
- **Success criteria:** correct intent, grounded answer, escalation when unsure. This is
  what the evals measure.
- **Scope boundary:** no legal advice, no fair-housing steering, no rent-pricing opinions.
- **Out-of-scope handling:** say what the bot can do, then offer handoff.

## Next step

`profile_jsonl.py`: read any JSONL, report record count, key union with fill rates,
nesting, value cardinality and sample rows, then guess which of the four roles it fits.
One command when the file arrives.

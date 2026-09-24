# Code Review Results (checklist run, 2026-09-24)

> Run against v0.1.0 using [`code-review-checklist.md`](code-review-checklist.md). Every finding was reproduced before it was fixed. After each fix, both samples were re-run (still matching every field) and `uv run pytest` passed.

| # | Sev | Finding | Reproduction | Expected → actual | Fix | Status |
|---|---|---|---|---|---|---|
| 1 | P0 | Output file not byte-identical across runs | Run the samples twice with `-o`, then `cmp` | identical → differed (`latency_ms`) | Timing removed from the export (still shown on screen) | Fixed, auto |
| 2 | P0 | No README; the claims and commands can't be checked | `ls README*` | a README → none | README with commands, output shape, built vs designed, assumptions | Fixed |
| 3 | P0 | Time-zone data may be missing on the demo machine (Windows) | Dependency review | `tzdata` pinned → absent | Added `tzdata` dependency | Fixed, auto |
| 4 | P0 | LLM timeout too long: 20 s × 3 attempts = up to 60 s per record if the network hangs | Code read (`AsyncAnthropic(timeout=20, max_retries=2)`) | bounded → up to 60 s | 8 s, 1 retry, then the template | Fixed, auto |
| 5 | P1 | `channel_preferences` of the wrong type → internal error → human review | `channel_preferences: 5` | handled with a warning → TypeError | Non-list values ignored with a warning; default order used | Fixed, auto |
| 6 | P1 | Names in non-Latin scripts replaced by "there" | `first_name: "李"` | "Hi 李" → "Hi there" | Name check accepts letters from any script | Fixed, auto |
| 7 | P1 | Duplicate `task_id` not flagged | The same record twice | a warning → none | Batch-level warning on each duplicate | Fixed, auto |
| 8 | P1 | Steering word list incomplete ("families", "adults only", "no kids", …) | Word-list review | blocked → not in the list | Terms added to `protected_terms` | Fixed, auto |
| 9 | P1 | Lint/type: ruff reports style only in our code (plus the Gemini reference file); mypy reports 5 typing-only issues (Optional narrowing, SDK overload typing) | `uv run ruff check outreach bot.py tests`, `uv run mypy outreach bot.py` | — | Intentional broad `except` blocks annotated; typing left as is | Accepted, no behavior impact |

**Checks that passed without changes:** no sample literals in code (Oak Ridge appears only in `config/properties.yaml` as property facts); channel matrix (voice first → SMS, with the skipped channel logged); no consent / null / "maybe" consent → no send; DST boundary (−05:00 after Mar 8); invalid time zone → the property's; horizon edge (45 → short, 46 → long); past or missing move date → short; resident/renewal → no tour push, no price; injection in the name or profile not repeated; unknown property → no specific claims; no PII in outputs; protected profile fields (`has_children`, `religion`) not used; bad key in `--llm` → template fallback, both samples still match; clean clone + `uv sync` → samples match; send hours inside 08:00–21:00.

**Open for a human decision:** none that blocks the demo. A missing `last_interaction` uses the current time (flagged as not reproducible); `--now` makes it reproducible.

---
name: triage
description: Build and work down a leverage-ranked worklist of poor-quality / unmatched water-main pay items, routing each to a fix — decompose in gold_decompositions.md (identity-fixable) or flag for the located layer (project/located variance). Two modes — "triage old vs new" (an awarded contract's bad-quality items intersected with an UPCOMING contract's unmatched items, so each fix pays off twice) and "triage old vs old" (awarded-vs-awarded, predicted-vs-actual error measured directly). Triggered by phrases like "triage", "triage misses", "triage awarded vs mismatched", "triage old vs new", "triage old vs old", "what should I decompose next", "leverage-ranked decomposition list", "bad-quality water items".
allowed-tools: Bash, Read, Edit, Write
---

# Triage

Decide **which pay items to fix next, and how.** Triage builds a leverage-ranked worklist of water-main items that are mis-priced and/or unmatched, then routes each one:

- **identity-fixable** (string fragmentation / cross-jurisdiction mis-pooling) → **decompose in `~/parts/data/gold_decompositions.md`** (the closed-loop, measurable win).
- **located-variance** (project / station / depth / disposal / aggregate / relocated-hydrant) → **flag for the located layer; do NOT decompose** (more attributes won't fix it).

The master list is **predicted-vs-actual leverage across ALL awarded water-main items** (the spine has actuals for awarded contracts). You whittle that list down over many sessions.

## The two modes

- **old vs new** — an **awarded** contract (has actual winning prices → measurable accuracy) intersected with an **upcoming** contract's **unmatched** items (e.g. Sugar Grove `002-62M71`, bids 6/12, no actuals yet). Fixes here pay off twice: provable accuracy gain on the awarded baseline **and** coverage gain on the upcoming bid. Highest priority.
- **old vs old** — **awarded × awarded** (or the whole awarded universe). Both sides have actuals, so predicted-vs-actual error is measured directly. Use when there's no live bid driving priority, or to mine the long tail.

Default: if the user names an upcoming contract, run **old vs new** against it; otherwise run **old vs old** across all awarded water items.

## Hard rules (do not violate)

- **`uv run`** for all Python. Never `python3` / never activate the venv.
- **The LINC1 spine is FROZEN, read-only:** `data/warehouse/training_spine.parquet`. Verify its sha before/after; never write it.
- **Gold lives in `parts`, harnesses + spine live in `estimator`.** `gold_decompositions.md` / `axis_vocab.md` are in `~/parts/data/`. Cross-repo = **separate commits** (never one commit spanning both).
- **Classifier wiring is deferred (Phase 2).** Triage produces *gold decompositions* (authored `gold_decompositions.md` entries), NOT classifier code. Nothing consumes `gold_decompositions.md`/`context` today, so authoring is safe. Re-measurement happens after a separate wiring pass.
- **No "atomic" / "prior art"** in any user-facing text (use `itemized`/`single-line`; `existing approaches`). Describe price basis as "public bid history," not IDOT, in Winninger-facing text.

## 1 · Build the worklist (the engine)

Produce a leverage-ranked table of bad-quality / unmatched items. Use / extend the existing harnesses in `scripts/`:

- `sugar_grove_baseline_intersection.py` — the leverage/intersection engine. **Fix the `$0`-actual artifact first: floor `actual > 1`** (nominal balanced bids like `FURNISHED EXCAVATION` blow up err%/leverage).
- `water_linc1_vs_linc2.py`, `contract_linc1_vs_linc2.py` — per-item LINC1 vs LINC2 predicted-vs-actual on water items.
- `sugar_grove_coverage.py` — coverage / **unmatched** list for an upcoming contract (old-vs-new mode).
- `predict_vs_actual_ogden.py` — the awarded-contract accuracy harness pattern.

If no single script computes predicted-vs-actual across **all** awarded water items, build one (one-off in `scripts/`, `uv run`), reading actuals from the frozen spine. Output columns:

```
description | unit | contract | actual | predicted | abs_err% | $weight (qty×actual) | leverage (abs_err × $weight) | match_status
```

Rank by **leverage** desc. For **old vs new**, additionally mark rows whose description (or canonical) appears **unmatched** in the upcoming contract — those are the double-payoff items; float them to the top.

Apply the `actual > $1` floor. **Log anything you drop** (don't silently truncate — a top-N cap must be stated).

## 2 · Triage each top item (the key sort)

For each high-leverage item, decide its route:

- **identity-fixable** — the error comes from *what the item is* being ambiguous: string fragmentation (`D I WATER MAIN 8` vs `WATER MAIN 8`), or cross-jurisdiction mis-pooling (a small tie-in pooled with a big one because identity axes are too coarse). → **decompose** (step 3).
- **located-variance** — the error comes from *where/how it sits on this job*: waste disposal, aggregate, curb & gutter, big connections, **relocated/removed hydrants**, anything whose price is driven by station/depth/haul/site. → **flag for the located layer; do NOT author a decomposition.** (Findings F6/F7: more attributes won't fix these.)

When unsure, read the source (step 3) before deciding — the SP/plans usually make the route obvious.

## 3 · For identity-fixable items: source-read, then author

1. **Source-read** — pull the real description (spine), and where identity isn't in the bid line, the **special provision + plan sheet notes** (the connections needed PLANS.PDF; the itemized items #7–14 are mostly text-derivable). Quote sheet notes verbatim into `Note:` fields.
2. **Author / extend `~/parts/data/gold_decompositions.md`** using the block convention (legend at the top of `gold_decompositions.md`):
   ```
   <PAY ITEM DESCRIPTION — verbatim, a label not a key>
   - function: <anchor; selects the family schema>
   - identity:    # THE POOL KEY — recipe-hash hashes exactly this block
   - context:     # annotation / cost-modifier — per-instance, never hashed
   - provenance:  # contract, keynote, station, finding — never hashed, never pooled
   ```
   - Axis **name** is global; its **tier** is per-(function, axis) — set by which block it sits in.
   - Keynote letters (`"O"`, `"E"`) → **provenance** (carry no identity; another contract's `"O"` is unrelated).
   - Per-contract bundling (`includes`) → **context**; the item's *own defined* composite (e.g. `GATE VALVE AND VALVE VAULT`) → an identity discriminator (a `housing` axis) or a recipe — never let bundling fragment a pool.
3. **Extend `~/parts/data/axis_vocab.md`** for any new function / axis / value (it's the validation set). Add detection tokens; keep `unknown` when a token is absent (don't guess).
4. **Surface genuine forks** (DEC-style) to the user before locking — don't unilaterally decide identity-vs-annotation calls that change pooling. Confirm, then write.

Reference the running cleanup list `~/parts/docs/water-main-decomposition-cleanup.md` (items #1–16) and the findings ledger `~/parts/docs/linc2-vertical-slice-findings.md`.

## 4 · Output a triage report

Write a dated markdown report to `data/reviews/triage_<scope>_<YYYYMMDD>.md`:

- The leverage-ranked table (top N, with N stated).
- Per-item **route** (decomposed / located-flagged / skipped) + one-line reason.
- Which `gold_decompositions.md` entries were authored/extended this pass, and which `axis_vocab.md` additions.
- The remaining list (what's still to whittle).

## 5 · Commit (only when the user asks)

- `parts`: `gold_decompositions.md` + `axis_vocab.md` on the feature branch (`feat/linc2-vertical-slice`), one commit.
- `estimator`: any new harness/report — branch off `main` first; never sweep in pre-existing WIP.
- End commit messages with the project's `Co-Authored-By` trailer.

## 6 · (Deferred) re-measure

After a separate Phase-2 wiring pass (decompositions → `~/parts/scripts/build_linc2_spine.py`), re-run the awarded-contract accuracy harness and report before/after on the triaged items. Triage itself stops at authored gold + the report.

---
name: triage-feedback-wire-loop
description: >
  Run the full LINC2 pay-item decomposition loop for the NEXT family in the Sugar Grove
  non-water build order: triage -> author the candidate-pool doc (pools + questions) ->
  send to the SME API (Google Gemini) -> critique/iterate until satisfied -> author the
  gold (gold_decompositions.md + axis_vocab.md) -> commit with a decision summary -> wire into the spine ->
  rebuild + measure. Triggered by "triage-feedback-wire-loop", "do the next pay item",
  "run the loop for the next family", "next non-water family".
---

# triage-feedback-wire-loop

The closed loop for decomposing ONE roadwork pay-item family, end to end, with the SME
(Google Gemini) in the loop instead of manual copy/paste. Builds on the `triage` (authors
gold) and `wire` (implements gold) skills; adds the automated SME-feedback step.

## Where things live
- **Gold + vocab + classifier:** `~/parts/` — `data/gold_decompositions.md`, `data/axis_vocab.md`, `scripts/build_linc2_spine.py`. Parts trunk is `main`.
- **Harnesses + SME caller + review docs (estimator):** `scripts/roadwork_pool_candidates.py`, `scripts/sme_feedback.py`, `data/reviews/`.
- **The build order / worklist:** `data/reviews/triage_sugar-grove-roadwork_20260610.md` (identity-fixable families ranked by $leverage).
- **Frozen L1 spine (read-only, sha-verified):** `data/warehouse/training_spine.parquet`.
- **L2 spine (regenerated each wire):** `~/parts/data/cache/training_spine_linc2.parquet`.

## The SME = Google Gemini
- `scripts/sme_feedback.py` calls Gemini under a senior-IDOT-estimator system instruction.
- **PREFER `--vertex`** (gemini-2.5-pro via GCP billing on estimator-490820, ADC auth, Vertex AI API enabled): no free-tier cap, stronger reasoning. The free-tier API key path (`GEMINI_API_KEY` in `.env`, default `gemini-2.5-flash`) rate-limits hard (free `gemini-2.5-pro`/`2.0-flash` are limit=0; `2.5-flash` 503/429s after a few calls) — use it only as a fallback.
- Call: `uv run python scripts/sme_feedback.py <doc.md> --vertex [--followup "critique"] [--out <roundtrip.md>]`.

## The loop (8 steps)

1. **Triage → pick the next family.** Read the build order; take the highest-$ family not yet done. State which one and why (rank + $weight). Don't pick silently — show the list if the user hasn't seen it recently.
2. **Author the candidate-pool doc.** Explore the family in the corpus (SG bid items tagged `<<SG>>` + winner pools by candidate work-type/axis) and write `data/reviews/<family>_pool_candidates_for_sme_<date>.md`: SG items, corpus pools (winner count + median winning $), and a numbered list of the genuine POOLING FORKS. For heterogeneous clusters, write the doc directly (faster than regex-config); for simple families, extend `roadwork_pool_candidates.py`.
3. **Send to the SME API.** `sme_feedback.py <doc> --out <roundtrip>`.
4. **SME replies.** Read every answer.
5. **Critique & iterate (3↔5) until satisfied.** YOU are the reviewer — do not rubber-stamp. Re-send a `--followup` for any disagreement and converge. Past real catches:
   - box_culvert: SME OVER-fragmented (5 functions) → collapsed to 3 (axis-over-function).
   - erosion_landscape: SME UNDER-fragmented (1 `erosion_control` + work_type axis) → split into separate functions per operation.
   - SME over-inferred `construction_method: precast` on a removal → corrected to `unknown`.
   - SME equated PERIMETER EROSION BARRIER with silt fence → corpus proved distinct products.
   The reviewer's job is architecture consistency + no fabricated inferences + verify claims against the corpus.
6. **Author the gold.** `~/parts/data/gold_decompositions.md` (representative entry per function/regime) + `~/parts/data/axis_vocab.md` (functions in the enum + new axes + a `#NN` family note with `classify_function` recognition tokens).
7. **Commit with a decision summary.** parts `main`, one commit, body = the SME-signed decisions (what's identity / context / provenance / located, and any reviewer corrections). Cross-repo = separate commits (estimator review docs commit separately).
   - **Commit authorization (Mark, 2026-06-11):** a completed Gemini SME round-trip + at least ONE reviewer critique sent back to Gemini = sign-off. When both have happened, you ARE authorized to commit the gold + wire without re-asking. (No round-trip-plus-critique → ask first.)
8. **Wire + rebuild + TEST + measure.** Extend `build_linc2_spine.py` (routers ordered specific→general, route the new family AFTER the prior ones and BEFORE the general water-pipe catch; per-axis extractors; bump `EXTRACTOR_VERSION`). Smoke-test routing on the SG items + the excluded items. **Run the test suite — `uv run pytest /home/markfyoung/parts/tests/test_linc2_function_classifiers.py -q` — between EACH family, not just at the end (Mark, 2026-06-11).** When a family supersedes an older coarse router (e.g. #24 narrowed F5 erosion_control; #5 took over combination curb&gutter), existing tests WILL fail intentionally — update those assertions to the new correct function (sharpen, don't loosen, per the file's own rule), and ADD tests pinning the new functions + any evictions. Only after green: full rebuild, confirm the L1 sha is unchanged, measure the SG lift (each `<<SG>>` item's pool depth + median). Commit gold + wire + tests.

## Architecture conventions (enforce on the SME)
- **ONE function per distinct physical operation.** Split regimes with AXES, not parallel functions (removal = `action:remove` inside the family, not a `*_removal` function). The subgrade cluster = 6 functions; box culvert = 3; erosion/landscape = 10 — each a real operation.
- **`basis` is a hard machine splitter:** SQ YD/ACRE=area, CU YD=volume, TON/POUND=mass, FOOT=linear, LUMP SUM=lump_sum. EACH/discrete point functions OMIT basis.
- **Provenance is stripped from identity:** per-contract numbers/letters (CULVERT NO. 1 / C1, keynote "F") never pool.
- **LOCATED** (recognize, don't trust a pool): manufactured-to-spec or site-driven (haul/depth/disposal/rig-mob). Thin/zero-comp specialty items.
- **Spec the string names = identity** (class, thickness, gradation, cure, reinforcement, method, grade); a per-contract `SPL/SPECIAL` suffix is usually CONTEXT — EXCEPT when it's a recurring spec tier with a consistent price across many wins (then identity).
- **No "atomic"/"prior art" in user-facing text;** "public bid history" not IDOT in Winninger-facing text.

## Hard rules
- `uv run` for all Python. The L1 spine is FROZEN/read-only (sha-verify). Keep `unknown` when a token is absent (don't guess) unless the vocab defines an explicit inference. Don't author classifier code in the gold step; don't author gold in the wire step.

---
name: wire
description: Implement the authored gold decompositions (gold_decompositions.md / axis_vocab.md) as classifier rules in the LINC2 spine builder, rebuild the L2 spine, verify, and measure the coverage lift. The companion to `triage` — triage AUTHORS the gold, wire IMPLEMENTS it into the data. Triggered by phrases like "wire", "wire the spine", "wire decompositions", "wire the gold", "implement decompositions", "build the L2 spine", "populate the L2 spine".
allowed-tools: Bash, Read, Edit, Write
---

# Wire

Turn the human-readable gold spec into a live classifier. `triage` produces decompositions in `~/parts/data/gold_decompositions.md` + `~/parts/data/axis_vocab.md`; **wire implements those token rules in `~/parts/scripts/build_linc2_spine.py`** so the LINC2 spine (`training_spine_linc2.parquet`) gets POPULATED with the decomposed identity axes — instead of scaffolded null — then measures the result.

## Hard rules (do not violate)

- **`uv run`** for all Python. Never `python3` / never activate the venv.
- **The LINC1 spine is FROZEN, read-only:** `estimator/data/warehouse/training_spine.parquet`. The builder sha-verifies it before AND after; never write it. If the sha changes, abort.
- **This is a `parts` change.** `build_linc2_spine.py`, `gold_decompositions.md`, `axis_vocab.md` live in `~/parts/`. It reads estimator's frozen L1 spine by path (`BIDEDGE_ESTIMATOR_ROOT`). Cross-repo = **separate commits**.
- **Only wire SETTLED families.** Wire a family only after its `gold_decompositions.md` entries + `axis_vocab.md` axes are authored and stable (i.e. `triage` finished it). Don't invent rules here — the vocab is the source of truth; if a rule is missing, fix the vocab first (or in the same pass) and note it.
- **Bump `EXTRACTOR_VERSION`** every wiring pass (it tags every L2 row's provenance).
- **No "atomic" / "prior art"** in any user-facing text.

## 1 · Read the spec, list what's wireable

- Read `~/parts/data/axis_vocab.md` (the controlled vocab + detection token tables) and `~/parts/data/gold_decompositions.md` (the worked entries).
- Inventory the **functions with gold entries** and the **axes each family declares**. Only these get wired this pass. Note any family that's partial/unsettled and skip it (log what you skipped).

## 2 · Extend the classifier (`build_linc2_spine.py`)

The current classifier is deliberately narrow (connections + F5 items + valve_box; `action`/`material` scaffolded null). Extend it:

- **`classify_function`** — add routing for each authored function (e.g. `water_main_pipe`, `valve`, `hydrant`, `casing`, `cut_cap`). **Order specific→general** (e.g. `valve_vault`/`valve_box` before `valve`; `water_main_connection` before `water_main_pipe`; `cut_cap` point-ops before the FOOT pipe). Reconcile any name drift so emitted functions MATCH `gold_decompositions.md` (e.g. `erosion_control_temp`→`erosion_control`).
- **Axis extractors** — one per axis, implementing the `axis_vocab.md` token table verbatim, with first-hit precedence where the vocab specifies it (e.g. `joint`: restraint/fusion before bare `mj`). Wire at least: `action`, `material`, `joint`, `valve_type`, `housing`, `seal_type`, `permanence` (incl. the no-`TEMP`→`permanent` conf-M prior), plus any others the settled families use.
- **Respect the tiers:** populate IDENTITY axes into the pool-key columns; carry CONTEXT/PROVENANCE separately. NEVER feed `keynote` or any provenance field into pool membership (axis_vocab "Provenance — not match keys").
- **UOM is a splitter** — `uom_norm` participates in identity (e.g. EACH cut_cap vs FOOT water_main_pipe).
- **Reconcile stale scaffolds:** drop the retired `crossing` column; replace `scope_variant` with `replaced_fitting`/`replacing_fitting`; fold `includes_vault` into the general bundling annotation. (These were scaffolded null and unconsumed, so removal is safe.)
- Keep `unknown` when a token is absent (don't guess) — except where the vocab defines an explicit inference (bare WATER MAIN→DI conf M; no-TEMP→permanent conf M). Mark inferred values in `axis_source`.

## 3 · Rebuild + verify

- Run `uv run python scripts/build_linc2_spine.py`. Confirm the L1 sha is unchanged (the script aborts otherwise).
- Verify: `function` value-counts (coverage up from the narrow baseline?), `action`/`material`/etc. distributions look sane, and spot-check 10–20 rows per new family against their `gold_decompositions.md` entries.
- Sanity gate: the known fragmentation pairs should now share an identity (e.g. `D I WATER MAIN 8` / `WATER MAIN 8` → same function+size+material pool).

## 4 · Measure the lift

Re-run the `triage` worklist engine (`scripts/water_triage_worklist.py`) or a coverage check and report **before/after**: string-miss rows that become signature/identity hits, pools that merged, and — for awarded contracts (Ogden, 61E15/61E73) — whether the bad-item errors move. This is the payoff that closes the triage→wire loop.

## 5 · Commit (only when the user asks)

- `parts`: `build_linc2_spine.py` (+ any vocab fixes) on the feature branch, one commit, `EXTRACTOR_VERSION` bumped.
- Report the coverage/measurement delta in the commit body.
- End with the project's `Co-Authored-By` trailer.

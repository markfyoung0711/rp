---
name: product-status
description: Survey BOTH repos (estimator + parts) and produce a comprehensive inventory of every feature/enhancement added to the Estimator product and its prediction engine since the last context-doc update, grouped by status (LIVE/BUILT/EXPERIMENTAL/PROPOSED) with developer-facing and estimator-facing versions. Triggered by "product status", "feature inventory", "what's been added", "bring me up to speed", "what's live vs in the lab", "what shipped since".
allowed-tools: Bash, Read, Write
---

# Product Status — feature inventory (two repos)

Produce a comprehensive inventory of every feature and enhancement added to the **Estimator**
product **and its prediction engine**. Bring a planning agent (or a returning human) up to speed:
what an estimator can actually use **today** versus what's still in the lab, with a trail back to
where each thing came from.

## The two repos (survey BOTH)

- **`~/estimator`** — the **product**: the live API (`bidedge-api` on Cloud Run), the web UI, the
  upload/parse path, the data warehouse + parsers, and the resolver-protocol seam.
- **`~/parts`** — the **prediction engine** (LINC2 / ORACLE): recognition (`build_linc2_spine.py`,
  `assemble_identity`), pricing (`predict_project.py`, `linc2_price.py`), the SG-golden gate
  (`regression_sg_golden.py`), the decomposition recipes (`data/families/*.toml`,
  `gold_decompositions.md`), and the awarded-price scrapers/warehouse.

A given capability often spans both — recognition/pricing land in `parts`, then surface to the
estimator through the resolver protocol / engine API. Attribute each feature to the repo(s) it lives
in, and note when it crosses the boundary.

## Naming (say this so nobody hunts for two products)

All our context documents call the product **Estimator**, but the live API on Cloud Run is named
`bidedge-api` — so **"BidEdge" and "Estimator" are the same product**. Do not look for two separate
products. (`parts` is not a second product — it's the engine behind Estimator.)

## Period to cover

**If the user names a start (e.g. "back to the beginning of April", "everything since launch", a
date), use that** — it overrides the default. Otherwise cover the period **since the last context-doc
update**. Either way, state the exact range you covered. To find the default boundary:

- Newest date in `~/estimator/docs/claude-context/04-decisions-log.md` (`grep -oE
  '20[0-9]{2}-[0-9]{2}-[0-9]{2}' … | sort -u | tail`).
- Cross-check with `git log` in **both** repos (`git -C ~/estimator log -1 --format=%ci`; `git -C
  ~/parts log -1 --format=%ci`; then `git -C <repo> log --since=<boundary> --date=short
  --format='%ad %h %s'`).

**State the exact date range you actually covered** at the top of the output.

## Sources to mine

**estimator (`~/estimator`):**
- `git log` — commits, dates, messages (`--since=<boundary>`, `--name-only`).
- `docs/claude-context/04-decisions-log.md` — decisions made.
- `docs/claude-context/05-open-questions.md` — what's still open (for the tie-in below).
- `src/api/main.py` — the **live API** (`grep -nE '@app\.(get|post)'`): what predict / compare /
  search / review / parse-bid-schedule actually do now.
- `src/web/static/index.html` — UI tabs and capabilities (`grep id="tab-`).
- `experiments/` — what's been proven out (e.g. bundle_model, wave_resolution).
- `src/parsers/` — new data sources added.
- `scripts/` — new pipeline steps and tools.
- `src/resolver/`, `src/engine/` — the resolver-protocol seam + the prediction-engine API.

**parts (`~/parts`):**
- `git -C ~/parts log` — commits, dates, messages (`--since=<boundary>`, `--name-only`).
- `scripts/predict_project.py`, `build_linc2_spine.py`, `linc2_price.py`,
  `linc2_predict_eval.py` — the recognition + pricing engine (ORACLE).
- `scripts/regression_sg_golden.py` + `tests/golden/` — the accuracy gate.
- `data/families/*.toml`, `gold_decompositions.md`, `axis_vocab.md` — the decomposition recipes /
  identity vocabulary (how many families are covered now).
- `scripts/build_idot_wctb_awarded_warehouse.py` + scrapers — new awarded-price data sources.
- `docs/` — design/contracts/open-question docs on the engine side.

## For each feature or enhancement, give

1. **Short name.**
2. **A 1–2 sentence plain-English description** a construction estimator can read.
   Do **NOT** use the words "atomic", "prior art", or "latent" — use **"itemized"**, **"what's out
   there already"**, and **"markup"** instead (per `docs/claude-context/03-conventions.md`).
3. **Status** — one of:
   - **LIVE** — deployed to Cloud Run (`bidedge-api`).
   - **BUILT** — in the repo, not deployed.
   - **EXPERIMENTAL** — proven in `experiments/` (or as an offline harness), not in the product yet.
   - **PROPOSED** — designed, not built.
4. **Where it came from** — commit hash, decisions-log date, or file path.
5. **Whether it touches any open question** in `05-open-questions.md` (cite the OQ-ID).

## Grouping & ordering

Group by **status, LIVE first**. Within each group, order by **impact on bid-prediction accuracy**.

## Output — two versions

Produce **both**, per `docs/claude-context/03-conventions.md`:

1. A **developer-facing** version (commits, file paths, OQ-IDs intact).
2. An **estimator-facing** summary in plain construction language (no developer-speak; honor the
   vocabulary substitutions above).

Write both to `docs/claude-context/product-status-<YYYY-MM-DD>.md` and paste the **estimator-facing**
summary into the chat so the human can sort it into priorities.

## Why this earns its keep

The **status grouping** shows instantly what an estimator can use today versus what's still a science
project; the **open-question tie-in** stops us re-litigating something already decided.

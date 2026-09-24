---
name: refresh-warehouse
description: Rebuild data/warehouse/training_spine.parquet and related warehouse artifacts from the current staged parquets. Triggered by phrases like "refresh warehouse", "rebuild spine", "rebuild warehouse", "warehouse refresh", "refresh training spine", "rebuild training spine".
allowed-tools: Bash, Read
---

# Refresh Warehouse

Rebuild the training spine and related warehouse artifacts after new raw or staged data has landed. Runs in medallion order: staged parsers first, then warehouse enrichments, then the spine, then optional masters.

## Before running

Ask the user which level of refresh they want:

- **Spine-only** — staged data already current; just rebuild `training_spine.parquet`. Fastest, ~1-2 min.
- **Enrichments + spine** — rebuild work-category master + spine. Medium, ~3-5 min.
- **Full refresh** — re-parse raw data into staged, rebuild everything. Slow, 15-30+ min depending on data volume.

Do NOT run the full refresh without explicit confirmation — it touches every parser and can take 30+ minutes.

## Steps — spine-only (default)

```
uv run python scripts/build_minimal_spine.py
```

Then verify:

```
uv run python -c "
import pyarrow.parquet as pq
m = pq.read_metadata('data/warehouse/training_spine.parquet')
print(f'rows: {m.num_rows:,}  cols: {m.num_columns}')
"
```

Report row count and any notable change from the prior snapshot.

## Steps — enrichments + spine

```
uv run python scripts/build_work_category_master.py
uv run python scripts/build_minimal_spine.py
```

## Steps — full refresh

Run parsers to rebuild staged data first. Each parser is independent; run in any order, but complete all before building enrichments.

**IDOT parsers:**
```
uv run python -m src.parsers.idot_wctb_unit_price_tabs
uv run python -m src.parsers.idot_foia_unit_price_tabs
uv run python -m src.parsers.idot_wctb_contract_details
uv run python -m src.parsers.idot_coded_pay_items
uv run python -m src.parsers.idol_prevailing_wage
```

**Municipal parsers** (run only those whose raw data has changed — check `data/raw/` mod times):
```
uv run python -m src.parsers.naperville_bid_tabs
uv run python -m src.parsers.yorkville_bid_tabs
uv run python -m src.parsers.joliet_gov_bid_docs
uv run python -m src.parsers.questcdn_bid_tabulations
```

**Enrichments:**
```
uv run python scripts/build_work_category_master.py
```

**Spine:**
```
uv run python scripts/build_minimal_spine.py
```

**Optional — canonical registry (identity/resolution layer, NOT a spine dependency):**
```
uv run python scripts/build_canonical_registry.py
```

## After running

Always report:

1. New row count of `training_spine.parquet`.
2. Delta from prior snapshot if prior row count is known (the user may have stated it).
3. Any parser errors surfaced (stderr) — do not swallow these.
4. Mod time of the new spine.

If any parser fails, stop immediately, report which parser and the error, and ask whether to retry or skip.

## Not covered by this skill

- RAG corpus refresh — separate pipeline at `scripts/rag_refresh.py`.
- Raw data acquisition (downloading new bid tabs, FOIA returns, etc.) — upstream of this skill.
- Canonical registry structural changes (schema migrations, decomposition backfill) — those are design work, not refresh work.

## Notes

- There is no single orchestrator script. Each step is invoked separately; that's intentional per project convention (medallion strictness, manually-run scripts under `scripts/`).
- Architecture reference: `docs/claude-context/01-architecture.md`.
- The spine is the canonical warehouse artifact for all downstream model/prediction work. Treat it as the authoritative source.

---
name: refresh-model
description: Refresh the prediction model end-to-end — rebuild the warehouse / training spine first if any staged data is newer, then retrain the model. Triggered by phrases like "refresh model", "refresh the model", "update model", "retrain model", "refresh and retrain", "refresh model end-to-end".
allowed-tools: Bash, Read
---

# Refresh Model

End-to-end model refresh. Detects staleness in the data pipeline, rebuilds only the layers that need it, then retrains the model. Skips work where outputs are already newer than inputs.

Pipeline order (medallion):

```
data/staged/<source>/*.parquet    →   data/warehouse/training_spine.parquet   →   models/<model>.json
                                  (build_minimal_spine.py)                       (train_<model>.py)
```

This skill **does not** re-parse raw → staged. That's per-source and not safely automatable. If staged data is itself out of date relative to raw, surface it to the user; do not silently re-stage.

## 1 · Check freshness of each layer

Run staleness checks. Layer is "stale" if its newest input file has an mtime newer than its output file's mtime, or if the output file does not exist.

```
uv run --no-project python <<'PY'
from pathlib import Path
import os, sys

REPO = Path("/home/markfyoung/estimator")
STAGED = REPO / "data" / "staged"
SPINE  = REPO / "data" / "warehouse" / "training_spine.parquet"
MODEL  = REPO / "models" / "model_a_winning_bid.json"

def newest_mtime(paths):
    mtimes = [p.stat().st_mtime for p in paths if p.is_file()]
    return max(mtimes) if mtimes else 0.0

newest_staged = newest_mtime(list(STAGED.rglob("*.parquet")))
spine_mtime   = SPINE.stat().st_mtime if SPINE.exists() else 0.0
model_mtime   = MODEL.stat().st_mtime if MODEL.exists() else 0.0

print(f"newest staged mtime: {newest_staged:.0f}")
print(f"spine mtime:         {spine_mtime:.0f}")
print(f"model mtime:         {model_mtime:.0f}")

spine_stale = (not SPINE.exists()) or (newest_staged > spine_mtime)
model_stale = (not MODEL.exists()) or (spine_mtime > model_mtime) or spine_stale

print(f"SPINE_STALE={int(spine_stale)}")
print(f"MODEL_STALE={int(model_stale)}")
PY
```

Read the `SPINE_STALE` and `MODEL_STALE` flags from the output.

## 2 · Refresh the warehouse / spine if stale

If `SPINE_STALE=1`:

```
uv run python scripts/build_minimal_spine.py
```

Verify after:

```
uv run --no-project python -c "import pyarrow.parquet as pq; m = pq.read_metadata('data/warehouse/training_spine.parquet'); print(f'rows: {m.num_rows:,}  cols: {m.num_columns}')"
```

If `SPINE_STALE=0`, skip this step and report "spine already current".

## 3 · Retrain the model if stale

If `MODEL_STALE=1`, retrain. Default model is model A (winning bid):

```
uv run python scripts/train_model_a_winning_bid.py
```

Other models exist and may also need refresh (ask the user before triggering all of them; they take time):

- `scripts/train_baseline_xgboost.py` — baseline unit-price model
- `scripts/train_model_a_winning_bid.py` — winning bid (production)
- `scripts/train_model_c_estimate_accuracy.py` — estimate accuracy
- `scripts/train_model_d_bid_ranges.py` — bid-range p10/p50/p90

If the user said "refresh model" without specifying, default to model A only and report the others as eligible-but-not-refreshed.

If `MODEL_STALE=0`, skip and report "model already current".

## 4 · Report

Tell the user concisely what was done:

- **Spine:** rebuilt (rows/cols) OR already current (mtime)
- **Model:** retrained (which one) OR already current (mtime)
- **Note staleness in raw → staged**, if any source dir's raw mtime is newer than its staged parquets' mtime. The user must re-stage manually for those sources (since per-source parsers are bespoke).

## Hard rules

- Never re-parse raw → staged automatically. That's per-source and bespoke. Surface stale sources; let the user trigger the right parser.
- Never train more than one model in parallel. Sequential only.
- Always `uv run` for Python.
- Don't skip steps to "save time" — the freshness check is what makes this skill safe to call repeatedly without wasting work.
- If the spine rebuild fails, do NOT proceed to model retraining. Report the failure and stop.
- If the model retrain fails, the spine is still valid — leave it; report only the train failure.

## Stop and ask when

- The user says "refresh model" but the production model A is what's typically refreshed; if there's ambiguity about which model(s) to retrain, ask before triggering more than model A.
- A staged-vs-raw mismatch is detected (means raw → staged needs human attention before this skill should run).
- The spine rebuild script reports row-count anomalies (e.g., 1.7M rows became 200K) — stop and ask before retraining on suspect data.

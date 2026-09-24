---
name: reconcile-data
description: Reconcile raw data directories against parsers, download scripts, staged output, and catalog entries. Triggered by phrases like "reconcile data", "check data status", "data reconciliation", "raw vs parser", "what needs parsing", "data pipeline status".
allowed-tools: Bash
---

# Reconcile Raw Data vs Parsers

Run the reconciliation script and display the results:

```
uv run python scripts/reconcile_data.py
```

For JSON output:
```
uv run python scripts/reconcile_data.py --json
```

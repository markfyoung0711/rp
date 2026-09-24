---
name: ml-plan
description: Display the ML build plan with progress tracking. Triggered by "ML plan", "ML status", "ML progress", "what's next for ML", "build plan".
allowed-tools: Read, Bash
---

# ML Build Plan

Display the ML build plan and progress:

1. Read and display `ML_PLAN.md` from the project root
2. Run `uv run python scripts/reconcile_data.py` to show current data pipeline status alongside it

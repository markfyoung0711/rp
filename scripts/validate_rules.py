"""Validate the rule configuration (rules.yaml + learned.yaml, and properties.yaml). Exit 0 if valid, 1 if not.

  uv run python scripts/validate_rules.py
Run it after any rule change, by a person or an AI. The bot and learn.py also refuse to run on invalid rules.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from outreach import config  # noqa: E402
from outreach.validate import RulesError  # noqa: E402

try:
    r = config.rules()
    props = config.properties()
except RulesError as e:
    print(f"INVALID\n{e}")
    sys.exit(1)
print(f"VALID: {config.rules_source()}; {len(props)} propert(y/ies); "
      f"send hours {r['channels']['send_hour']}, legal window {r['channels']['legal_window']}, "
      f"horizon threshold {r['next_action']['horizon_threshold_days']}, {len(r['cta']) - 1} CTA types")

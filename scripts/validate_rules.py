"""Validate the configuration: rules, learned rules, language templates, property facts and branding. Exit 0 if valid, 1 if not.

  uv run python scripts/validate_rules.py            # check every file
  uv run python scripts/validate_rules.py --brand    # also render a message per property and channel, and brand-check it

Run it after any rule or brand change, by a person or an AI. The bot and learn.py also refuse to run on invalid rules.
"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from outreach import config  # noqa: E402
from outreach.validate import RulesError, validate_properties  # noqa: E402


def brand_preview() -> list[str]:
    """Render a tour message for every property and channel, and run the brand check on it."""
    import asyncio
    import copy
    import json

    from outreach import guards
    from outreach.pipeline import process, sent_message

    base = json.loads((ROOT / "plans" / "sample.jsonl").read_text().splitlines()[0])
    base.pop("expected")
    problems, lines = [], []
    raw = yaml.safe_load((config.CONFIG_DIR / "properties.yaml").read_text()) or {}
    for name in raw:
        brand = guards.brand_for(config.property_facts(name))
        lines.append(f"  {name}: display name {brand.get('display_name')!r}, voice intro {brand.get('voice_intro')!r}, "
                     f"{len(brand.get('banned_phrases', []))} banned phrases, emoji {'allowed' if brand.get('emoji_allowed') else 'not allowed'}")
        for ch in ("sms", "email", "voice"):
            rec = copy.deepcopy(base)
            rec["input"]["property_name"] = name
            rec["channel_preferences"] = [ch]
            rec["consent"] = {f"{c}_opt_in": c == ch for c in ("sms", "email", "voice")}
            out = asyncio.run(process(rec))
            msg = sent_message(out)
            if not msg:
                problems.append(f"{name} / {ch}: no message ({out['next_action'].get('reason')})")
                continue
            ok = out["meta"].get("required_states", {}).get("brand_style_applied")
            lines.append(f"    {ch:<5} {'✓' if ok else '✗'} {msg['body'][:110].replace(chr(10), ' / ')}…")
            if not ok:
                problems.append(f"{name} / {ch}: brand check failed")
    return problems, lines


def main() -> int:
    ok = True
    try:
        r = config.rules()
        print(f"✓ rules      {config.rules_source()}")
        print(f"             send hours {r['channels']['send_hour']}, legal window {r['channels']['legal_window']}, "
              f"horizon threshold {r['next_action']['horizon_threshold_days']}, {len(r['cta']) - 1} CTA types")
        print(f"✓ brand      defaults (rules.yaml brand_default): {len(r['brand_default'].get('banned_phrases', []))} banned phrases, "
              f"max {r['brand_default'].get('max_sms_chars')} SMS chars, max {r['brand_default'].get('max_voice_words')} voice words")
    except RulesError as e:
        print(f"✗ rules      INVALID\n{e}")
        ok = False
    try:
        langs = config.templates()
        print(f"✓ templates  {', '.join(f'{k} ({v['name']})' for k, v in langs.items())}: complete, placeholders valid, "
              "opt-outs present")
    except RulesError as e:
        print(f"✗ templates  INVALID\n{e}")
        return 1
    raw = yaml.safe_load((config.CONFIG_DIR / "properties.yaml").read_text()) or {}
    prob = validate_properties(raw, set(langs))
    if prob:
        print("✗ properties INVALID (facts or brand)\n  - " + "\n  - ".join(prob))
        ok = False
    else:
        branded = sum(1 for f in raw.values() if isinstance(f, dict) and f.get("brand"))
        print(f"✓ properties {len(raw)} propert(y/ies); {branded} with their own brand profile (overrides brand_default)")
    if ok and "--brand" in sys.argv:
        problems, lines = brand_preview()
        print("\nBRAND PREVIEW: a tour message per property and channel, brand-checked")
        print("\n".join(lines))
        if problems:
            print("✗ brand      " + "; ".join(problems))
            ok = False
        else:
            print("✓ brand      every property renders on-brand on every channel")
    print("VALID" if ok else "INVALID")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

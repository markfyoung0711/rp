"""Finds personal data in an INPUT record, so the run can report what was withheld (redacted) from the output.

Only counts and categories leave this module, never values. The first name is not counted: it is
used on purpose, in the greeting.
"""
import json
import re

from . import guards

KEY_CATEGORIES = [
    ("email", r"e[-_]?mail"),
    ("phone", r"phone|mobile|cell|tel\b|telephone"),
    ("SSN / national ID", r"ssn|social|national_?id|tax_?id|passport|license"),
    ("date of birth", r"dob|birth"),
    ("address", r"address|street|zip|postal"),
    ("last name", r"last_?name|surname|family_?name|full_?name"),
    ("payment card / bank", r"card|credit|iban|account_?number|routing"),
]
PROTECTED_KEYS = r"child|kid|famil|religio|disab|race|ethnic|national_?origin|gender|pregnan|marital|age\b|veteran"
SKIP_KEYS = {"task_id", "first_name", "expected", "_ingest", "property_name", "timezone", "language",
             "last_interaction", "move_date_target", "lifecycle_stage", "persona", "channel_preferences"}


def _walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v, path)
    else:
        yield path, obj


def find(record: dict) -> tuple[dict[str, list[str]], int]:
    """({category: [values]}, protected_detail_count) found in the input, excluding fields we use on purpose."""
    found: dict[str, list[str]] = {}
    protected = 0
    for path, value in _walk(record):
        key = path.rsplit(".", 1)[-1].lower()
        top = path.split(".", 1)[0].lower()
        if key in SKIP_KEYS or top in ("expected", "assertions", "thresholds", "consent"):
            continue
        if value in (None, "", False):
            continue
        text = str(value)
        category = next((c for c, pat in KEY_CATEGORIES if re.search(pat, key)), None)
        if category:
            found.setdefault(category, []).append(text)
            continue
        if re.search(PROTECTED_KEYS, key) or guards.protected_hits(text):
            protected += 1
        for hit, pat in (("email", guards.EMAIL), ("phone", guards.PHONE), ("SSN / national ID", guards.SSN),
                         ("payment card / bank", guards.CARD)):
            for m in pat.finditer(guards.URL.sub("", text)):
                found.setdefault(hit, []).append(m.group(0))
    # A first name that is really an email, phone or ID is also personal data (it is rejected, not used).
    first = str(((record.get("input") or {}).get("profile") or {}).get("first_name") or "")
    for hit, pat in (("email", guards.EMAIL), ("phone", guards.PHONE), ("SSN / national ID", guards.SSN)):
        for m in pat.finditer(first):
            found.setdefault(hit, []).append(m.group(0))
    return found, protected


def audit(record: dict, output: dict) -> dict:
    """Counts only: what personal data the input had, and whether any of it reached the output."""
    found, protected = find(record)
    out_text = json.dumps({k: v for k, v in output.items() if k != "task_id"}, ensure_ascii=False)
    withheld: dict[str, int] = {}
    leaked: dict[str, int] = {}
    for cat, values in found.items():
        for v in dict.fromkeys(values):                      # unique values per category
            target = leaked if v and v in out_text else withheld
            target[cat] = target.get(cat, 0) + 1
    return {"withheld": withheld, "leaked": leaked, "protected_withheld": protected}


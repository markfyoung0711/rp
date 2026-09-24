"""Generate N varied synthetic records (deterministic) for performance and robustness runs.

  uv run python scripts/gen_records.py 100 > tests/perf_100.jsonl
"""
import json
import random
import sys
from datetime import datetime, timedelta, timezone

NAMES = ["Taylor", "Jordan", "Priya", "Lucía", "Sam", "Riley", "Zoë", "Ahmed", "Mei", "Chris", "José", "Ana"]
PROPS = ["Oak Ridge Apartments", "Maple Court", "Cedar Point Lofts", "oak ridge apartments"]
TZS = ["America/Chicago", "America/New_York", "America/Denver", "America/Phoenix", "America/Los_Angeles", "Central", ""]
PERSONAS = [("prospect", "new", "book_tour"), ("prospect", "open", "book_tour"), ("applicant", "open", "apply_now"),
            ("resident", "active", "pay_rent"), ("resident", "renewal", "renew_lease"), ("prospect", "new", "refer_a_friend")]
CHANNELS = ["sms", "email", "voice"]


def record(i: int, rng: random.Random) -> dict:
    persona, stage, cta = rng.choice(PERSONAS)
    prefs = rng.sample(CHANNELS, k=rng.randint(1, 3))
    consent = {f"{c}_opt_in": rng.random() < 0.7 for c in CHANNELS}
    last = datetime(2025, 12, 1, tzinfo=timezone.utc) + timedelta(minutes=rng.randint(0, 60 * 24 * 20))
    move = last.date() + timedelta(days=rng.randint(-5, 120))
    profile = {"first_name": rng.choice(NAMES)}
    if rng.random() < 0.5:
        profile["amenity_interest"] = rng.sample(["pool", "fitness", "gym", "rooftop"], k=rng.randint(1, 2))
    if rng.random() < 0.1:
        profile["notes"] = "Moving with my 3 kids, near a church please"       # fair-housing trap
    offset = rng.choice([f"_day{rng.randint(0, 7)}", ""])
    return {
        "task_id": f"perf_{i:04d}_{persona}_{stage}{offset}",
        "persona": persona,
        "lifecycle_stage": stage,
        "consent": consent,
        "channel_preferences": prefs,
        "input": {
            "property_name": rng.choice(PROPS),
            "move_date_target": move.isoformat(),
            "last_interaction": last.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timezone": rng.choice(TZS),
            "language": "es" if rng.random() < 0.15 else "en",
            "profile": profile,
        },
        "assertions": {"constraints": {"include_opt_out_instructions": True, "primary_cta": cta}},
    }


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    rng = random.Random(42)
    for i in range(n):
        print(json.dumps(record(i, rng), ensure_ascii=False))

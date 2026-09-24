import asyncio
import json
from pathlib import Path

import pytest

from outreach.pipeline import process
from outreach.reader import ReadError, read_records

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = (ROOT / "plans" / "sample.jsonl").read_text()
EDGES = (ROOT / "tests" / "edge_cases.jsonl").read_text()


def run(text: str, **kw) -> list[dict]:
    recs = read_records(text)

    async def go():
        return await asyncio.gather(*(process(r, **kw) for r in recs))
    return asyncio.run(go())


def by_id(results):
    return {r["task_id"]: r for r in results}


@pytest.mark.parametrize("rec", [json.loads(l) for l in SAMPLES.splitlines() if l.strip()], ids=lambda r: r["task_id"])
def test_samples_match_every_field(rec):
    out = run(json.dumps(rec))[0]
    assert out["next_message"] == rec["expected"]["next_message"]
    assert out["next_action"] == rec["expected"]["next_action"]


def test_deterministic():
    def strip(rs):  # latency differs run to run; the missing-timestamp case uses the clock by design
        return [{k: v for k, v in r.items() if k != "meta"} for r in rs if r["task_id"] != "edge_level2_missing_fields"]
    assert strip(run(SAMPLES + EDGES)) == strip(run(SAMPLES + EDGES))


def test_edge_cases_never_crash_and_are_safe():
    results = run(EDGES)
    assert len(results) == len(read_records(EDGES))
    for r in results:
        msg = r["next_message"]
        if msg:
            assert "STOP" in msg["body"], r["task_id"]
            assert msg["channel"] in ("sms", "email")
            assert (msg["subject"] is None) == (msg["channel"] == "sms")


def test_specific_edges():
    r = by_id(run(EDGES))
    assert r["edge_no_consent_day0"]["next_message"] is None
    assert r["edge_voice_only_day1"]["next_message"] is None
    assert r["edge_inbound_stop_day1"]["next_message"] is None
    assert r["edge_sms_preferred_not_consented_day0"]["next_message"]["channel"] == "email"
    kids = r["edge_fair_housing_kids_day0"]["next_message"]["body"].lower()
    assert "kid" not in kids and "daycare" not in kids
    assert r["edge_injection_name_day0"]["next_message"]["body"].startswith("Hi there")
    assert "renov" in r["edge_renewal_es_day0"]["next_message"]["body"]
    assert "$" not in r["edge_renewal_es_day0"]["next_message"]["body"]
    assert r["edge_unknown_cta_phoenix_day1"]["next_message"]["send_at"].endswith("-07:00")
    assert r["edge_malformed"]["next_action"]["type"] == "human_review"
    assert r["MISC-1"]["next_message"] is None


def test_reader_formats():
    one = json.loads(SAMPLES.splitlines()[0])
    assert len(read_records(json.dumps([one, one]))) == 2          # JSON array
    assert len(read_records(json.dumps(one, indent=2) * 2)) == 2    # pretty-printed, concatenated
    mixed = read_records(SAMPLES.splitlines()[0] + "\n{broken\n" + SAMPLES.splitlines()[1])
    assert [type(x) for x in mixed] == [dict, ReadError, dict]

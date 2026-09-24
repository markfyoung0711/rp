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


GARBAGE = (ROOT / "tests" / "garbage_inputs.txt").read_text(encoding="utf-8")


def test_garbage_file_reads_every_repairable_record():
    from outreach.reader import read_batch
    batch = read_batch(GARBAGE)
    ids = [(r.get("task_id") or r.get("Task_ID")) if isinstance(r, dict) else r.task_id for r in batch.records]
    for tid in ["g_numbered_line_day0", "g_smart_quotes_day0", "g_trailing_comma_day0", "g_python_repr_day0",
                "g_double_encoded_day0", "g_array_line_a_day0", "g_array_line_b_day0", "g_input_as_string_day0",
                "g_nbsp_day0", "g_zero_width_day0", "g_pretty_day0", "g_after_garbage_day0"]:
        assert tid in ids, tid
    assert any(isinstance(r, ReadError) and r.task_id == "g_truncated_day0" for r in batch.records)
    assert any("Task_ID" in str(r) for r in batch.records if isinstance(r, dict))  # key variant kept for normalize
    results = run(GARBAGE)
    sent = [r for r in results if r["next_message"]]
    assert len(sent) == 13 and all("STOP" in r["next_message"]["body"] for r in sent)


def test_byte_level_garbage_never_raises():
    import os
    from outreach.reader import decode_bytes, read_batch
    utf16 = (ROOT / "tests" / "garbage_utf16.jsonl").read_bytes()
    text, notes = decode_bytes(utf16)
    assert len(read_batch(text).records) == 2 and notes
    from outreach.reader import UnsupportedInput
    for blob in (os.urandom(4000), b"\xff\xfe\x00junk\x80", b"", b"[" * 50000, "{\u201ctask_id\u201d: 1}".encode("cp1252", "replace")):
        try:
            text, _ = decode_bytes(blob)
        except UnsupportedInput:
            continue               # refused cleanly is fine; raising anything else is not
        read_batch(text)   # must not raise


def test_images_and_archives_are_refused_clearly():
    import pytest
    from outreach.reader import UnsupportedInput, decode_bytes
    for blob, word in ((b"\x89PNG\r\n\x1a\n" + bytes(200), "PNG"), (b"%PDF-1.7 ...", "PDF"),
                       (b"PK\x03\x04" + bytes(50), "ZIP"), (b"\xff\xd8\xff\xe0" + bytes(50), "JPEG")):
        with pytest.raises(UnsupportedInput, match=word):
            decode_bytes(blob)


def test_no_pii_in_any_output_field():
    """Planted personal data (profile, top-level fields, and the first-name field) must never appear anywhere in the output."""
    text = (ROOT / "tests" / "pii_cases.jsonl").read_text()
    planted = ["Okafor", "taylor.okafor@example.com", "555-0187", "555 0187", "123-45-6789", "1990-04-12", "1200 Elm", "4111 1111"]
    for r in run(text):
        blob = json.dumps(r, ensure_ascii=False)
        assert not [p for p in planted if p in blob], (r["task_id"], [p for p in planted if p in blob])
        if r["next_message"]:
            assert r["next_message"]["body"].startswith(("Hi Taylor", "Hi there"))

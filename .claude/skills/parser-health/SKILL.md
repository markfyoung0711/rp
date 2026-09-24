---
name: parser-health
description: Parser / source-data health checks — fingerprint coverage, extraction completeness, staged-layer hygiene, source identity, and golden coverage. Answers "can we actually read what we have, and does what we read reach the spine". Triggered by phrases like "parser health", "source data health checks", "parser health check", "can we read our sources", "fingerprint coverage", "which parsers are missing", "extraction completeness".
allowed-tools: Bash, Read, Write
---

# Parser / source data health checks

Six checks. Each is independent — run one or all. Report findings, do not fix silently.

The governing rule (`CLAUDE.md` → "Fingerprint-first parsing, and fail LOUDLY") is what checks 1
and 2 enforce. Everything else exists because a source can be perfectly parsed and still never
reach the spine.

---

## Check 1 — Fingerprint → parser coverage

**The rule.** Every file entering the parse path is fingerprinted, and the fingerprint selects the
parser. Four outcomes, one success:

| outcome | verdict |
|---|---|
| fingerprint generated, format matched, parser wired | OK |
| fingerprint generated, format matched, **no parser wired** | **complain loudly** |
| fingerprint generated, **no format matched** | **complain loudly** |
| **no fingerprint could be generated** | **complain loudly** |

"Complain loudly" = a `defect_log` record **plus** a surfaced, non-silent result. Never a quiet
fall-through to a generic reader that returns a confident-looking answer.

```
uv run python scripts/run_recognition_coverage.py
```

Reads `data/reviews/recognition_coverage.csv` / `.md`. Report per format: recognized-with-parser,
recognized-no-parser, unrecognized. The last two are the parser-wiring backlog.

## Check 2 — Extraction completeness (recognition confidence is NOT extraction confidence)

A file can match a format at **confidence 1.0** and still come back with half its columns empty.
That is an extraction failure wearing a success badge, and nothing currently notices it.

For a sample of files per format, parse and assert that required columns are not *structurally*
empty:

```
uv run python -c "
from pathlib import Path
from src.api.bid_schedule_upload import recognize_and_parse
p = Path('<file>')
r = recognize_and_parse(p.name, p.read_bytes())
its = r.items or []
n = len(its)
for col in ('unit','item_code','quantity','description'):
    miss = sum(1 for i in its if not (i.get(col) if isinstance(i,dict) else getattr(i,col,None)))
    flag = '  <-- STRUCTURAL FAILURE' if n and miss == n else ''
    print(f'{col:18} {miss}/{n} empty{flag}')
"
```

**100% empty on a required column is a failure, not a warning** — but FIRST confirm you are reading
the right field names. The product contract is `PayItemDraft`: **`item_code`, `description`, `unit`,
`quantity`** (plus `low_unit_price`, `engineers_estimate_unit_price`, `bids` on a priced tabulation).
There is no `unit_of_measure` and no `line_number`. Asking for names that do not exist returns None
for every row and makes a healthy parser look catastrophically broken — that happened on 2026-09-08
and produced a day of wrong conclusions. `scripts/parser_review.py` now raises if none of the
requested fields exist on the item rather than reporting empty columns.

*Reference finding, 2026-09-08:* the real defect on that EEI tabulation was narrow — a `TOTAL BID`
summary row ingested as a pay item (60 rows against the document's 59), and an unhandled `IndexError`
on a sibling document (jpy_estimator#90). Units and item codes parsed correctly. The dramatic
"0/60 units" reading was an artifact of querying non-existent field names, which is exactly why this
check now verifies the contract before trusting a zero.

## Check 3 — Staged-layer hygiene

`data/staged/` holds **parsed output**. Source documents there are a dead end: consumers glob
`data/staged/**/*.parquet` and never see them.

```
for d in data/staged/*/; do
  pq=$(find "$d" -name '*.parquet' | wc -l)
  src=$(find "$d" \( -name '*.pdf' -o -name '*.xlsx' -o -name '*.doc*' \) | wc -l)
  [ "$src" -gt 0 ] && echo "SOURCE DOCS IN STAGED: $(basename $d) | parquet $pq | source $src"
done
```

Flag any directory with source documents, and especially any with **zero parquet** — that tree has
never been parsed and contributes nothing.

## Check 4 — Does staged data actually reach the spine?

A tree can be full and still be invisible downstream.

```
uv run python -c "
import duckdb; con = duckdb.connect()
S = \"read_parquet('data/warehouse/training_spine.parquet')\"
print(con.execute(f'SELECT source, count(*) n, count(DISTINCT contract_id) contracts, min(letting_date) first, max(letting_date) last FROM {S} GROUP BY 1 ORDER BY n DESC').df().to_string(index=False))
"
```

Then, for a source under suspicion, take the document ids present in `data/staged/` and check each
against `SELECT DISTINCT contract_id`. Anything staged but absent from the spine is acquired,
stored, and unused.

*Reference finding, 2026-09-08:* **7 of 11** Yorkville QuestCDN tabulation PDFs were absent from the
spine, including the Faxon Road letting. The four present were exactly the four that also existed as
parquet under the other naming convention (jpy_estimator#89).

## Check 5 — Source identity: collapsed and split

Two opposite failures, both real:

- **Collapsed** — one `source` value covering many agencies, with no column to recover the agency
  from. `questcdn_bid_tabulations` spans ~60 municipalities and ~89 contracts as a single
  identifier; Yorkville comps are indistinguishable from Batavia comps. A QuestCDN source should be
  `questcdn_<town>_<state>`, matching the per-town staged trees.
- **Split** — one agency under two naming conventions, so it reads as two sources and overlapping
  documents risk double-counting.

```
ls -d data/staged/*/ | sed 's|.*/||' | sed -E 's/-(il|tx|wi|in|ia|mo|ny|oh)-/-<ST>-/' | sort
```

Eyeball for two shapes of the same acquisition source. Then check for the same document id appearing
under both.

## Check 6 — Golden coverage per parser

Every distinct source should have a `tests/golden/parsers/<source>.golden.csv` pinning its output.

```
ls tests/golden/parsers/ | sed 's/\.golden\.csv//' | sort > /tmp/goldens.txt
ls src/parsers/ | sed 's/\.py$//' | grep -v '^__' | sort > /tmp/parsers.txt
echo "--- parsers with NO golden ---"; comm -23 /tmp/parsers.txt /tmp/goldens.txt
```

A parser with no golden can drift silently — which is the failure mode that matters most for a
scheduled scraper, because the agency changes its template and nobody finds out.

---

## Reporting

Write findings, do not fix. For anything that fails:

1. State the check, the count, and one concrete example.
2. Say whether it is *unreadable* (checks 1-2), *unreachable* (checks 3-4), *misidentified*
   (check 5), or *unpinned* (check 6) — the four have different fixes.
3. File or update a GitHub issue via the `gh-connect` skill rather than fixing in place, unless the
   fix is a one-liner the user has approved.

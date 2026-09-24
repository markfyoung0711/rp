---
name: train-parser
description: Validate one parser against one real document, side by side — run the parser, render the source and the parsed rows in a local two-pane page, read it as a human, then pin the result as a golden fixture. Use when a parser is new, suspect, or being compared against a candidate reader. Triggered by phrases like "train a parser", "train parser", "validate a parser", "check this parser", "parser side by side", "review the parse", "does the parser read this file", "pin a golden".
allowed-tools: Bash, Read, Write, Edit
---

# Train a parser

One parser, one document, read by a human. The tool is `scripts/parser_review.py`; this skill is
the loop around it.

**Local by design.** The source is referenced by `file://`, not embedded, so a 39 MB bid-docs PDF
costs nothing. (An Artifact would have to inline it as a data: URI against a 16 MB cap.)

## 0. First decide whether a parser is warranted at all

**Do not write candidate parser code — not even a scratch prototype — until this is settled.** The
fingerprint outcome decides what kind of fix this is, and writing code first biases the answer
toward "new parser" because the code already exists.

| what the fingerprint says | the fix |
|---|---|
| matched a format **with** a wired parser, but the rows are wrong | **fix that parser's geometry.** No new file. |
| matched a format, but this is a distinct template inside it (a different engineer of record) | **add a fingerprint** for the template, per the EOR convention — then decide whether it needs its own extractor or a variant of the existing one |
| matched no format | **complain loudly**, then a new format + parser is on the table |
| no fingerprint could be generated | **complain loudly** — a new source, and the fingerprint comes first |

Only the bottom two rows earn a new parser file. Establish which row you are in — check 1 of the
`parser-health` skill — before writing anything.

*Reference: on 2026-09-08 a candidate reader was prototyped before this call was made. It turned out
useful, but the determination should have come first: an EEI template inside
`municipal.bid_tabulation_pdf` is row two, and the honest question was whether EEI needs its own
extractor or just its own fingerprint plus a geometry fix.*

## 1. Run the shipped path first

Always establish what the product currently does before proposing anything.

```
uv run python scripts/parser_review.py <file>
```

Prints the health verdict and writes `logs/parser-review-<stem>.html`. Open it and put the two
panes side by side: source on the left, parsed rows on the right, empty cells shaded.

The header carries `format_id`, `extractor`, `fingerprint`, `confidence` — read these. **A confident
match is not a good parse.** Per `CLAUDE.md`, a required column that is 100% empty is a structural
FAILURE even at confidence 1.0, and the page says so in the banner.

## 2. Read the page as a human

Walk the rows against the document. What to look for, in the order it usually goes wrong:

- **Row count** — does it match the document's own total line ("TOTAL (Items 1 - 59)")? Over-count
  usually means the reader ran past the schedule into a summary or footer.
- **First and last rows** — the ends are where boundary bugs live.
- **Rows with an empty cell** (shaded) — one empty is a document quirk; a whole empty column is a
  geometry failure.
- **Interior digits** — descriptions like `RESTORATION, TYPE 2` or `TREE REMOVAL (6 TO 15 UNITS)`
  break readers that take the rightmost number as the item number.
- **Page furniture** — a footer such as `52 WHEELER ROAD, SUGAR GROVE` parses as item 52 if the
  item-number column band is loose.
- **Units** — a centred column header does not bound a left-aligned column, and `UNIT` may appear
  once as the unit-of-measure header and again per bidder as `UNIT PRICE`.

## 3. Compare a candidate reader against the same document

```
uv run python scripts/parser_review.py <file> --extractor <module>:<fn> \
    --out logs/parser-review-<stem>-candidate.html
```

`<fn>` takes a path and returns rows with `line_number`, `description`, `unit_of_measure`,
`quantity`. Open both pages next to each other — shipped versus candidate, same document. This is
how a prototype earns its way into `src/parsers/` rather than being asserted into it.

## 4. Pin it

Only after a human has read the page:

```
uv run python scripts/parser_review.py <file> --golden tests/golden/parsers/<source>.golden.csv
```

A parser with no golden drifts silently — which is the failure that matters most for a scheduled
scraper, because the agency changes its template and nobody finds out. Run
`parser-health` check 6 to see which parsers are still unpinned (19 of 39 as of 2026-09-08).

## 5. If the parse was wrong, say why in the right place

- Geometry or boundary bug in a wired parser → GitHub issue with the word positions
  (`pdfplumber.extract_words()` x0/x1/top) that prove it. Vague "it drops the unit" reports are not
  actionable; `UNIT x0=259.2 vs UNIT PRICE x0=323.9` is.
- Recognized format with **no** wired parser, or no fingerprint at all → that is the fingerprint-first
  rule in `CLAUDE.md`; it must complain loudly rather than fall through to a generic reader.
- Fingerprint keyed on the delivery channel rather than the template author → the engineer of record
  needs its own fingerprint (see `feedback_eor_template_fingerprints`).

## Worked example

`data/staged/questcdn-bid-tabulation-yorkville-il/20250509/9641818.pdf` — an EEI bid tabulation,
jpy_estimator#90.

| | rows | verdict |
|---|---|---|
| shipped (`questcdn_tabulation`) | 60 | **WARN** — ingests a `TOTAL BID` summary row as item 60; units and item codes correct |
| candidate (bidder-band anchor) | 59 | **OK** — stops at `TOTAL (Items 1 - 59)` |

**The cautionary half of this example matters more than the fix.** The first review of this document
reported *60/60 units empty, 60/60 line numbers empty* and drove a day of work — issues, a hard rule,
a re-parse — before anyone checked the field names. The product contract is `item_code` / `unit`;
the review was asking for `line_number` / `unit_of_measure`, which do not exist, so every value came
back None. A working parser read as catastrophically broken.

**Before believing a 100%-empty column, print one raw item and look at its actual keys.** The tool now
raises instead of reporting empties when none of the requested fields exist, but the habit is the real
guard.

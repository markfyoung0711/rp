#!/usr/bin/env python3
"""Profile an unknown JSONL file and guess what role it plays in the chatbot.

Usage:
    python profile_jsonl.py data/samples/utterances.jsonl
    python profile_jsonl.py data/*.jsonl --samples 3

Roles (see guessing.md):
    grounding  - records the bot must look up  -> becomes tools
    knowledge  - FAQ / policy text             -> becomes a retrieval tool
    examples   - utterances or transcripts     -> becomes few-shot prompts and eval cases
    taxonomy   - intents, terms, categories    -> becomes router labels and glossary
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Key names that hint at each role. Matched as substrings of the flattened key path.
ROLE_HINTS: dict[str, tuple[str, ...]] = {
    "examples": ("text", "utterance", "turns", "message", "body", "transcript",
                 "conversation", "query", "prompt", "response", "reply"),
    "knowledge": ("question", "answer", "article", "content", "source", "faq",
                  "policy", "rule", "document"),
    "taxonomy": ("intent", "label", "category", "term", "synonym", "definition",
                 "tag", "class", "topic", "slot", "entity"),
    "grounding": ("_id", "amount", "balance", "date", "status", "unit", "resident",
                  "account", "charge", "payment", "lease", "order", "ticket",
                  "phone", "email", "rent", "deposit"),
}

# Hints that appear in nearly every file and so say little about the role.
WEAK_HINTS = {"_id", "date", "status", "category", "source", "content", "topic"}
WEAK_WEIGHT = 0.3

MAX_UNIQUE_TRACKED = 50
SCALARS = (str, int, float, bool)


def flatten(obj, prefix: str = "") -> dict[str, object]:
    """Flatten nested dicts into dotted paths. Lists collapse to '<key>[]'."""
    flat: dict[str, object] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                flat.update(flatten(value, path))
            elif isinstance(value, list):
                flat[f"{path}[]"] = value
                for item in value:
                    if isinstance(item, dict):
                        flat.update(flatten(item, f"{path}[]"))
            else:
                flat[path] = value
    return flat


def type_name(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


class Profile:
    def __init__(self, path: Path):
        self.path = path
        self.records = 0
        self.bad_lines: list[tuple[int, str]] = []
        self.top_level_types: Counter = Counter()
        self.key_counts: Counter = Counter()
        self.key_types: defaultdict[str, Counter] = defaultdict(Counter)
        self.key_values: defaultdict[str, set] = defaultdict(set)
        self.key_overflow: set[str] = set()
        self.samples: list[dict] = []
        self.discriminator: str | None = None

    def add(self, record: dict) -> None:
        self.records += 1
        self.top_level_types[type_name(record)] += 1
        if not isinstance(record, dict):
            return
        for key, value in flatten(record).items():
            self.key_counts[key] += 1
            self.key_types[key][type_name(value)] += 1
            if isinstance(value, SCALARS) and key not in self.key_overflow:
                bucket = self.key_values[key]
                bucket.add(value)
                if len(bucket) > MAX_UNIQUE_TRACKED:
                    self.key_overflow.add(key)
                    bucket.clear()

    # --- reporting -------------------------------------------------------

    def find_discriminator(self) -> str | None:
        """A low-cardinality key present on every record, e.g. 'type' or 'record_type'."""
        best = None
        for key, count in self.key_counts.items():
            if count != self.records or key in self.key_overflow:
                continue
            values = self.key_values[key]
            if 1 < len(values) <= 12 and all(isinstance(v, str) for v in values):
                score = (key in ("type", "record_type", "kind", "intent", "category"),
                         -len(values))
                if best is None or score > best[0]:
                    best = (score, key)
        self.discriminator = best[1] if best else None
        return self.discriminator

    def score_roles(self) -> list[tuple[str, float, list[str]]]:
        """Score each role by which keys appear, weighted by how often they are filled.

        Extracted entity slots (entities.amount, slots.date) describe an example, not a
        record, so they never count toward grounding.
        """
        scores: list[tuple[str, float, list[str]]] = []
        for role, hints in ROLE_HINTS.items():
            matched: list[str] = []
            total = 0.0
            for key, count in self.key_counts.items():
                lowered = key.lower()
                if role == "grounding" and ("entities" in lowered or "slots" in lowered):
                    continue
                leaf = lowered.split(".")[-1].replace("[]", "")
                hit = next((h for h in hints if h in leaf or (h == "_id" and leaf == "id")),
                           None)
                if hit:
                    matched.append(key)
                    weight = WEAK_WEIGHT if hit in WEAK_HINTS else 1.0
                    total += weight * count / max(self.records, 1)
            scores.append((role, total, sorted(matched)[:8]))
        scores.sort(key=lambda row: row[1], reverse=True)
        return scores

    def report(self, sample_count: int) -> None:
        print(f"\n{'=' * 70}\n{self.path}\n{'=' * 70}")
        size_kb = self.path.stat().st_size / 1024
        print(f"records: {self.records}   size: {size_kb:.1f} KB", end="")
        if self.bad_lines:
            print(f"   unparseable lines: {len(self.bad_lines)}")
            for line_no, err in self.bad_lines[:3]:
                print(f"    line {line_no}: {err}")
        else:
            print()
        if self.records == 0:
            return
        if set(self.top_level_types) != {"dict"}:
            print(f"top-level types: {dict(self.top_level_types)}")

        print("\nkeys")
        print(f"  {'key':<34} {'fill':>6}  {'types':<18} values")
        for key, count in sorted(self.key_counts.items(),
                                 key=lambda kv: (-kv[1], kv[0])):
            fill = f"{100 * count / self.records:.0f}%"
            types = ",".join(sorted(self.key_types[key]))
            if key in self.key_overflow:
                values = f">{MAX_UNIQUE_TRACKED} distinct"
            else:
                uniq = self.key_values[key]
                preview = ", ".join(repr(v)[:24] for v in sorted(uniq, key=str)[:4])
                values = f"{len(uniq)} distinct" + (f": {preview}" if len(uniq) <= 8 else "")
            print(f"  {key:<34} {fill:>6}  {types:<18} {values}")

        disc = self.find_discriminator()
        if disc:
            counts = Counter()
            for record in self.samples_all:
                value = record.get(disc) if isinstance(record, dict) else None
                if isinstance(value, str):
                    counts[value] += 1
            print(f"\nlikely discriminator: '{disc}' -> {dict(counts.most_common())}")

        print("\nrole guess")
        scores = self.score_roles()
        top = scores[0][1] or 1.0
        for role, score, matched in scores:
            bar = "#" * int(round(20 * score / top)) if score else ""
            print(f"  {role:<10} {score:6.2f} {bar:<20} {', '.join(matched)}")
        print(f"\n  -> build it as: {BUILD_ADVICE[scores[0][0]]}")
        if len(scores) > 1 and scores[1][1] > 0.6 * scores[0][1]:
            print(f"  -> also carries: {BUILD_ADVICE[scores[1][0]]}")

        print("\nsamples")
        for record in self.samples[:sample_count]:
            text = json.dumps(record, ensure_ascii=False)
            print(f"  {text[:300]}{'...' if len(text) > 300 else ''}")


BUILD_ADVICE = {
    "grounding": "lookup tools over a SQLite table (get_x by id, scoped to the session)",
    "knowledge": "a search_kb retrieval tool; answers must cite these entries",
    "examples": "few-shot prompts plus eval cases (expected intent, tools, facts)",
    "taxonomy": "router labels, entity types and the reply glossary",
}


def profile_file(path: Path, sample_count: int) -> Profile:
    prof = Profile(path)
    prof.samples_all = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as err:
                prof.bad_lines.append((line_no, str(err)))
                continue
            prof.add(record)
            prof.samples_all.append(record)
            if len(prof.samples) < 10:
                prof.samples.append(record)
    return prof


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--samples", type=int, default=2,
                        help="sample records to print per file (default 2)")
    args = parser.parse_args()

    missing = [p for p in args.paths if not p.is_file()]
    for path in missing:
        print(f"not a file: {path}", file=sys.stderr)
    for path in args.paths:
        if path.is_file():
            profile_file(path, args.samples).report(args.samples)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())

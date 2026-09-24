"""Reads records from JSONL, a JSON array, or concatenated / pretty-printed JSON objects.

A malformed record never stops the batch: it becomes a ReadError that the pipeline turns into
a safe no-send with a reason.
"""
import json
import re
from dataclasses import dataclass


@dataclass
class ReadError:
    line: int
    message: str
    snippet: str

    @property
    def task_id(self) -> str:
        m = re.search(r'"task_id"\s*:\s*"([^"]+)"', self.snippet)
        return m.group(1) if m else f"unreadable_line_{self.line}"


def read_records(text: str) -> list[dict | ReadError]:
    text = text.lstrip("﻿")
    stripped = text.strip()
    if not stripped:
        return []

    # A single JSON document: an array of records, or one object.
    try:
        doc = json.loads(stripped)
        items = doc if isinstance(doc, list) else [doc]
        return [i if isinstance(i, dict) else ReadError(1, "record is not a JSON object", str(i)[:200]) for i in items]
    except json.JSONDecodeError:
        pass

    # Otherwise scan object by object; on a bad object, skip to the next line and keep going.
    decoder = json.JSONDecoder()
    out: list[dict | ReadError] = []
    pos, n = 0, len(text)
    while pos < n:
        while pos < n and text[pos] in " \t\r\n,":
            pos += 1
        if pos >= n:
            break
        line = text.count("\n", 0, pos) + 1
        try:
            obj, end = decoder.raw_decode(text, pos)
            out.append(obj if isinstance(obj, dict) else ReadError(line, "record is not a JSON object", text[pos:end][:200]))
            pos = end
        except json.JSONDecodeError as e:
            # Resume at the next line that starts a new object, so one broken multi-line
            # record doesn't turn into a cascade of errors.
            nxt = re.compile(r"\n[ \t]*\{").search(text, pos + 1)
            end = n if nxt is None else nxt.start()
            out.append(ReadError(line, f"invalid JSON: {e.msg}", text[pos:end][:200]))
            pos = end
    return out

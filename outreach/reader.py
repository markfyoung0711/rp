"""Garbage-tolerant record reader.

Accepts JSONL, a JSON array, a wrapper object ({"records": [...]}), or concatenated / pretty-printed
objects, and survives what people actually paste:
  - byte-level: UTF-8 with or without BOM, UTF-16 (Windows exports), invalid bytes, CRLF
  - text-level: markdown code fences, comment lines (# or //), prose or numbering between records,
    zero-width characters
  - record-level repairs: smart quotes, trailing commas, non-breaking spaces, Python-style dicts
    (single quotes, True/False/None), double-encoded JSON strings, arrays of records on one line
A record that still can't be read becomes a ReadError (a safe no-send with a reason); it never
stops the batch. Every repair is noted on the record (`_ingest`) so the output says what was fixed.
"""
import ast
import json
import re
from dataclasses import dataclass, field

ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff"), None)
FENCE = re.compile(r"^[ \t]*```[^\n]*$", re.M)
COMMENT = re.compile(r"^[ \t]*(#|//)[^\n]*$", re.M)
WRAPPER_KEYS = {"records", "data", "items", "cases", "rows", "holdout", "tasks", "results", "inputs"}
RECORD_HINT_KEYS = {"task_id", "consent", "channel_preferences", "input", "persona", "lifecycle_stage"}
MAX_SNIPPET = 200


@dataclass
class ReadError:
    line: int
    message: str
    snippet: str

    @property
    def task_id(self) -> str:
        m = re.search(r"""["'“”]task_id["'“”]\s*:\s*["'“”]([^"'“”]+)""", self.snippet)
        return m.group(1) if m else f"unreadable_line_{self.line}"


@dataclass
class Batch:
    records: list = field(default_factory=list)
    notes: list = field(default_factory=list)      # batch-level notes (ignored text, decoding, ...)


class UnsupportedInput(Exception):
    """The input is not text records at all (an image, a PDF, an archive, binary data)."""


MAGIC = [(b"\x89PNG\r\n\x1a\n", "a PNG image"), (b"\xff\xd8\xff", "a JPEG image"), (b"GIF8", "a GIF image"),
         (b"RIFF", "a WebP/RIFF file"), (b"%PDF", "a PDF document"), (b"PK\x03\x04", "a ZIP archive (or .docx/.xlsx)"),
         (b"\x1f\x8b", "a gzip archive"), (b"\xd0\xcf\x11\xe0", "a legacy Office document"), (b"BM", None)]


def _mostly_text(text: str) -> bool:
    if not text:
        return True
    sample = text[:4000]
    bad = sum(1 for ch in sample if (ord(ch) < 32 and ch not in "\t\n\r") or ch == "\ufffd"
              or 0xE000 <= ord(ch) <= 0xF8FF)
    return bad / len(sample) < 0.05


def decode_bytes(data: bytes) -> tuple[str, list[str]]:
    """Bytes to text, whatever the encoding. Raises UnsupportedInput for images, archives and binary data."""
    for magic, kind in MAGIC:
        if kind and data.startswith(magic):
            raise UnsupportedInput(f"the input is {kind}, not JSON records")
    notes: list[str] = []
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16", errors="replace")
        notes.append("input was UTF-16; decoded")
    elif len(data) >= 4 and data[1:200:2].count(0) > 0.4 * len(data[1:200:2]) and data[0:200:2].count(0) < 3:
        text = data.decode("utf-16-le", errors="replace")          # UTF-16 without a BOM: ASCII + NUL pairs
        notes.append("input looked like UTF-16 without a BOM; decoded")
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = data.decode("cp1252")
                notes.append("input was not UTF-8; decoded as Windows-1252")
            except UnicodeDecodeError:
                text = data.decode("utf-8", errors="replace")
                notes.append("input had invalid bytes; replaced with \ufffd")
    if not _mostly_text(text):
        raise UnsupportedInput("the input looks like binary data, not JSON records")
    return text, notes


def _looks_like_record(d: dict) -> bool:
    return bool(RECORD_HINT_KEYS & {str(k).lower() for k in d})


def _expand(obj, line: int, snippet: str, notes: list[str]) -> list:
    """A parsed value to a list of records: unwrap arrays, wrapper objects and JSON-in-a-string."""
    if isinstance(obj, str):
        s = obj.strip()
        if s[:1] in "{[":
            try:
                inner = json.loads(s)
                return _expand(inner, line, snippet, notes + ["record was a JSON string containing JSON; decoded"])
            except (json.JSONDecodeError, RecursionError):
                pass
        return [ReadError(line, "record is a string, not a JSON object", snippet)]
    if isinstance(obj, list):
        out: list = []
        for item in obj:
            out.extend(_expand(item, line, json.dumps(item, ensure_ascii=False, default=str)[:MAX_SNIPPET], notes))
        return out
    if isinstance(obj, dict):
        if not _looks_like_record(obj):
            lists = [(k, v) for k, v in obj.items() if isinstance(v, list) and v and all(isinstance(x, dict) for x in v)]
            if len(lists) == 1 and lists[0][0].lower() in WRAPPER_KEYS:
                return _expand(lists[0][1], line, snippet, notes + [f"records unwrapped from '{lists[0][0]}'"])
        rec = dict(obj)
        if notes:
            rec["_ingest"] = list(dict.fromkeys(notes))
        return [rec]
    return [ReadError(line, f"record is a {type(obj).__name__}, not a JSON object", snippet)]


def _balanced_end(text: str, start: int) -> int | None:
    """Index just past the bracket that closes text[start], respecting quoted strings; None if unclosed."""
    pairs = {"{": "}", "[": "]"}
    closers = {'"': '"”', "'": "'", "“": '”"'}      # tolerate mixed straight/curly quotes
    stack: list[str] = []
    quote: str | None = None      # the characters that may close the open string
    i, n = start, len(text)
    while i < n:
        c = text[i]
        if quote:
            if c == "\\":
                i += 2
                continue
            if c in quote:
                quote = None
        elif c in closers:
            quote = closers[c]
        elif c in pairs:
            stack.append(pairs[c])
        elif c in "}]":
            if not stack or c != stack[-1]:
                return None
            stack.pop()
            if not stack:
                return i + 1
        i += 1
    return None


def _repair(seg: str) -> tuple[object, list[str]] | None:
    """Try progressively looser fixes on one record's text. Returns (value, notes) or None."""
    attempts: list[tuple[str, str]] = []
    s = seg
    if " " in s:
        s = s.replace(" ", " ")
        attempts.append(("non-breaking spaces", s))
    if re.search(r"[“”]", s):
        s = s.replace("“", '"').replace("”", '"')
        attempts.append(("smart quotes", s))
    t = re.sub(r",\s*([}\]])", r"\1", s)
    if t != s:
        s = t
        attempts.append(("trailing commas", s))
    t = re.sub(r"\n", " ", s)
    if t != s:
        attempts.append(("line breaks inside strings", t))
    notes: list[str] = []
    for label, candidate in attempts:
        notes.append(label)
        try:
            return json.loads(candidate), [f"repaired: {', '.join(notes)}"]
        except (json.JSONDecodeError, RecursionError):
            continue
    # Python-style dict: single quotes, True/False/None. literal_eval evaluates literals only.
    try:
        py = re.sub(r"\bnull\b", "None", re.sub(r"\btrue\b", "True", re.sub(r"\bfalse\b", "False", s)))
        value = ast.literal_eval(py)
        if isinstance(value, (dict, list)):
            return value, ["repaired: Python-style record (single quotes / True / None)"]
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        pass
    return None


def read_batch(text: str) -> Batch:
    batch = Batch()
    text = text.translate(ZERO_WIDTH).replace("\r\n", "\n").replace("\r", "\n")
    if FENCE.search(text):
        text = FENCE.sub("", text)
        batch.notes.append("removed markdown code fences")
    if COMMENT.search(text):
        text = COMMENT.sub("", text)
        batch.notes.append("ignored comment lines")
    if not text.strip():
        return batch

    # Fast path: the whole input is one JSON document.
    try:
        doc = json.loads(text)
        batch.records = _expand(doc, 1, text.strip()[:MAX_SNIPPET], [])
        return batch
    except (json.JSONDecodeError, RecursionError):
        pass

    decoder = json.JSONDecoder()
    pos, n = 0, len(text)
    ignored: list[str] = []
    counted_to, line_no = 0, 1        # incremental line counting keeps big files linear
    while pos < n:
        while pos < n and text[pos] in " \t\n,]":
            pos += 1
        if pos >= n:
            break
        line_no += text.count("\n", counted_to, pos)
        counted_to = pos
        line = line_no
        c = text[pos]

        if c not in "{[\"":
            # Prose, numbering ("1."), CSV, or other junk: skip to the next place a record could start.
            m = re.compile(r"[{\[]").search(text, pos)
            end = n if m is None else m.start()
            junk = text[pos:end].strip()
            if junk:
                ignored.append(f"line {line}: {junk[:60]!r}")
            pos = end
            continue

        try:
            obj, end = decoder.raw_decode(text, pos)
            if isinstance(obj, str) and obj.strip()[:1] not in ("{", "["):
                ignored.append(f"line {line}: {obj[:60]!r}")      # a quoted line of prose
            else:
                batch.records.extend(_expand(obj, line, text[pos:end][:MAX_SNIPPET], []))
            pos = end
            continue
        except (json.JSONDecodeError, RecursionError) as e:
            err = getattr(e, "msg", type(e).__name__)

        # JSONL: the record is probably this whole line. Try repairing just the line first.
        nl = text.find("\n", pos)
        line_end = n if nl == -1 else nl
        line_text = text[pos:line_end].rstrip().rstrip(",")
        if line_text.endswith(("}", "]")):
            fixed = _repair(line_text)
            if fixed is not None:
                value, notes = fixed
                batch.records.extend(_expand(value, line, line_text[:MAX_SNIPPET], notes))
                pos = line_end
                continue

        end = _balanced_end(text, pos)
        if end is not None:
            seg = text[pos:end]
            fixed = _repair(seg)
            if fixed is not None:
                value, notes = fixed
                batch.records.extend(_expand(value, line, seg[:MAX_SNIPPET], notes))
                pos = end
                continue
            if c == "[" or re.match(r"\{\s*[\"'“]?\w+[\"'”]?\s*:\s*\[", seg):
                # A broken array or wrapper: step inside and read its records one by one.
                pos = text.index("[", pos) + 1 if c == "{" else pos + 1
                continue
            batch.records.append(ReadError(line, f"invalid JSON: {err}", seg[:MAX_SNIPPET]))
            pos = end
            continue

        # Unclosed (truncated) record: report it and resume at the next line that starts a record.
        m = re.compile(r"\n[ \t]*[{\[]").search(text, pos + 1)
        end = n if m is None else m.start()
        batch.records.append(ReadError(line, f"incomplete or invalid JSON: {err}", text[pos:end][:MAX_SNIPPET]))
        pos = end

    if ignored:
        batch.notes.append(f"ignored {len(ignored)} non-JSON text fragment(s): " + "; ".join(ignored[:5])
                           + (" …" if len(ignored) > 5 else ""))
    return batch


def read_records(text: str) -> list[dict | ReadError]:
    return read_batch(text).records

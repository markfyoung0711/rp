"""Output checks that run on every message before it is released."""
import re

from . import config

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\w)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\w)")
URL = re.compile(r"https?://\S+")
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CARD = re.compile(r"\b(?:\d[ -]?){13,16}\b")


def pii_hits(text: str) -> list[str]:
    """Personal data patterns anywhere in an output record (URLs are removed first; links are not PII)."""
    t = URL.sub("", text)
    hits = []
    if EMAIL.search(t):
        hits.append("email address")
    if PHONE.search(t):
        hits.append("phone number")
    if SSN.search(t):
        hits.append("SSN-like number")
    if CARD.search(t):
        hits.append("card-like number")
    return hits


def protected_hits(text: str) -> list[str]:
    low = text.lower()
    return [t for t in config.rules()["protected_terms"] if re.search(r"\b" + re.escape(t.lower()), low)]


def check_free_text(text: str) -> list[str]:
    """Problems in model-written text (it may not contain links, contact details, opt-out or protected terms)."""
    problems = []
    if URL.search(text):
        problems.append("contains a link")
    if EMAIL.search(text) or PHONE.search(text):
        problems.append("contains contact details")
    if re.search(r"\bSTOP\b", text):
        problems.append("contains opt-out wording (code adds it)")
    hits = protected_hits(text)
    if hits:
        problems.append("protected-class terms: " + ", ".join(hits))
    return problems


def check_message(channel: str, subject: str | None, body: str, opt_out_line: str) -> list[str]:
    """Final checks on the assembled message."""
    problems = []
    if opt_out_line not in body:
        problems.append("opt-out line missing")
    scrubbed = URL.sub("", body)
    if EMAIL.search(scrubbed) or PHONE.search(scrubbed):
        problems.append("contact details in body")
    hits = protected_hits(f"{subject or ''} {body}")
    if hits:
        problems.append("protected-class terms: " + ", ".join(hits))
    if channel == "sms" and subject:
        problems.append("SMS must not have a subject")
    if channel == "email" and not subject:
        problems.append("email needs a subject")
    return problems

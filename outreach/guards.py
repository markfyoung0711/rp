"""Output checks that run on every message before it is released."""
import re

from . import config

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\w)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\w)")
URL = re.compile(r"https?://\S+")
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CARD = re.compile(r"\b(?:\d[ -]?){13,16}\b")
MONEY = re.compile(r"[$€£]\s?\d|\b\d[\d,]*\.\d{2}\b|\b\d+\s?(dollars|usd)\b", re.I)
LONG_DIGITS = re.compile(r"\b\d{8,}\b")          # account, routing, card or ID-like numbers


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
    if MONEY.search(text) or LONG_DIGITS.search(text):
        problems.append("money amount or account-like number")
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
    # SMS and email are weak channels: no balances, amounts or account-like numbers in a message.
    if MONEY.search(f"{subject or ''} {scrubbed}"):
        problems.append("money amount in message")
    if LONG_DIGITS.search(f"{subject or ''} {scrubbed}") or SSN.search(scrubbed):
        problems.append("account- or ID-like number in message")
    if channel in ("sms", "voice") and subject:
        problems.append(f"{channel.upper()} must not have a subject")
    if channel == "email" and not subject:
        problems.append("email needs a subject")
    return problems


EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]")
CAPS_WORD = re.compile(r"\b[A-Z]{4,}\b")
CAPS_OK = {"STOP", "STOPALL", "HELP", "YES", "SMS", "HTTPS", "HTTP"}


def brand_for(facts: dict | None) -> dict:
    """The brand profile for a property: rules.yaml brand_default, overridden by the property's brand block."""
    brand = dict(config.rules().get("brand_default") or {})
    brand.update((facts or {}).get("brand") or {})
    return brand


def check_brand(channel: str, subject: str | None, body: str, facts: dict | None, full_name: str | None) -> list[str]:
    """Problems with brand style (the samples' `brand_style_applied`). Empty list means the brand was applied."""
    brand = brand_for(facts)
    text = f"{subject or ''} {URL.sub('', body)}"
    low = text.lower()
    problems = []
    hits = [p for p in brand.get("banned_phrases", []) if p.lower() in low]
    if hits:
        problems.append("off-brand phrases: " + ", ".join(hits))
    if not brand.get("emoji_allowed", False) and EMOJI.search(text):
        problems.append("emoji not allowed by the brand")
    if text.count("!") > int(brand.get("max_exclamations", 2)):
        problems.append("too many exclamation marks")
    if channel in ("sms", "voice") and len(body) > int(brand.get("max_sms_chars", 320)):
        problems.append(f"SMS longer than {brand.get('max_sms_chars', 320)} characters")
    if not brand.get("shouting_allowed", False):
        shouting = [w for w in CAPS_WORD.findall(text) if w not in CAPS_OK]
        if shouting:
            problems.append("ALL-CAPS words: " + ", ".join(sorted(set(shouting))[:3]))
    if channel == "voice":
        words = len(body.split())
        if words > int(brand.get("max_voice_words", 75)):
            problems.append(f"call script too long ({words} words; brand limit {brand.get('max_voice_words', 75)})")
        if re.search(r"https?://|[→&@#*/<>]", body):
            problems.append("call script contains symbols or links that don't read aloud")
    display = brand.get("display_name") or (facts or {}).get("short_name")
    if brand.get("use_display_name", True) and display and full_name and full_name != display and full_name in text:
        problems.append(f"uses the full property name instead of the brand name {display!r}")
    return problems


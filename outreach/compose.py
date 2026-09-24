"""Message composition: template text plus the fixed parts (CTA mechanics and opt-out).

The message has three parts:
  subject  - email only; template or model
  core     - greeting, personalization and the call-to-action question; template or model
  tail     - reply options / link and the opt-out line; ALWAYS this fixed code
Property claims (tour days, amenities, links) come only from config/properties.yaml.
"""
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from . import config
from .normalize import Case

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_FULL = {"en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
            "es": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]}
MONTHS = {"en": ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                 "October", "November", "December"],
          "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
                 "octubre", "noviembre", "diciembre"]}
OPT_OUT = {"en": {"sms": "Reply STOP to opt out.", "email": "To opt out of emails, click here or reply STOP.",
                  "voice": "To stop these calls, press 9 or say stop."},
           "es": {"sms": "Responde STOP para cancelar.", "email": "Para dejar de recibir correos, haz clic aquí o responde STOP.",
                  "voice": "Para no recibir más llamadas, marque 9 o diga stop."}}
SUPPORTED_LANGS = {"en", "es"}

# Generic (non-tour) purpose lines: {name}, {prop}. No prices, no invented facts.
PURPOSE_LINES = {
    "en": {
        "apply": "your application for {prop} takes just a few minutes. Ready to get started?",
        "sign_lease": "your lease for {prop} is ready for your signature.",
        "payment": "this is a friendly reminder about your payment for {prop}. You can take care of it online.",
        "renewal": "we'd love to have you stay at {prop}. Your renewal options are ready to review.",
        "maintenance": "we can help schedule your maintenance request at {prop}.",
        "general": "we wanted to follow up about {prop}. How can we help?",
    },
    "es": {
        "apply": "tu solicitud para {prop} toma solo unos minutos. ¿Listo para empezar?",
        "sign_lease": "tu contrato de arrendamiento para {prop} está listo para firmar.",
        "payment": "te recordamos amablemente tu pago para {prop}. Puedes hacerlo en línea.",
        "renewal": "nos encantaría que te quedes en {prop}. Tus opciones de renovación están listas.",
        "maintenance": "podemos ayudarte a programar tu solicitud de mantenimiento en {prop}.",
        "general": "queríamos darte seguimiento sobre {prop}. ¿Cómo podemos ayudarte?",
    },
}
SUBJECTS = {
    "en": {"apply": "Your application for {prop}", "sign_lease": "Your {prop} lease is ready to sign",
           "payment": "Payment reminder for {prop}", "renewal": "Your renewal options at {prop}",
           "maintenance": "Your maintenance request at {prop}", "general": "Following up from {prop}"},
    "es": {"apply": "Tu solicitud para {prop}", "sign_lease": "Tu contrato de {prop} está listo para firmar",
           "payment": "Recordatorio de pago de {prop}", "renewal": "Tus opciones de renovación en {prop}",
           "maintenance": "Tu solicitud de mantenimiento en {prop}", "general": "Seguimiento de {prop}"},
}
SAFE_NAME = re.compile(r"^[^\W\d_][^\W\d_'’ .-]{0,29}$")   # any script's letters, plus ' ’ space . -


@dataclass
class Draft:
    subject: str | None
    core: str
    tail: str
    cta: dict
    facts_used: bool
    tour_days: list | None = None   # full day names offered, in order (for the model prompt)


def display_name(full: str) -> str:
    """Short brand-style name for a property without a facts file: 'Cedar Point Apartments' -> 'Cedar Point'."""
    suffixes = sorted(config.rules().get("display_name_suffixes") or [], key=len, reverse=True)
    for sfx in suffixes:
        m = re.match(rf"^(.*\S)\s+{re.escape(sfx)}\.?$", full.strip(), re.I)
        if m and len(m.group(1).split()) >= 1 and m.group(1).lower() not in ("the", "a"):
            return m.group(1)
    return full


def safe_first_name(case: Case, why: list) -> str:
    raw = str(case.profile.get("first_name") or "").strip()
    if raw and SAFE_NAME.match(raw) and not re.search(r"\b(ignore|instruction|system|prompt|assistant)\b", raw, re.I):
        return raw
    if raw:
        # Never echo the rejected value: it may be an email, phone number, ID or injection text.
        why.append(f"first name rejected as unsafe or invalid ({len(raw)} characters, not shown); greeting uses 'there'")
    return "there"


def move_phrase(d: date | None, lang: str) -> str | None:
    if not d:
        return None
    part = ("early", "mid", "late")[0 if d.day <= 10 else 1 if d.day <= 20 else 2]
    month = MONTHS[lang][d.month - 1]
    if lang == "es":
        return f"{ {'early': 'principios', 'mid': 'mediados', 'late': 'finales'}[part]} de {month}"
    return f"{part}‑{month}"      # non-breaking hyphen, as in the sample ("mid‑February")


def next_tour_days(facts: dict, send_at: datetime) -> list[tuple[str, date]]:
    """The next two tour days after the send date, within the coming week."""
    days = [d for d in facts.get("tour_days", []) if d in DAY_NAMES]
    out = []
    for i in range(1, 8):
        d = send_at.date() + timedelta(days=i)
        if DAY_NAMES[d.weekday()] in days:
            out.append((DAY_NAMES[d.weekday()], d))
    return out[:2]


def amenity_labels(case: Case, facts: dict | None) -> list[tuple[str, str]]:
    interests = case.profile.get("amenity_interest") or []
    if isinstance(interests, str):
        interests = [interests]
    table = (facts or {}).get("amenities", {})
    return [tuple(table[str(i).lower()]) for i in interests if str(i).lower() in table]


def draft(case: Case, channel: str, send_at: datetime, why: list) -> Draft:
    lang = case.language if case.language in SUPPORTED_LANGS else "en"
    if lang != case.language:
        case.warnings.append(f"language {case.language!r} has no template; wrote English")
    rule, known = config.cta_rule(case.primary_cta)
    if not known:
        why.append(f"primary_cta {case.primary_cta!r} is not mapped; used the generic '{rule['type']}' CTA")
    facts = config.property_facts(case.property_name)
    prop_full = case.property_name or ("la propiedad" if lang == "es" else "our community")
    prop = (facts or {}).get("short_name") or display_name(prop_full)
    if case.property_name and not facts:
        why.append(f"no facts on file for {case.property_name!r}; generic message with no specific claims")
        if not any(g.get("code") == "property_facts_missing" for g in case.gaps):
            case.warnings.append(f"property {case.property_name!r} has no facts file: generic message, default brand, "
                                 f"display name {prop!r}")
            case.gaps.append({"code": "property_facts_missing", "property": case.property_name})
    name = safe_first_name(case, why)
    link = (facts or {}).get(rule["link_key"])
    opt_out = OPT_OUT[lang][channel]      # always included, whatever the record says
    purpose = rule["purpose"]

    if purpose == "tour":
        return _tour(case, channel, send_at, lang, name, prop, facts, link, opt_out, rule)

    line = PURPOSE_LINES[lang][purpose].format(prop=prop)
    cta = {"type": rule["type"]}
    if channel == "voice":
        # A call can't carry a link: offer to connect the caller to the team instead.
        core = f"{'Hi' if lang == 'en' else 'Hola'} {name}, {voice_intro(facts, prop, lang)}. " + line[0].upper() + line[1:]
        tail = ("Press 1 to be connected to our team. " if lang == "en" else "Marque 1 para hablar con nuestro equipo. ") + opt_out
        cta["options"] = ["1"]
        return Draft(None, core, tail, cta, bool(facts))
    if link:
        cta["link"] = link
    if channel == "sms":
        core = f"Hi {name}—{line}" if lang == "en" else f"Hola {name}: {line}"
        tail = (f"{'Details' if lang == 'en' else 'Detalles'}: {link} " if link else "") + opt_out
        return Draft(None, core, tail.strip(), cta, bool(facts))
    subject = SUBJECTS[lang][purpose].format(prop=prop)
    core = (f"Hi {name},\n" if lang == "en" else f"Hola {name}:\n") + line[0].upper() + line[1:]
    action = {"en": "Continue", "es": "Continuar"}[lang]
    tail = (f"{action} → {link}\n" if link else "") + opt_out
    return Draft(subject, core, tail, cta, bool(facts))


def voice_intro(facts: dict | None, prop: str, lang: str) -> str:
    """How an automated call identifies itself: the brand's voice_intro, else "this is <property>"."""
    intro = ((facts or {}).get("brand") or {}).get("voice_intro")
    if intro and lang == "en":
        return intro
    return f"le llamamos de {prop}" if lang == "es" else f"this is {prop}"


def _tour(case, channel, send_at, lang, name, prop, facts, link, opt_out, rule) -> Draft:
    cta = {"type": rule["type"]}
    if channel == "voice":
        # Automated call script: the same offer as SMS, with keypad choices instead of reply codes.
        slots = next_tour_days(facts, send_at) if facts else []
        if slots:
            full = [DAY_FULL[lang][d.weekday()] for _, d in slots]
            this_week = all(d.isocalendar()[1] == send_at.date().isocalendar()[1] for _, d in slots)
            if lang == "es":
                when = "esta semana" if this_week else "en los próximos días"
                core = f"Hola {name}, {voice_intro(facts, prop, lang)}. Hay visitas disponibles {when}. ¿Le gustaría reservar el {' o el '.join(full)}?"
                keys = ", ".join(f"marque {i + 1} para el {f}" for i, f in enumerate(full))
                tail = f"Por favor, {keys}. {opt_out}"
            else:
                when = "this week" if this_week else "in the coming days"
                core = f"Hi {name}, {voice_intro(facts, prop, lang)}. Tours are available {when}. Would you like to book a time on {' or '.join(full)}?"
                keys = ", ".join(f"press {i + 1} for {f}" for i, f in enumerate(full))
                tail = f"Please {keys}. {opt_out}"
            cta["options"] = [s for s, _ in slots]
            return Draft(None, core, tail, cta, bool(facts), full)
        if lang == "es":
            core = f"Hola {name}, {voice_intro(facts, prop, lang)}. ¿Le gustaría agendar una visita?"
            tail = f"Marque 1 y le devolveremos la llamada con horarios. {opt_out}"
        else:
            core = f"Hi {name}, {voice_intro(facts, prop, lang)}. Would you like to schedule a tour?"
            tail = f"Press 1 and we'll call you back with available times. {opt_out}"
        cta["options"] = ["1"]
        return Draft(None, core, tail, cta, bool(facts))
    if channel == "sms":
        slots = next_tour_days(facts, send_at) if facts else []
        if slots:
            full = [DAY_FULL[lang][d.weekday()] for _, d in slots]
            this_week = all(d.isocalendar()[1] == send_at.date().isocalendar()[1] for _, d in slots)
            opts = [s for s, _ in slots]
            if lang == "es":
                when = "esta semana" if this_week else "en los próximos días"
                core = f"Hola {name}, ¡te damos la bienvenida a {prop}! Hay visitas disponibles {when}. ¿Te gustaría reservar el {' o el '.join(full)}?"
                codes = ", ".join(f"{i + 1} para {DAY_FULL['es'][d.weekday()][:3]}" for i, (_, d) in enumerate(slots))
                tail = f"Responde {codes}. {opt_out}"
            else:
                greet = "welcome to" if case.stage == "new" else "thanks for your interest in"
                when = "this week" if this_week else "in the coming days"
                core = f"Hi {name}—{greet} {prop}! Tours are available {when}. Would you like to book a time on {' or '.join(full)}?"
                codes = ", ".join(f"{i + 1} for {s}" for i, s in enumerate(opts))
                tail = f"Reply {codes}. {opt_out}"
            cta["options"] = opts
            return Draft(None, core, tail, cta, bool(facts), full)
        else:
            if lang == "es":
                core = f"Hola {name}, gracias por tu interés en {prop}. ¿Te gustaría agendar una visita?"
                tail = f"Responde SÍ y te enviaremos horarios. {opt_out}"
                cta["options"] = ["SÍ"]
            else:
                core = f"Hi {name}—thanks for your interest in {prop}! Would you like to schedule a tour?"
                tail = f"Reply YES and we'll text you available times. {opt_out}"
                cta["options"] = ["YES"]
        return Draft(None, core, tail, cta, bool(facts))

    # email
    labels = amenity_labels(case, facts)
    move = move_phrase(case.move_date, lang)
    if lang == "es":
        subject = f"Visita {prop}" + (f": conoce {' y '.join(b for _, b in labels)}" if labels else "")
        parts = []
        if move:
            parts.append(f"Como planeas mudarte a {move}, ")
        if labels:
            parts.append(("aquí tienes" if move else "Aquí tienes") + f" un vistazo a nuestro {' y '.join(b for _, b in labels)}.")
        elif move:
            parts.append(f"es un buen momento para conocer {prop}.")
        first = "".join(parts) or f"Nos encantaría mostrarte {prop}."
        core = f"Hola {name}:\n{first} Agenda una visita esta semana."
        tail = (f"Reserva aquí → {link}\n" if link else "Responde a este correo para agendar una visita.\n") + opt_out
    else:
        subject = f"Tour {prop}—See the {' & '.join(s for s, _ in labels)} you asked about" if labels else f"Tour {prop}—Book a visit"
        parts = []
        if move:
            article = "an" if move[0].lower() in "aeiou" else "a"
            parts.append(f"Since you’re planning {article} {move} move, ")
        if labels:
            parts.append(("here’s" if move else "Here’s") + f" a quick look at our {' and '.join(b for _, b in labels)}.")
        elif move:
            parts.append(f"now is a great time to see {prop} in person.")
        first = "".join(parts) or f"We’d love to show you around {prop}."
        closer = (facts or {}).get("email_closer") or "We’d love to show you around."
        core = f"Hi {name},\n{first} {closer}"
        tail = (f"Book now → {link}\n" if link else "Reply to this email to set up a visit.\n") + opt_out
    if link:
        cta["link"] = link
    return Draft(subject, core, tail, cta, bool(facts))


def assemble(channel: str, core: str, tail: str) -> str:
    return f"{core.rstrip()} {tail}" if channel in ("sms", "voice") else f"{core.rstrip()}\n{tail}"

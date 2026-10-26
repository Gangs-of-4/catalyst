"""Spoken dates and times in English, romanized Hindi and Devanagari -> date / 'HH:MM'.

Every tool result states the resolved day so the agent can read it back (C2).
"""
import re
from datetime import date, timedelta

_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
# Devanagari matras are not \w in Python, so word edges are spelled out.
_L = r"(?<![\wऀ-ॿ])"
_R = r"(?![\wऀ-ॿ])"

WEEKDAYS = [  # index = date.weekday()
    ["monday", "mon", "somvar", "somvaar", "somwar", "सोमवार"],
    ["tuesday", "tue", "tues", "mangalvar", "mangalvaar", "mangalwar", "मंगलवार"],
    ["wednesday", "wed", "budhvar", "budhvaar", "budhwar", "budh", "बुधवार"],
    ["thursday", "thu", "thurs", "guruvar", "guruvaar", "guruwar", "brihaspativar", "veervar", "गुरुवार", "बृहस्पतिवार"],
    ["friday", "fri", "shukravar", "shukravaar", "shukrvar", "shukrawar", "शुक्रवार"],
    ["saturday", "sat", "shanivar", "shanivaar", "shaniwar", "शनिवार"],
    ["sunday", "ravivar", "ravivaar", "raviwar", "itvar", "itwar", "itvaar", "रविवार", "इतवार"],
]
MONTHS = [
    ["january", "jan", "जनवरी"], ["february", "feb", "फरवरी"], ["march", "mar", "मार्च"],
    ["april", "apr", "अप्रैल"], ["may", "मई"], ["june", "jun", "जून"], ["july", "jul", "जुलाई"],
    ["august", "aug", "अगस्त"], ["september", "sep", "sept", "सितंबर", "सितम्बर"],
    ["october", "oct", "अक्टूबर"], ["november", "nov", "नवंबर", "नवम्बर"], ["december", "dec", "दिसंबर", "दिसम्बर"],
]
RELATIVE = [
    (2, ["day after tomorrow", "parso", "parson", "parsoon", "parsun", "परसों", "परसो"]),
    (0, ["today", "aaj", "aj", "आज"]),
    (1, ["tomorrow", "kal", "कल"]),  # "kal" also means yesterday; for booking it is tomorrow
]
NEXT_WORDS = ["next", "agle", "agla", "अगले", "अगला"]

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "chhah": 6,
    "che": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10, "gyarah": 11, "barah": 12, "baarah": 12,
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "छः": 6, "सात": 7, "आठ": 8,
    "नौ": 9, "दस": 10, "ग्यारह": 11, "बारह": 12,
}
PERIODS = {
    "morning": "am", "subah": "am", "subha": "am", "सुबह": "am",
    "afternoon": "noon", "dopahar": "noon", "dopehar": "noon", "dophar": "noon", "दोपहर": "noon",
    "evening": "pm", "shaam": "pm", "sham": "pm", "शाम": "pm",
    "night": "night", "raat": "night", "रात": "night",
}
FRACTIONS = {  # (minutes, hour offset)
    "saade": (30, 0), "sade": (30, 0), "saadhe": (30, 0), "साढ़े": (30, 0), "साढे": (30, 0),
    "sawa": (15, 0), "sava": (15, 0), "सवा": (15, 0),
    "paune": (45, -1), "pone": (45, -1), "पौने": (45, -1),
}
SPECIAL = {"dedh": "01:30", "डेढ़": "01:30", "dhai": "02:30", "dhaai": "02:30", "ढाई": "02:30"}


def _has(text: str, word: str) -> bool:
    return re.search(_L + re.escape(word) + _R, text) is not None


def _norm(text: str) -> str:
    return " ".join(str(text).translate(_DIGITS).lower().replace(",", " ").split())


def parse_date(text: str | None, today: date) -> date | None:
    """Resolve the first date expression in `text`, or None."""
    if not text:
        return None
    t = _norm(text)
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    for offset, words in RELATIVE:
        if any(_has(t, w) for w in words):
            return today + timedelta(days=offset)
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", t)
    if m:
        return _dm(int(m[1]), int(m[2]), m[3], today)
    for i, names in enumerate(MONTHS):
        for name in names:
            m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s*" + _L + re.escape(name) + _R, t) or re.search(
                _L + re.escape(name) + _R + r"\s*(\d{1,2})(?:st|nd|rd|th)?\b", t
            )
            if m:
                return _dm(int(m[1]), i + 1, None, today)
    for i, names in enumerate(WEEKDAYS):
        if any(_has(t, n) for n in names):
            ahead = (i - today.weekday()) % 7
            if ahead == 0 and any(_has(t, w) for w in NEXT_WORDS):
                ahead = 7
            return today + timedelta(days=ahead)
    return None


def _dm(day: int, month: int, year: str | None, today: date) -> date | None:
    try:
        if year:
            y = int(year)
            return date(y + 2000 if y < 100 else y, month, day)
        d = date(today.year, month, day)
        return d if d >= today else date(today.year + 1, month, day)
    except ValueError:
        return None


def parse_time(text: str | None) -> str | None:
    """Resolve a clock time to 'HH:MM'. A bare hour from 1 to 7 is PM."""
    if not text:
        return None
    t = _norm(text)
    for word, hhmm in SPECIAL.items():
        if _has(t, word):
            h, mnt = map(int, hhmm.split(":"))
            return _apply_period(h, mnt, _period(t), bare=True)
    period = _period(t)
    m = re.search(r"\b(\d{1,2})[:.](\d{2})\s*(am|pm|a\.m\.|p\.m\.)?", t)
    if m:
        h, mnt = int(m[1]), int(m[2])
        if m[3]:
            period = "am" if m[3].startswith("a") else "pm"
        if h > 23 or mnt > 59:
            return None
        return _apply_period(h, mnt, period, bare=h <= 12 and not m[3] and period is None)
    m = re.search(r"\b(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)", t)
    if m:
        return _apply_period(int(m[1]), 0, "am" if m[2].startswith("a") else "pm", bare=False)
    hour = None
    m = re.search(r"\b(\d{1,2})\b", t)
    if m:
        hour = int(m[1])
    elif _period(t) or any(_has(t, w) for w in (*FRACTIONS, "baje", "bje", "बजे", "o'clock")):
        # Number words only count next to a time cue, so "book kar do" is not 2 o'clock.
        for word, n in NUMBER_WORDS.items():
            if _has(t, word):
                hour = n
                break
    if hour is None or not 0 <= hour <= 23:
        return None
    mnt = 0
    for word, (minutes, shift) in FRACTIONS.items():
        if _has(t, word):
            mnt, hour = minutes, hour + shift
            break
    if hour > 12:
        return f"{hour:02d}:{mnt:02d}"
    if hour == 0:
        hour = 12
    return _apply_period(hour, mnt, period, bare=True)


def _period(t: str) -> str | None:
    for word, p in PERIODS.items():
        if _has(t, word):
            return p
    return None


def _apply_period(h: int, m: int, period: str | None, bare: bool) -> str | None:
    if h > 12 or (h == 12 and period is None):
        return f"{h:02d}:{m:02d}" if h < 24 else None
    if period == "am":
        h = 0 if h == 12 else h
    elif period == "pm":
        h = h if h == 12 else h + 12
    elif period == "noon":
        h = h if h in (11, 12) else h + 12
    elif period == "night":
        h = h if h == 12 else (h + 12 if h >= 6 else h)
    elif bare and 1 <= h <= 7:
        h += 12
    return f"{h:02d}:{m:02d}"


def spoken_date(d: date) -> str:
    """'Wednesday, 28 October 2026'."""
    return f"{d:%A}, {d.day} {d:%B %Y}"


def spoken_time(hhmm: str) -> str:
    """'17:30' -> '5:30 PM', '10:00' -> '10 AM'."""
    h, m = map(int, hhmm.split(":"))
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12} {suffix}" if m == 0 else f"{h12}:{m:02d} {suffix}"


def short_date(d: date) -> str:
    """'Wed, 28 Oct'."""
    return f"{d:%a}, {d.day} {d:%b}"

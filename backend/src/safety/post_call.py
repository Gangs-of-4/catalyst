"""Post-call safety flag (ADR-0035): scan what the assistant said for medicine, dosage, diagnosis,
or (for a business that sells medicines) a substitute.

Detection, not prevention. The in-call guard (custom-LLM route, ADR-0032) replaces this before a real pilot.
"""

import re
import unicodedata

_B = r"(?<![\wऀ-ॿ])"  # word edge that also works for Devanagari
_E = r"(?![\wऀ-ॿ])"

# Always flag: a named drug, a dose, an instruction to take something, a diagnosis or reassurance.
STRONG = [
    r"\d+\s*(mg|ml|mcg)" + _E,
    _B
    + r"(paracetamol|ibuprofen|amoxicillin|amoxycillin|metronidazole|diclofenac|aceclofenac|crocin|dolo|combiflam"
    r"|calpol|ketorolac|nimesulide|azithromycin|augmentin|zerodol|brufen|disprin|aspirin)" + _E,
    _B + r"(dose|dosage|twice a day|thrice a day|din mein (do|teen|ek) (baar|bar))" + _E,
    _B
    + r"(dawai|dawaai|dawa|goli|tablet|capsule|medicine|painkiller|antibiotic|syrup|gel|ointment)s?\b.{0,25}"
    r"(lijiye|le lijiye|le lo|lelo|khaiye|kha lijiye|khao|lagaiye|laga lijiye|take|apply)",
    _B
    + r"(take|try|apply|use) (a |an |some )?(painkiller|antibiotic|tablet|medicine|ointment|gel)",
    _B
    + r"(you have|sounds like|it is|it's|looks like) (an? )?(infection|abscess|cavity|cyst|sensitivity|gum disease)",
    _B
    + r"(nothing serious|not serious|kuch serious nahi|ghabraane ki (koi )?baat nahi|ghabrane ki (koi )?baat nahi)",
    _B
    + r"(garam paani|gungune paani|namak|salt water|laung|clove oil|ice pack|sikai|gargle|kulla)"
    + _E,
    r"(दवाई|दवा|गोली|टैबलेट)\s*(ले लीजिए|लीजिए|खाइए|लें)",
    r"(घबराने की (कोई )?बात नहीं|कुछ सीरियस नहीं)",
    r"(नमक|लौंग|गुनगुने पानी)",
]
# Flag only if the line is not a refusal ("main dawai nahi bata sakti", "infection hai ya nahi, doctor hi batayenge").
WEAK = [
    _B + r"(infection|abscess|cavity|pus|cyst) (hai|ho gaya|ho gayi|lag raha|lagta|hoga)" + _E,
    r"(इन्फेक्शन|संक्रमण)\s*(है|हो गया)",
    # Not "prescription": "bring your old prescription" is a clinic FAQ answer, not advice.
    _B + r"(dawai|dawaai|goli|tablet|capsule|antibiotic|painkiller|medicine)s?" + _E,
    r"(दवाई|गोली|टैबलेट)",
]
REFUSAL = re.compile(
    r"(nahi de sakti|nahi de sakta|nahi bata sakti|nahi bata sakta|can't|cannot|can not|not able to|unable to|"
    r"doctor hi|only the doctor|नहीं दे सकती|नहीं बता सकती|डॉक्टर ही)",
    re.I,
)
# A business that sells medicines (orders template) names products and pack sizes all the time.
# For it, only the two "a medicine was named" checks (a drug name, a dose like "500 mg") ignore the
# catalogue's own names, compared after folding case, punctuation and "500mg"/"500 mg". Every advice
# check still runs on the line as said, catalogue names included, plus selling-only checks: using a
# product for a symptom, and offering a substitute (contracts §1.11).
_SYMPTOM = (
    r"(bukhar|fever|dard|pain|sardi|zukaam|zukam|cold|khansi|cough|headache|acidity|gas|"
    r"bachch\w*|child\w*|baby|बुखार|दर्द|सर्दी|खांसी|बच्च\w*)"
)
_TAKE = (
    r"(take|le lijiye|lijiye|le lo|lelo|khaiye|kha lijiye|de dijiye|dijiye|pilaiye|pila dijiye|"
    r"lagaiye|de sakte|le sakte|chalegi|chalega|kaam karegi|kaam karega|लीजिए|खाइए|दीजिए)"
)
# Always flagged, refusal or not: telling someone to take or give a product for a symptom.
SELLING_ADVICE = [
    _B + _TAKE + r"\b.{0,60}?" + _SYMPTOM + _E,
    _B + _SYMPTOM + r".{0,60}?" + _TAKE + _E,
]
# Flagged unless the line is a refusal: saying what a product is for, or offering a substitute.
SELLING_CLAIMS = [
    _B + r"(for|mein kaam|me kaam) (the |a )?" + _SYMPTOM + _E,
    _B + _SYMPTOM + r" (ke liye|mein kaam|me kaam|mein aaram|ke liye theek|के लिए|में आराम)" + _E,
    _B + r"(ki jagah|ke badle|ke badale|instead of|substitute|alternative|same (hi )?(hai|kaam)|"
    r"wahi kaam|vahi kaam|same composition|generic)" + _E,
    r"(की जगह|के बदले|वही काम)",
]
_STRONG = [re.compile(p, re.I) for p in STRONG]
_NAMED = _STRONG[:2]  # a dose ("500 mg") and a drug name: the only checks a catalogue name excuses
_ADVICE = _STRONG[2:]
_WEAK = [re.compile(p, re.I) for p in WEAK]
_WEAK_ADVICE = _WEAK[:2]  # diagnosis words; the rest are bare medicine nouns
_SELLING_ADVICE = [re.compile(p, re.I) for p in SELLING_ADVICE]
_SELLING_CLAIMS = [re.compile(p, re.I) for p in SELLING_CLAIMS]


def fold(text: str) -> str:
    """Case, punctuation and digit-letter joins folded, like the catalogue's name keys:
    "Dolo-650" → "dolo 650", "500mg" → "500 mg"."""
    text = unicodedata.normalize("NFC", str(text)).casefold()
    text = re.sub(r"(?<=\d)(?=[^\W\d_])|(?<=[^\W\d_])(?=\d)", " ", text)
    return " ".join(
        "".join(c if unicodedata.category(c)[0] in "LNM" else " " for c in text).split()
    )


def _mask(text: str, terms: list[str]) -> str:
    """The folded line with every catalogue name and pack size (as whole words) taken out."""
    padded = f" {fold(text)} "
    for term in sorted({fold(t) for t in terms if t and t.strip()} - {""}, key=len, reverse=True):
        while f" {term} " in padded:
            padded = padded.replace(f" {term} ", " ")
    return padded.strip()


def _first(patterns: list[re.Pattern], text: str) -> re.Match | None:
    return next((m for m in (r.search(text) for r in patterns) if m), None)


def scan(
    assistant_lines: list[str], catalogue: list[str] | None = None, selling: bool = False
) -> list[str]:
    """The matched phrases, one per flagged line. Empty means nothing to review.

    `selling` is for a business whose products may be medicines (orders template): `catalogue`
    holds its product names and pack sizes, which the agent is allowed to *say*. Only the "a
    medicine was named" checks ignore them; any advice about them (take it, for a symptom, a dose,
    a diagnosis, reassurance, a substitute) is flagged."""
    hits = []
    for line in assistant_lines:
        text = " ".join(str(line).split())
        refusal = REFUSAL.search(text)
        if not selling:
            m = _first(_STRONG, text) or (None if refusal else _first(_WEAK, text))
        else:
            m = (
                _first(_ADVICE, text)
                or _first(_SELLING_ADVICE, text)
                or _first(_NAMED, _mask(text, catalogue or []))
                or (None if refusal else _first(_SELLING_CLAIMS + _WEAK_ADVICE, text))
            )
        if m:
            hits.append(m.group(0))
    return hits

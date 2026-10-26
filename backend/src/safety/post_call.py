"""Post-call safety flag (ADR-0035): scan what the assistant said for medicine, dosage or diagnosis.

Detection, not prevention. The in-call guard (custom-LLM route, ADR-0032) replaces this before a real pilot.
"""
import re

_B = r"(?<![\wऀ-ॿ])"   # word edge that also works for Devanagari
_E = r"(?![\wऀ-ॿ])"

# Always flag: a named drug, a dose, an instruction to take something, a diagnosis or reassurance.
STRONG = [
    r"\d+\s*(mg|ml|mcg)" + _E,
    _B + r"(paracetamol|ibuprofen|amoxicillin|amoxycillin|metronidazole|diclofenac|aceclofenac|crocin|dolo|combiflam"
         r"|calpol|ketorolac|nimesulide|azithromycin|augmentin|zerodol|brufen|disprin|aspirin)" + _E,
    _B + r"(dose|dosage|twice a day|thrice a day|din mein (do|teen|ek) (baar|bar))" + _E,
    _B + r"(dawai|dawaai|dawa|goli|tablet|capsule|medicine|painkiller|antibiotic|syrup|gel|ointment)s?\b.{0,25}"
         r"(lijiye|le lijiye|le lo|lelo|khaiye|kha lijiye|khao|lagaiye|laga lijiye|take|apply)",
    _B + r"(take|try|apply|use) (a |an |some )?(painkiller|antibiotic|tablet|medicine|ointment|gel)",
    _B + r"(you have|sounds like|it is|it's|looks like) (an? )?(infection|abscess|cavity|cyst|sensitivity|gum disease)",
    _B + r"(nothing serious|not serious|kuch serious nahi|ghabraane ki (koi )?baat nahi|ghabrane ki (koi )?baat nahi)",
    _B + r"(garam paani|gungune paani|namak|salt water|laung|clove oil|ice pack|sikai|gargle|kulla)" + _E,
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
    r"doctor hi|only the doctor|नहीं दे सकती|नहीं बता सकती|डॉक्टर ही)", re.I,
)
_STRONG = [re.compile(p, re.I) for p in STRONG]
_WEAK = [re.compile(p, re.I) for p in WEAK]


def scan(assistant_lines: list[str]) -> list[str]:
    """The matched phrases, one per flagged line. Empty means nothing to review."""
    hits = []
    for line in assistant_lines:
        text = " ".join(str(line).split())
        m = next((r.search(text) for r in _STRONG if r.search(text)), None)
        if not m and not REFUSAL.search(text):
            m = next((r.search(text) for r in _WEAK if r.search(text)), None)
        if m:
            hits.append(m.group(0))
    return hits

import pytest

from src.safety.post_call import scan


@pytest.mark.parametrize("line", [
    "Aap ek painkiller le lijiye, aaram milega.",
    "Take 500 mg paracetamol twice a day.",
    "Dawai lijiye aur kal aa jaiye.",
    "Crocin le sakte hain.",
    "It sounds like an infection.",
    "Infection hai, doctor dekh lenge.",
    "Garam paani mein namak daal kar kulla kijiye.",
    "Ghabraane ki baat nahi hai.",
    "It's nothing serious.",
    "Try an antibiotic until you come in.",
    "आप दवाई ले लीजिए।",
    "घबराने की बात नहीं है।",
    "Laung ka tel lagaiye.",
])
def test_flags_medical_advice(line):
    assert scan([line]), line


@pytest.mark.parametrize("line", [
    "Main medical salah nahi de sakti, yeh doctor hi bata payenge.",
    "Main dawai ke baare mein nahi bata sakti. Doctor hi batayenge.",
    "I can't recommend any medicine; the doctor will advise you.",
    "Infection hai ya nahi, yeh doctor hi bata payenge.",
    "Aapka appointment kal shaam 5 baje Dr. Asha Verma ke saath book ho gaya hai.",
    "Consultation fee 300 rupees hai.",
    "Purani prescription ho to saath le aaiye.",   # FAQ answer, not advice
    "Clinic ka address B-14, Sector C, Aliganj hai.",
    "मैं medical सलाह नहीं दे सकती, यह doctor ही बता पाएँगे।",
    "Kya aap apna mobile number bata sakte hain?",
])
def test_does_not_flag_safe_lines(line):
    assert scan([line]) == [], line


def test_one_hit_per_flagged_line():
    hits = scan(["Namaste!", "Dolo le lijiye.", "Theek hai, aapka appointment book ho gaya."])
    assert len(hits) == 1

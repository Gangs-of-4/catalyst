"""Function schemas the voice platform shows the LLM. Handlers live in agents/tools.py."""

_DATE = {"type": "string", "description": "Day as said by the caller or ISO: 'kal', 'parso', 'Monday', 'somvar', '28 Oct', '2026-10-28'."}
_TIME = {"type": "string", "description": "Time as said by the caller or 24h: 'shaam 5 baje', 'saade 10', '5 pm', '17:00'."}
_PHONE = {"type": "string", "description": "Caller's 10-digit mobile number, digits only."}
_NAME = {"type": "string", "description": "Caller's name."}


def _fn(name: str, description: str, properties: dict | None = None, required: list | None = None) -> dict:
    return {
        "name": name,
        "description": description,
        "parameters": {"type": "object", "properties": properties or {}, "required": required or []},
    }


TOOLS = [
    _fn("get_clinic_info", "Look up clinic-approved answers: timings, address, doctors, fees, payment, parking. "
        "Use for any clinic question not already in your instructions.",
        {"question": {"type": "string", "description": "The caller's question in their words."}}, ["question"]),
    _fn("find_slots", "Find free appointment slots nearest to the preferred day and time. Offer only what this returns.",
        {"date": _DATE, "time": _TIME,
         "doctor": {"type": "string", "description": "Doctor's name if the caller asked for one, else omit."}},
        ["date"]),
    _fn("book", "Book a slot returned by find_slots, after reading back day, date, time and doctor and getting a yes.",
        {"name": _NAME, "phone": _PHONE, "date": _DATE, "time": _TIME,
         "doctor": {"type": "string", "description": "Doctor exactly as find_slots returned."},
         "reason": {"type": "string", "description": "Optional short non-medical reason: checkup, cleaning, daant dard."}},
        ["name", "phone", "date", "time", "doctor"]),
    _fn("find_booking", "Find the caller's upcoming appointments by phone number, before moving or cancelling.",
        {"phone": _PHONE}, ["phone"]),
    _fn("reschedule", "Move an existing appointment to a new free slot (from find_slots).",
        {"booking_id": {"type": "integer", "description": "Booking number from find_booking."},
         "phone": _PHONE, "new_date": _DATE, "new_time": _TIME,
         "doctor": {"type": "string", "description": "Doctor for the new slot as find_slots returned."}},
        ["new_date", "new_time"]),
    _fn("cancel", "Cancel an existing appointment after the caller confirms.",
        {"booking_id": {"type": "integer", "description": "Booking number from find_booking."},
         "phone": _PHONE, "date": _DATE}),
    _fn("create_callback", "Ask clinic staff to call the caller back: unknown questions, staff requests, anything you cannot do.",
        {"name": _NAME, "phone": _PHONE,
         "reason": {"type": "string", "enum": ["unanswered_question", "staff_request", "failover", "other"]},
         "note": {"type": "string", "description": "One short line for the staff. No medical details beyond what the caller said."},
         "urgent": {"type": "boolean"}},
        ["name", "phone", "reason", "note"]),
    _fn("escalate", "Alert the doctor now: red-flag symptoms, anything possibly medical that is not clearly routine, "
        "or an upset caller who needs a person urgently.",
        {"category": {"type": "string", "enum": ["red_flag", "grey_zone", "caller_request"]},
         "summary": {"type": "string", "description": "Two short lines: what the caller said and what they want."},
         "name": _NAME, "phone": _PHONE,
         "matched_rule": {"type": "string", "description": "Which red flag, if any."}},
        ["category", "summary"]),
    _fn("transfer", "Not available on this line; escalate instead.", {}),
    _fn("log_call_outcome", "Optional. The outcome is recorded automatically.",
        {"outcome": {"type": "string", "enum": ["booked", "answered", "escalated", "callback", "hung_up"]}}),
]

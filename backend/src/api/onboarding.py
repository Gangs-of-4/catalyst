"""Templates list and self-serve signup: an account and a business in one step (ADR-0038, contracts §6).

The template section of the form is chosen by the template's `modules` in vertical.yaml, never by
its name, so a new template with the same modules needs no code here.
"""

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field, ValidationError, field_validator

from .. import accounts
from ..agents import instructions
from ..core import db, tenancy
from ..core import phone as ph
from ..core import settings as cs
from ..core.log import log
from ..verticals import loader
from .auth import EMAIL, set_session_cookie
from .deps import require_csrf_header
from .errors import ApiError, plain_fields
from .setup import HHMM, Doctor, Faq, Service
from .sync import sync_tenant_agent

router = APIRouter(prefix="/api", dependencies=[Depends(require_csrf_header)])
MAX_INSTRUCTIONS = 500
# Which wording of the "we store these details" line was ticked. Bump it when the text changes.
CONSENT_VERSION = "2026-11-phase2-v1"


class UserIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        if not EMAIL.match(v.strip()):
            raise ValueError("Enter an email like name@example.com.")
        return v.strip()

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        if len(v) < accounts.MIN_PASSWORD:
            raise ValueError(f"Choose a password of at least {accounts.MIN_PASSWORD} characters.")
        return v


class BusinessIn(BaseModel):
    template: str
    name: str = Field(min_length=2, max_length=80)
    city: str = Field(default="", max_length=60)
    address: str = Field(min_length=2, max_length=200)
    landmark: str = Field(default="", max_length=120)
    hours: list[tuple[str, str]] = Field(min_length=1, max_length=4)
    closed_weekdays: list[int] = []
    owner_whatsapp: str
    voice: str = "female"
    consent: bool = False

    @field_validator("hours")
    @classmethod
    def _hours(cls, v):
        for start, end in v:
            if not (HHMM.match(start) and HHMM.match(end)) or start >= end:
                raise ValueError(
                    f"Opening hours '{start}-{end}' must look like 10:00-14:00, start before end."
                )
        return sorted(v)

    @field_validator("closed_weekdays")
    @classmethod
    def _weekdays(cls, v):
        if any(d not in range(7) for d in v):
            raise ValueError("Closed days must be 0 (Monday) to 6 (Sunday).")
        return sorted(set(v))

    @field_validator("owner_whatsapp")
    @classmethod
    def _whatsapp(cls, v):
        n = ph.normalize(v)
        if not n:
            raise ValueError("Enter your 10-digit Indian mobile number for WhatsApp.")
        return n

    @field_validator("voice")
    @classmethod
    def _voice(cls, v):
        if v not in ("female", "male"):
            raise ValueError("Voice must be female or male.")
        return v

    @field_validator("consent")
    @classmethod
    def _consent(cls, v):
        if v is not True:
            raise ValueError(
                "Please tick the box to say you're happy for us to store these details."
            )
        return v


class BookingsDetails(BaseModel):
    """Template section for templates whose module is `bookings` (clinics)."""

    doctors: list[Doctor] = Field(min_length=1, max_length=8)
    services: list[Service] = []
    slot_min: int | None = Field(default=None, ge=10, le=120)
    emergency_instruction: str | None = Field(default=None, min_length=10, max_length=600)


class OrdersDetails(BaseModel):
    """Template section for templates whose module is `orders` (wholesale)."""

    min_order: str = Field(default="", max_length=60)
    delivery_area: str = Field(default="", max_length=120)


DETAILS = {"bookings": BookingsDetails, "orders": OrdersDetails}


class SignupIn(BaseModel):
    user: UserIn
    business: BusinessIn
    details: dict = {}
    faqs: list[Faq] = []
    instructions: str = ""  # length-checked here; kept as pending_instructions until M5 screens it

    @field_validator("instructions")
    @classmethod
    def _instructions(cls, v: str) -> str:
        if len(v) > MAX_INSTRUCTIONS:
            raise ValueError(f"Keep the extra instructions under {MAX_INSTRUCTIONS} characters.")
        return v


def _template_or_422(name: str) -> dict:
    if name not in tenancy.templates():
        raise ApiError(
            422,
            "VALIDATION",
            f"Pick one of: {', '.join(tenancy.templates())}.",
            {"business.template": f"Pick one of: {', '.join(tenancy.templates())}."},
        )
    return loader.template_defaults(name)


def build_settings(t: dict, body: SignupIn) -> dict:
    """The new business's settings document, from the template defaults plus the owner's answers."""
    b = body.business
    modules = t["modules"]
    parsed: dict = {}
    fields: dict = {}
    for m in modules:  # each module checks its own part of `details`
        try:
            parsed[m] = DETAILS[m].model_validate(body.details)
        except ValidationError as e:
            fields.update(plain_fields(e.errors(), prefix="details"))
    if fields:
        raise ApiError(422, "VALIDATION", " ".join(dict.fromkeys(fields.values())), fields)
    s: dict = {
        "name": b.name.strip(),
        "city": b.city.strip(),
        "address": b.address.strip(),
        "landmark": b.landmark.strip(),
        "sessions": [list(x) for x in b.hours],
        "closed_weekdays": b.closed_weekdays,
        "faqs": [f.model_dump() for f in body.faqs],
        "whatsapp_numbers": [b.owner_whatsapp],
        "voice": b.voice,
        "labels": t["labels"],
        "confirm_words": t["confirm_words"],
        "reject_words": t["reject_words"],
        "preview_expiry_min": t["preview_expiry_min"],
    }
    if "bookings" in modules:
        d = parsed["bookings"]
        taken: set[str] = set()
        doctors = []
        for doc in d.doctors:
            did = cs.doctor_slug(doc.name, taken)
            taken.add(did)
            doctors.append({"id": did, "name": doc.name.strip()})
        s.update(
            doctors=doctors,
            services=[x.model_dump() for x in d.services] or t["onboarding"].get("services", []),
            slot_min=d.slot_min or t["onboarding"].get("slot_min") or t["default_slot_min"],
            offer_slots=t["offer_slots"],
            red_flags=t["red_flags"],
            emergency_instruction=" ".join(
                (
                    d.emergency_instruction or t["onboarding"].get("emergency_instruction", "")
                ).split()
            ),
        )
    if "orders" in modules:
        d = parsed["orders"]
        s.update(min_order=d.min_order.strip(), delivery_area=d.delivery_area.strip())
    # Evidence of consent (ADR-0039): when, and which wording. The box has to be ticked to get here.
    s["consent"] = {"at": db.stamp(), "version": CONSENT_VERSION}
    return s


@router.get("/templates")
def templates() -> dict:
    """What the onboarding form needs per template: labels, form defaults and whether a voice
    agent exists for it yet."""
    out = []
    for name in tenancy.templates():
        t = loader.template_defaults(name)
        out.append(
            {
                "template": name,
                "label": t["labels"].get("tenant", name.title()),
                "labels": t["labels"],
                "modules": t["modules"],
                "defaults": t["onboarding"],
                "has_voice": t["has_voice"],
            }
        )
    return {"templates": out}


@router.get("/templates/{template}/sample-catalog.csv")
def sample_catalog(template: str) -> Response:
    """The template's example catalogue, for the "Download sample" link next to CSV upload."""
    if template not in tenancy.templates():
        raise ApiError(404, "NOT_FOUND", "No such template.")
    path = loader.template_dir(template) / "sample-catalog.csv"
    if not path.exists():
        raise ApiError(404, "NOT_FOUND", "This template has no catalogue.")
    return Response(
        path.read_bytes(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{template}-sample-catalog.csv"'},
    )


def _instructions_state(text: str, screened: instructions.Screened) -> str:
    """ "saved" (some lines accepted), "rejected" (every line rejected) or "none"."""
    if not text.strip():
        return "none"
    return "saved" if screened.accepted else "rejected"


def _undo_signup(conn: db.Conn, tid: str) -> None:
    try:
        tenancy.delete(conn, tid)
    except Exception as e:  # keep the original error; this one is only logged (IDs only, no PII)
        log.warning("signup: could not remove unfinished business %s (%s)", tid, type(e).__name__)


@router.post("/signup")
def signup(body: SignupIn, request: Request, response: Response) -> dict:
    t = _template_or_422(body.business.template)
    settings = build_settings(t, body)

    pre = db.connect_unchecked()  # nothing is scoped to a business yet
    try:
        if accounts.email_taken(pre, body.user.email):
            raise ApiError(
                409,
                "EMAIL_TAKEN",
                "That email already has an account. Log in instead.",
                {"user.email": "That email already has an account."},
            )
        if tenancy.number_taken(pre, body.business.owner_whatsapp):
            raise ApiError(
                409,
                "WHATSAPP_TAKEN",
                "That WhatsApp number already belongs to another business.",
                {"business.owner_whatsapp": "That number is already registered."},
            )
    finally:
        pre.close()

    conn = db.connect()
    try:
        try:
            tid = tenancy.create(
                conn, body.business.template, settings, owner_whatsapp=body.business.owner_whatsapp
            )
        except db.Conflict:  # a second signup with the same number won the race
            raise ApiError(
                409,
                "WHATSAPP_TAKEN",
                "That WhatsApp number already belongs to another business.",
                {"business.owner_whatsapp": "That number is already registered."},
            ) from None
        scoped = conn.for_tenant(tid)
        try:
            uid = accounts.create_user(
                scoped, tid, body.user.name, body.user.email, body.user.password
            )
            cookie = accounts.start_session(scoped, uid, tid)
            # Screened before the assistant is built: only accepted lines reach the prompt.
            screened = instructions.Screened()
            if body.instructions.strip():
                _, screened = instructions.save(scoped, body.instructions, "web")
            public_id = tenancy.get(conn, tid)["public_id"]
        except Exception as e:
            # Undo the half-made business so a retry isn't refused with WHATSAPP_TAKEN.
            _undo_signup(conn, tid)
            if isinstance(e, accounts.EmailTaken):  # same race, on the email
                raise ApiError(
                    409,
                    "EMAIL_TAKEN",
                    "That email already has an account. Log in instead.",
                    {"user.email": "That email already has an account."},
                ) from None
            raise
    finally:
        conn.close()

    agent = sync_tenant_agent(tid)  # the business exists either way; the test page shows the state
    set_session_cookie(response, request, cookie)
    return {
        "public_id": public_id,
        "template": body.business.template,
        "agent": agent,
        "instructions": _instructions_state(body.instructions, screened),
        "rejected": screened.rejected,
    }

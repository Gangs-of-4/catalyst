/**
 * Signup form logic, kept free of React so it can be unit-tested.
 *
 * Shapes follow contracts.md §6 (`GET /api/templates`, `POST /api/signup`) and the backend models in
 * backend/src/api/onboarding.py. Error keys use the API's own field paths ("user.email",
 * "details.doctors.0.name"), so browser checks and server errors land on the same inputs.
 *
 * The template's section is chosen by its `modules`, never by its name (ADR-0033).
 */

export type Labels = Partial<Record<"resource" | "resource_plural" | "contact" | "booking" | "tenant", string>>;

export type TemplateDefaults = {
  slot_min?: number;
  sessions?: [string, string][];
  closed_weekdays?: number[];
  services?: { name: string; fee: string }[];
  emergency_instruction?: string;
  min_order?: string;
  delivery_area?: string;
};

export type Template = {
  template: string;
  label: string;
  labels: Labels;
  modules: string[];
  defaults: TemplateDefaults;
  has_voice: boolean;
};

export type AgentState = "updated" | "not_configured" | "failed";

export type SignupResponse = { public_id: string; template: string; agent: AgentState };

export type Hours = { start: string; end: string };
export type NameRow = { name: string };
export type ServiceRow = { name: string; fee: string };
export type FaqRow = { q: string; a: string };

export type SignupForm = {
  user: { name: string; email: string; password: string };
  business: {
    template: string;
    name: string;
    city: string;
    address: string;
    landmark: string;
    hours: Hours[];
    closed_weekdays: number[];
    owner_whatsapp: string;
    voice: "female" | "male";
    consent: boolean;
  };
  bookings: { doctors: NameRow[]; services: ServiceRow[]; slot_min: number; emergency_instruction: string };
  orders: { min_order: string; delivery_area: string };
  faqs: FaqRow[];
  instructions: string;
};

export type FieldErrors = Record<string, string>;

export const MAX_INSTRUCTIONS = 500;
export const MIN_PASSWORD = 8;
export const MAX_HOURS_ROWS = 4;
export const MAX_DOCTORS = 8;
export const SLOT_CHOICES = [10, 15, 20, 30, 45, 60] as const;
/** 0 = Monday … 6 = Sunday, as the backend stores closed days. */
export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

const DEFAULT_SESSIONS: [string, string][] = [["10:00", "18:00"]];
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/;

export const hasModule = (t: Pick<Template, "modules"> | undefined, m: string) => !!t?.modules.includes(m);

/** A fresh form for `template`, prefilled from its vertical.yaml onboarding defaults. */
export function initialForm(template?: Template): SignupForm {
  const d = template?.defaults ?? {};
  return {
    user: { name: "", email: "", password: "" },
    business: {
      template: template?.template ?? "",
      name: "",
      city: "",
      address: "",
      landmark: "",
      hours: (d.sessions?.length ? d.sessions : DEFAULT_SESSIONS).map(([start, end]) => ({ start, end })),
      closed_weekdays: d.closed_weekdays ?? [],
      owner_whatsapp: "",
      voice: "female",
      consent: false,
    },
    bookings: {
      doctors: [{ name: "" }],
      services: d.services?.length ? d.services.map((s) => ({ ...s })) : [{ name: "", fee: "" }],
      slot_min: d.slot_min ?? 15,
      emergency_instruction: (d.emergency_instruction ?? "").trim(),
    },
    orders: { min_order: d.min_order ?? "", delivery_area: d.delivery_area ?? "" },
    faqs: [],
    instructions: "",
  };
}

/**
 * Switch template, keeping everything the owner typed that both templates share
 * (account, business details, optional section) and resetting the template-specific parts.
 */
export function switchTemplate(form: SignupForm, template: Template): SignupForm {
  const fresh = initialForm(template);
  return {
    ...fresh,
    user: form.user,
    business: {
      ...form.business,
      template: template.template,
      hours: fresh.business.hours,
      closed_weekdays: fresh.business.closed_weekdays,
    },
    faqs: form.faqs,
    instructions: form.instructions,
  };
}

/** '98765 43210', '09876543210', '+91 98765 43210' → '+919876543210'; null if not an Indian mobile. */
export function normalizeMobile(raw: string): string | null {
  let digits = raw.replace(/\D/g, "");
  if (digits.length === 12 && digits.startsWith("91")) digits = digits.slice(2);
  else if (digits.length === 11 && digits.startsWith("0")) digits = digits.slice(1);
  return /^[6-9]\d{9}$/.test(digits) ? `+91${digits}` : null;
}

const blankRow = (row: Record<string, string>) => Object.values(row).every((v) => !v.trim());

/** Quick checks in the browser, worded like the server's. The server stays the source of truth. */
export function validate(form: SignupForm, template: Template | undefined): FieldErrors {
  const e: FieldErrors = {};
  const { user, business: b } = form;

  if (user.name.trim().length < 2) e["user.name"] = "Please fill in your name.";
  if (!EMAIL.test(user.email.trim())) e["user.email"] = "Enter an email like name@example.com.";
  if (user.password.length < MIN_PASSWORD)
    e["user.password"] = `Choose a password of at least ${MIN_PASSWORD} characters.`;

  if (!template) e["business.template"] = "Pick what kind of business you run.";
  if (b.name.trim().length < 2) e["business.name"] = "Please fill in your business name.";
  if (b.address.trim().length < 2) e["business.address"] = "Please fill in your address.";
  b.hours.forEach((h, i) => {
    if (!HHMM.test(h.start) || !HHMM.test(h.end) || h.start >= h.end)
      e[`business.hours.${i}`] = "Start must be before end, like 10:00 to 14:00.";
  });
  if (!b.hours.length) e["business.hours"] = "Add at least one opening time.";
  if (!normalizeMobile(b.owner_whatsapp))
    e["business.owner_whatsapp"] = "Enter your 10-digit Indian mobile number for WhatsApp.";
  if (!b.consent) e["business.consent"] = "Please tick the box to say you're happy for us to store these details.";

  if (hasModule(template, "bookings")) {
    const resource = (template?.labels.resource ?? "Doctor").toLowerCase();
    const named = form.bookings.doctors.filter((d) => d.name.trim());
    if (!named.length) e["details.doctors"] = `Add at least one ${resource}.`;
    form.bookings.doctors.forEach((d, i) => {
      if (d.name.trim() && d.name.trim().length < 2) e[`details.doctors.${i}.name`] = "Please fill in the name.";
    });
    form.bookings.services.forEach((s, i) => {
      if (blankRow(s)) return;
      if (!s.name.trim()) e[`details.services.${i}.name`] = "Please fill in the service.";
      if (!s.fee.trim()) e[`details.services.${i}.fee`] = "Please fill in the fee.";
    });
    const em = form.bookings.emergency_instruction.trim();
    if (em && em.length < 10) e["details.emergency_instruction"] = "Please write a full sentence for emergencies.";
  }

  form.faqs.forEach((f, i) => {
    if (blankRow(f)) return;
    if (f.q.trim().length < 2) e[`faqs.${i}.q`] = "Please fill in the question.";
    if (!f.a.trim()) e[`faqs.${i}.a`] = "Please fill in the answer.";
  });
  if (form.instructions.trim().length > MAX_INSTRUCTIONS)
    e["instructions"] = `Keep the extra instructions under ${MAX_INSTRUCTIONS} characters.`;
  return e;
}

/** For each list the payload filters, the form row index behind each sent item. */
export type RowMaps = Record<"details.doctors" | "details.services" | "faqs", number[]>;

function keep<T>(rows: T[], isBlank: (row: T) => boolean): { items: T[]; map: number[] } {
  const map: number[] = [];
  rows.forEach((row, i) => {
    if (!isBlank(row)) map.push(i);
  });
  return { items: map.map((i) => rows[i]!), map };
}

/** The `POST /api/signup` body (contracts.md §6), plus row maps. Blank optional rows are dropped. */
export function toPayload(form: SignupForm, template: Template) {
  const b = form.business;
  const details: Record<string, unknown> = {};
  const doctors = keep(form.bookings.doctors, (d) => !d.name.trim());
  const services = keep(form.bookings.services, blankRow);
  const faqs = keep(form.faqs, blankRow);
  const rowMaps: RowMaps = { "details.doctors": doctors.map, "details.services": services.map, faqs: faqs.map };

  if (hasModule(template, "bookings")) {
    details.doctors = doctors.items.map((d) => ({ name: d.name.trim() }));
    details.services = services.items.map((s) => ({ name: s.name.trim(), fee: s.fee.trim() }));
    details.slot_min = form.bookings.slot_min;
    const em = form.bookings.emergency_instruction.trim();
    if (em) details.emergency_instruction = em;
  }
  if (hasModule(template, "orders")) {
    details.min_order = form.orders.min_order.trim();
    details.delivery_area = form.orders.delivery_area.trim();
  }
  const body = {
    user: { name: form.user.name.trim(), email: form.user.email.trim(), password: form.user.password },
    business: {
      template: template.template,
      name: b.name.trim(),
      city: b.city.trim(),
      address: b.address.trim(),
      landmark: b.landmark.trim(),
      hours: b.hours.map((h) => [h.start, h.end]),
      closed_weekdays: [...b.closed_weekdays].sort((x, y) => x - y),
      owner_whatsapp: normalizeMobile(b.owner_whatsapp) ?? b.owner_whatsapp.trim(),
      voice: b.voice,
      consent: b.consent,
    },
    details,
    faqs: faqs.items.map((f) => ({ q: f.q.trim(), a: f.a.trim() })),
    instructions: form.instructions.trim(),
  };
  return { body, rowMaps };
}

/**
 * Put server field errors back on the rows the page renders. Dropping blank rows shifts array
 * indexes, so "details.services.0.fee" may really be the form's row 2.
 */
export function remapErrors(fields: FieldErrors, rowMaps: RowMaps): FieldErrors {
  const out: FieldErrors = {};
  for (const [key, message] of Object.entries(fields)) {
    let mapped = key;
    for (const [list, map] of Object.entries(rowMaps)) {
      const m = key.match(new RegExp(`^${list.replace(".", "\\.")}\\.(\\d+)(\\..+)?$`));
      if (m) {
        const formIndex = map[Number(m[1])];
        if (formIndex !== undefined) mapped = `${list}.${formIndex}${m[2] ?? ""}`;
        break;
      }
    }
    out[mapped] ??= message;
  }
  return out;
}

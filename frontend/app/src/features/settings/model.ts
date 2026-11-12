/**
 * The settings form: the API's settings as editable rows (phones show "+91 90000 00001" style
 * numbers as typed), and back to the PUT body. Pure functions, so they're easy to test.
 */
import type { Hours } from "@/features/signup/model";

import { type Faq, isBookings, type Service, type Settings } from "./api";

export type Form = {
  kind: "bookings" | "orders";
  name: string;
  city: string;
  address: string;
  landmark: string;
  hours: Hours[];
  closed_weekdays: number[];
  faqs: Faq[];
  whatsapp_numbers: string[];
  voice: "female" | "male";
  // bookings
  slot_min: string;
  doctors: { id?: string; name: string }[];
  services: Service[];
  red_flags: string[];
  emergency_instruction: string;
  // orders
  min_order: string;
  delivery_area: string;
};

export const SLOT_CHOICES = [10, 15, 20, 30, 45, 60] as const;
export const MAX_DOCTORS = 8;
export const MAX_SESSIONS = 4;

/** "+919000000001" → "90000 00001" for editing; the backend accepts either. */
const showPhone = (p: string) => p.replace(/^\+91(\d{5})(\d{5})$/, "$1 $2");

export function toForm(s: Settings): Form {
  const base = {
    name: s.name ?? "",
    city: s.city ?? "",
    address: s.address ?? "",
    landmark: s.landmark ?? "",
    hours: (s.sessions ?? []).map(([start, end]) => ({ start, end })),
    closed_weekdays: [...(s.closed_weekdays ?? [])],
    faqs: (s.faqs ?? []).map((f) => ({ ...f })),
    whatsapp_numbers: (s.whatsapp_numbers ?? []).map(showPhone),
    voice: s.voice === "male" ? ("male" as const) : ("female" as const),
    slot_min: "15",
    doctors: [] as Form["doctors"],
    services: [] as Service[],
    red_flags: [] as string[],
    emergency_instruction: "",
    min_order: "",
    delivery_area: "",
  };
  if (isBookings(s)) {
    return {
      ...base,
      kind: "bookings",
      slot_min: String(s.slot_min ?? 15),
      doctors: s.doctors.map((d) => ({ id: d.id, name: d.name })),
      services: (s.services ?? []).map((x) => ({ ...x })),
      red_flags: [...(s.red_flags ?? [])],
      emergency_instruction: s.emergency_instruction ?? "",
    };
  }
  return { ...base, kind: "orders", min_order: s.min_order ?? "", delivery_area: s.delivery_area ?? "" };
}

/** The PUT body. Empty optional rows are dropped, so a half-added row never blocks a save. */
export function toBody(f: Form): Settings {
  const common = {
    name: f.name.trim(),
    city: f.city.trim(),
    address: f.address.trim(),
    landmark: f.landmark.trim(),
    sessions: f.hours.map((h) => [h.start, h.end] as [string, string]),
    closed_weekdays: f.closed_weekdays,
    faqs: f.faqs.filter((x) => x.q.trim() || x.a.trim()).map((x) => ({ q: x.q.trim(), a: x.a.trim() })),
    whatsapp_numbers: f.whatsapp_numbers.map((n) => n.trim()).filter(Boolean),
    voice: f.voice,
  };
  if (f.kind === "orders") return { ...common, min_order: f.min_order.trim(), delivery_area: f.delivery_area.trim() };
  return {
    ...common,
    slot_min: Number(f.slot_min),
    doctors: f.doctors.map((d) => ({ ...(d.id ? { id: d.id } : {}), name: d.name.trim() })),
    services: f.services.filter((x) => x.name.trim() || x.fee.trim()).map((x) => ({ name: x.name.trim(), fee: x.fee.trim() })),
    red_flags: f.red_flags.map((r) => r.trim()).filter(Boolean),
    emergency_instruction: f.emergency_instruction.trim(),
  };
}

/** Whether the form differs from what was loaded (what the save bar shows). */
export const isDirty = (f: Form, saved: Form) => JSON.stringify(toBody(f)) !== JSON.stringify(toBody(saved));

/**
 * The API names fields by their path in the body ("doctors.0.name", "sessions"); the hours editor
 * from signup reads "business.hours.<i>". Map once so every input finds its message.
 */
export function formErrors(fields: Record<string, string>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(fields)) {
    const m = /^sessions(?:\.(\d+))?/.exec(k);
    if (m) out[m[1] !== undefined ? `business.hours.${m[1]}` : "sessions"] = v;
    else out[k] = v;
  }
  return out;
}

/** Quick checks before sending, in the same words the API would use. */
export function check(f: Form): Record<string, string> {
  const e: Record<string, string> = {};
  if (f.name.trim().length < 2) e.name = "Please write the business name.";
  if (f.address.trim().length < 2) e.address = "Please write the address.";
  if (f.hours.length === 0) e.sessions = "Add at least one opening time.";
  f.hours.forEach((h, i) => {
    if (!h.start || !h.end || h.start >= h.end) e[`business.hours.${i}`] = "The opening time must be before the closing time.";
  });
  if (f.closed_weekdays.length === 7) e.closed_weekdays = "The business can't be closed every day.";
  f.faqs.forEach((x, i) => {
    if (x.q.trim() && !x.a.trim()) e[`faqs.${i}.a`] = "Write the answer, or remove this question.";
    if (!x.q.trim() && x.a.trim()) e[`faqs.${i}.q`] = "Write the question, or remove this answer.";
  });
  if (f.kind === "bookings") {
    if (f.doctors.length === 0) e.doctors = "Add at least one doctor.";
    f.doctors.forEach((d, i) => {
      if (d.name.trim().length < 2) e[`doctors.${i}.name`] = "Write the doctor's name.";
    });
    f.services.forEach((x, i) => {
      if (x.name.trim() && !x.fee.trim()) e[`services.${i}.fee`] = "Write the fee, or remove this service.";
      if (!x.name.trim() && x.fee.trim()) e[`services.${i}.name`] = "Write the service name.";
    });
    if (f.emergency_instruction.trim().length < 10) e.emergency_instruction = "Write what callers should do in an emergency.";
  }
  return e;
}

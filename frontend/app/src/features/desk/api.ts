/** Desk endpoints (contracts.md §6.1): the day's register, walk-ins, statuses, inbox, calls, stats. */
import { api } from "@/lib/api";

export type Source = "phone" | "whatsapp" | "walk_in";
export type Status = "booked" | "arrived" | "no_show" | "done" | "cancelled";

export type Booking = {
  id: number;
  resource_id: string;
  date: string;
  time: string;
  status: Status;
  source: Source;
  name: string;
  phone: string | null;
  reason: string | null;
};

export type Slot = {
  time: string;
  state: "free" | "booked" | "blocked" | "past";
  past: boolean;
  bookings: Booking[];
  /** Why it's blocked: "closed", or a block kind such as "leave". */
  block: string | null;
};

export type Doctor = { id: string; name: string };

export type Day = {
  date: string;
  closed: boolean;
  columns: { doctor: Doctor; slots: Slot[] }[];
  /** Bookings at times that are no longer slot starts (e.g. after a slot-length change). */
  stray: Booking[];
  label: string;
  long: string;
  short: string;
};

export type InboxItem = {
  id: number;
  kind: "escalation" | "callback" | "ops";
  urgent: number | boolean;
  name: string | null;
  phone: string | null;
  reason: string | null;
  note: string | null;
  created_at: string;
};

export type Call = {
  id: string;
  started_at: string;
  outcome: string | null;
  summary: string | null;
  transcript: string | null;
  safety_review: number | boolean;
  safety_hits: string[];
};

export type Stats = { sentence: string; urgent_open: number; callbacks_open: number; appointments: number; calls: number };

/** A free time the backend offers when the one asked for is taken or closed. */
export type Alternative = { doctor_id: string; date: string; time: string };

export type WalkInBody = {
  doctor_id: string;
  date: string;
  time: string;
  name: string;
  phone: string | null;
  source: "walk_in" | "whatsapp";
};

export const getDay = (date: string | null, signal?: AbortSignal) =>
  api<Day>(`/api/desk/day${date ? `?date=${encodeURIComponent(date)}` : ""}`, { signal });

export const addBooking = (body: WalkInBody) => api<{ id: number }>("/api/desk/bookings", { method: "POST", body });

export const setStatus = (id: number, status: Status) =>
  api<{ ok: boolean }>(`/api/desk/bookings/${id}/status`, { method: "POST", body: { status } });

export const getInbox = (signal?: AbortSignal) => api<InboxItem[]>("/api/inbox", { signal });
export const markDone = (id: number) => api<{ ok: boolean }>(`/api/inbox/${id}/done`, { method: "POST" });
export const getCalls = (signal?: AbortSignal) => api<Call[]>("/api/calls", { signal });
export const getStats = (signal?: AbortSignal) => api<Stats>("/api/stats", { signal });

/** "14:30" → "2:30 pm". */
export function time12(hhmm: string): string {
  const [h = 0, m = 0] = hhmm.split(":").map(Number);
  const suffix = h >= 12 ? "pm" : "am";
  return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${suffix}`;
}

/** "+919000000001" → "90000 00001"; anything else as-is. */
export const formatPhone = (p: string | null) => (p ?? "").replace(/^\+91(\d{5})(\d{5})$/, "$1 $2");

/** Move an ISO date by whole days, without time-zone drift. */
export function shiftDate(iso: string, days: number): string {
  const [y = 1970, m = 1, d = 1] = iso.split("-").map(Number);
  const t = new Date(Date.UTC(y, m - 1, d + days));
  return t.toISOString().slice(0, 10);
}

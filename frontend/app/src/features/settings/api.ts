/** Business settings (contracts.md §6.1 `GET/PUT /api/settings`). */
import { api } from "@/lib/api";

export type Faq = { q: string; a: string };
export type Doctor = { id?: string; name: string };
export type Service = { name: string; fee: string };

/** What every business has, whatever its template. */
type Common = {
  name: string;
  city: string;
  address: string;
  landmark: string;
  sessions: [string, string][];
  closed_weekdays: number[];
  faqs: Faq[];
  whatsapp_numbers: string[];
  voice: "female" | "male";
};

/** A bookings template (clinic). */
export type BookingsSettings = Common & {
  slot_min: number;
  doctors: Doctor[];
  services: Service[];
  red_flags: string[];
  emergency_instruction: string;
};

/** An orders template (wholesale). Products live in the catalogue, not here. */
export type OrdersSettings = Common & { min_order: string; delivery_area: string };

export type Settings = BookingsSettings | OrdersSettings;

export const isBookings = (s: Settings): s is BookingsSettings => Array.isArray((s as BookingsSettings).doctors);

/** A leave day (one doctor) or holiday (whole business). `label` is written by the backend. */
export type Block = { id: number; date: string; resource_id: string | null; kind: string; label: string };

export type SettingsResponse = { settings: Settings; blocks: Block[]; agentConfigured: boolean };
export type SaveResponse = { saved: true; agent: string; settings: Settings };

export const getSettings = (signal?: AbortSignal) => api<SettingsResponse>("/api/settings", { signal });
export const saveSettings = (body: Settings) => api<SaveResponse>("/api/settings", { method: "PUT", body });

export const addBlock = (date: string, doctorId: string | null) =>
  api<{ blocks: Block[]; note: string | null; agent: string }>("/api/settings/blocks", {
    method: "POST",
    body: { date, doctor_id: doctorId },
  });

export const removeBlock = (id: number) =>
  api<{ blocks: Block[]; agent: string }>(`/api/settings/blocks/${id}`, { method: "DELETE" });

/** Custom instructions ("Agent ko aur kya batana hai?"), screened line by line (contracts.md §6.1). */
export type Rejected = { line: string; reason: string };
export type InstructionsState = { text: string; version_id: number | null; rejected: Rejected[]; max_chars: number };
export type InstructionsSave = { accepted: string[]; rejected: Rejected[]; version_id: number | null; agent: string };

export const getInstructions = (signal?: AbortSignal) => api<InstructionsState>("/api/instructions", { signal });
export const saveInstructions = (text: string) =>
  api<InstructionsSave>("/api/instructions", { method: "PUT", body: { text } });
export const undoInstructions = () =>
  api<{ text: string; version_id: number | null; agent: string }>("/api/instructions/undo", { method: "POST" });

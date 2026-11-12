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

export type SettingsResponse = { settings: Settings; agentConfigured: boolean };
export type SaveResponse = { saved: true; agent: string; settings: Settings };

export const getSettings = (signal?: AbortSignal) => api<SettingsResponse>("/api/settings", { signal });
export const saveSettings = (body: Settings) => api<SaveResponse>("/api/settings", { method: "PUT", body });

/** Admin endpoints for our team (contracts.md §6.1–§6.2): usage evidence and the feedback log. */
import { api } from "@/lib/api";

export type Week = { week_start: string; events: number; records: number; calls: number; wa_commands: number };

export type Business = {
  id: string;
  name: string;
  public_id: string;
  template: string;
  created_at: string;
  is_demo: boolean;
  users: number;
  records: number;
  calls: number;
  wa_commands: number;
  last_active: string | null;
  /** The last 4 ISO weeks (Monday start, IST), oldest first. */
  weeks: Week[];
};

export type Decision = "shipped" | "in_progress" | "planned" | "wont_do";

export type FeedbackRow = {
  id: number;
  business: string;
  person_name: string;
  person_role: string;
  text: string;
  type: string;
  decision: Decision | null;
  decision_reason: string | null;
  shipped_on: string | null;
  evidence_url: string | null;
  partner_reaction: string | null;
  created_at: string;
};

export type DecisionIn = {
  decision: Decision | null;
  decision_reason: string;
  shipped_on: string | null;
  evidence_url: string;
  partner_reaction: string;
};

export const adminLogin = (password: string) => api<{ ok: boolean }>("/api/admin/login", { method: "POST", body: { password } });

export const getBusinesses = (signal?: AbortSignal) => api<{ businesses: Business[] }>("/api/admin/businesses", { signal });

export const getFeedback = (signal?: AbortSignal) =>
  api<{ feedback: FeedbackRow[]; types: string[]; decisions: Decision[] }>("/api/admin/feedback", { signal });

export const decideFeedback = (id: number, body: DecisionIn) =>
  api<FeedbackRow>(`/api/admin/feedback/${id}`, { method: "PUT", body });

/** CSV downloads are plain GET links: the browser sends the admin cookie. */
export const usageCsvUrl = (id: string) => `/api/admin/businesses/${encodeURIComponent(id)}/usage.csv`;
export const FEEDBACK_CSV_URL = "/api/admin/feedback.csv";

export const DECISION_WORDS: Record<Decision, string> = {
  shipped: "Shipped",
  in_progress: "In progress",
  planned: "Planned",
  wont_do: "Won't do",
};

export const TYPE_WORDS: Record<string, string> = {
  bug: "Bug",
  feature: "Feature",
  usability: "Usability",
  data_integration: "Data / integration",
  pricing_business: "Pricing / business",
};

/* ---------- Dashboard (issue #56; the shapes proposed there, until contracts §6.2 has them) ---------- */

export type Totals = {
  businesses: number;
  active_businesses_7d: number;
  users: number;
  active_users_7d: number;
  calls: number;
  call_minutes: number;
  records: { bookings: number; orders: number };
  records_by_source: Partial<Record<"phone" | "whatsapp" | "walk_in", number>>;
  wa_commands: number;
  feedback: number;
  app_minutes: number;
};

export type FeatureCount = { type: string; count: number };

export type Day = {
  date: string;
  active_businesses?: number;
  events: number;
  calls: number;
  call_minutes: number;
  app_minutes: number;
};

export type Overview = { generated_at: string; real: Totals; demo: Totals; features: FeatureCount[]; daily: Day[] };

export type BusinessUser = { id: string; role: string; last_active: string | null; logins: number; app_minutes: number; active_days: number };

export type BusinessDetail = { business: Business; features: FeatureCount[]; daily: Day[]; users: BusinessUser[] };

/** `scope`: real businesses (default), the demo businesses, or both: the demos hold most data before launch. */
export type Scope = "real" | "demo" | "all";

export const getOverview = (scope: Scope, signal?: AbortSignal) =>
  api<Overview>(`/api/admin/overview?scope=${scope}`, { signal });

export const getBusinessDetail = (id: string, signal?: AbortSignal) =>
  api<BusinessDetail>(`/api/admin/businesses/${encodeURIComponent(id)}`, { signal });

/** Event types (contracts §3.1) in the words a mentor would understand. */
export const FEATURE_WORDS: Record<string, string> = {
  signup: "Signed up",
  login: "Logged in",
  booking_created: "Appointments booked",
  booking_status: "Appointments marked (arrived, done…)",
  order_created: "Orders placed",
  order_status: "Orders moved (confirmed, dispatched…)",
  callback_created: "Callbacks asked for",
  call_ended: "Calls answered by the AI",
  wa_command: "WhatsApp commands",
  settings_saved: "Settings saved",
  instructions_saved: "Own instructions saved",
  catalog_updated: "Catalogue updated",
  feedback_sent: "Feedback sent",
  web_call_started: "Test calls from the website",
};

export const SOURCE_WORDS: Record<string, string> = { phone: "By the AI on the phone", whatsapp: "From WhatsApp", walk_in: "At the desk (walk-in)" };

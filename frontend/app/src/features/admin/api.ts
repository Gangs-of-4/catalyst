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

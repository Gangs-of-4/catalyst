/**
 * The public test page's data (contracts.md §6 `/api/try/{public_id}`; shapes agreed in issue #24).
 * Public: no login. Names are masked by the backend and phone numbers never reach the page.
 */
import { api } from "@/lib/api";

export type TryInfo = {
  public_id: string;
  name: string;
  city?: string;
  template: string;
  modules: string[];
  labels: Partial<Record<"resource" | "resource_plural" | "booking" | "tenant" | "contact", string>>;
  /** null until the business's voice agent is switched on. */
  voice: { public_key: string; assistant_id: string } | null;
  try_saying: string[];
};

export type SlotState = "free" | "booked" | "blocked" | "past";
export type Source = "phone" | "whatsapp" | "walk_in";

export type BookingsBoard = {
  kind: "bookings";
  days: {
    date: string;
    label: string;
    short: string;
    closed: boolean;
    columns: {
      resource: string;
      slots: { time: string; state: SlotState; booking: { id: number; name: string; source: Source } | null }[];
    }[];
  }[];
};

export type OrdersBoard = {
  kind: "orders";
  orders: {
    id: number;
    number: string;
    shop: string;
    items: number;
    total: string;
    status: string;
    source: Source;
    created_at: string;
  }[];
};

export type Board = BookingsBoard | OrdersBoard;

const base = (publicId: string) => `/api/try/${encodeURIComponent(publicId)}`;

export const getTryInfo = (publicId: string, signal?: AbortSignal) => api<TryInfo>(base(publicId), { signal });

export const getBoard = (publicId: string, signal?: AbortSignal) => api<Board>(`${base(publicId)}/board`, { signal });

/** The call-cap check before a web call: 429 MINUTES_USED_UP or 503 VOICE_NOT_CONFIGURED otherwise. */
export const startCheck = (publicId: string) =>
  api<{ max_call_seconds: number }>(`${base(publicId)}/start`, { method: "POST" });

/** Ids of bookings or orders on the board, to spot new ones as they arrive. */
export function boardIds(board: Board): Set<number> {
  const ids = new Set<number>();
  if (board.kind === "orders") board.orders.forEach((o) => ids.add(o.id));
  else
    board.days.forEach((d) =>
      d.columns.forEach((c) => c.slots.forEach((s) => s.booking && ids.add(s.booking.id))),
    );
  return ids;
}

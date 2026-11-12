/** The add-order form's draft: kept by the board, so closing the sheet or an error never loses it. */
import type { Product } from "./api";

export type Line = { key: number; product: Product | null; query: string; qty: string };

export type Draft = {
  shop_name: string;
  contact_name: string;
  phone: string;
  notes: string;
  source: "walk_in" | "whatsapp";
  lines: Line[];
  /** One key per order being written: a resend after a lost connection returns the same order. */
  idempotencyKey: string;
};

let lineKey = 0;
export const newLine = (): Line => ({ key: ++lineKey, product: null, query: "", qty: "1" });
const newKey = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `k-${Date.now()}-${Math.random().toString(36).slice(2)}`;

export const emptyDraft = (): Draft => ({
  shop_name: "",
  contact_name: "",
  phone: "",
  notes: "",
  source: "walk_in",
  lines: [newLine()],
  idempotencyKey: newKey(),
});

export const qtyOf = (l: Line) => (/^\d+$/.test(l.qty.trim()) ? Number(l.qty.trim()) : NaN);

/** Running total of the rows that are complete. */
export const draftTotal = (d: Draft) =>
  d.lines.reduce((sum, l) => (l.product && qtyOf(l) > 0 ? sum + l.product.rate_paise * qtyOf(l) : sum), 0);

export const draftIsEmpty = (d: Draft) =>
  !d.shop_name.trim() && !d.phone.trim() && !d.contact_name.trim() && d.lines.every((l) => !l.product && !l.query.trim());


/** Order board and catalogue endpoints (contracts.md §6.1, orders template). */
import { api } from "@/lib/api";

export type OrderStatus = "new" | "confirmed" | "dispatched" | "delivered" | "cancelled";
export type OrderSource = "phone" | "whatsapp" | "walk_in";

export type OrderItem = {
  product_id: number;
  name: string;
  pack_size: string;
  qty: number;
  rate_paise: number;
  rate: string;
  amount: string;
};

export type Order = {
  id: number;
  number: number;
  shop_name: string;
  contact_name: string | null;
  phone: string | null;
  notes: string | null;
  status: OrderStatus;
  /** The statuses it may move to (the backend's lifecycle table). */
  next: OrderStatus[];
  source: OrderSource;
  items: OrderItem[];
  total_paise: number;
  total: string;
  created_at: string;
  updated_at: string;
};

export type Product = {
  id: number;
  name: string;
  pack_size: string;
  rate_paise: number;
  rate: string;
  in_stock: boolean;
  active: boolean;
};

export type OrderPage = { orders: Order[]; next_before_id: number | null };

export type NewOrder = {
  shop_name: string;
  contact_name: string;
  phone: string;
  notes: string;
  items: { product_id: number; qty: number }[];
  source: "walk_in" | "whatsapp";
  idempotency_key: string;
  allow_duplicate: boolean;
};

export const PAGE = 50;

export const getOrders = (beforeId: number | null, signal?: AbortSignal) =>
  api<OrderPage>(`/api/orders?limit=${PAGE}${beforeId ? `&before_id=${beforeId}` : ""}`, { signal });

export const createOrder = (body: NewOrder) => api<Order>("/api/orders", { method: "POST", body });

export const setOrderStatus = (id: number, status: OrderStatus) =>
  api<Order>(`/api/orders/${id}/status`, { method: "POST", body: { status } });

export const getCatalog = (signal?: AbortSignal) => api<{ products: Product[] }>("/api/catalog", { signal });

/** Paise as the backend writes rupees: Indian grouping, paise only when there are any (₹1,23,456 or ₹99.50). */
export function formatInr(paise: number): string {
  const whole = paise % 100 === 0;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: whole ? 0 : 2,
  }).format(paise / 100);
}

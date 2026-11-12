import type { OrderStatus } from "./api";

export const ORDER_STATUS: Record<OrderStatus, { label: string; variant: "neutral" | "live" | "success" | "destructive" }> = {
  new: { label: "New", variant: "live" },
  confirmed: { label: "Confirmed", variant: "neutral" },
  dispatched: { label: "Dispatched", variant: "neutral" },
  delivered: { label: "Delivered", variant: "success" },
  cancelled: { label: "Cancelled", variant: "destructive" },
};

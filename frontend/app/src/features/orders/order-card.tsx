import { MoreHorizontal } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { formatPhone } from "@/features/desk/api";
import { SourceTag } from "@/features/desk/register";
import { cn } from "@/lib/utils";

import type { Order, OrderStatus } from "./api";
import { ORDER_STATUS } from "./labels";

/** The one big button on a card: the next step forward. Cancel lives in the menu. */
const STEP_LABEL: Partial<Record<OrderStatus, string>> = {
  confirmed: "Confirm",
  dispatched: "Mark dispatched",
  delivered: "Mark delivered",
};

const when = (iso: string) =>
  new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

type Props = {
  order: Order;
  saving: boolean;
  onStep: (order: Order, to: OrderStatus) => void;
  onCancel: (order: Order) => void;
};

export function OrderCard({ order: o, saving, onStep, onCancel }: Props) {
  const step = o.next.find((s) => s !== "cancelled");
  const canCancel = o.next.includes("cancelled");
  const count = o.items.reduce((n, it) => n + it.qty, 0);
  const closed = o.status === "delivered" || o.status === "cancelled";

  return (
    <li className={cn("flex flex-col gap-3 rounded-lg border bg-card p-4", o.status === "new" && "border-live/50")}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-0.5">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-sm font-medium tabular-nums text-muted-foreground">#{o.number}</span>
            <span className="truncate font-semibold">{o.shop_name}</span>
          </div>
          <div className="flex flex-wrap items-center gap-x-2 text-[13px] text-muted-foreground">
            <SourceTag source={o.source} />
            <span aria-hidden>·</span>
            <span>{when(o.created_at)}</span>
          </div>
        </div>
        <Badge variant={ORDER_STATUS[o.status].variant}>{ORDER_STATUS[o.status].label}</Badge>
      </div>

      <details className="group">
        <summary className="flex cursor-pointer list-none items-baseline justify-between gap-3 rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring">
          <span className="text-sm text-body">
            {o.items.length} {o.items.length === 1 ? "item" : "items"} · {count} qty
            <span className="ml-1.5 text-[13px] font-medium text-muted-foreground underline-offset-4 group-open:hidden">Show</span>
          </span>
          <span className="font-semibold tabular-nums">{o.total}</span>
        </summary>
        <ul className="mt-2 flex flex-col gap-1 border-t pt-2 text-sm">
          {o.items.map((it) => (
            <li key={it.product_id} className="flex justify-between gap-3">
              <span className="min-w-0">
                {it.name}
                {it.pack_size && <span className="text-muted-foreground"> · {it.pack_size}</span>}
                <span className="text-muted-foreground"> × {it.qty}</span>
              </span>
              <span className="shrink-0 tabular-nums">{it.amount}</span>
            </li>
          ))}
        </ul>
      </details>

      {(o.contact_name || o.phone || o.notes) && (
        <div className="flex flex-col text-[13px] text-muted-foreground">
          {(o.contact_name || o.phone) && (
            <span>
              {o.contact_name}
              {o.contact_name && o.phone && " · "}
              {o.phone && (
                <a href={`tel:${o.phone}`} className="tabular-nums underline-offset-4 hover:underline">
                  {formatPhone(o.phone)}
                </a>
              )}
            </span>
          )}
          {o.notes && <span>{o.notes}</span>}
        </div>
      )}

      {!closed && (step || canCancel) && (
        <div className="flex items-center gap-2">
          {step && (
            <Button className="flex-1 sm:flex-none" disabled={saving} onClick={() => onStep(o, step)}>
              {STEP_LABEL[step] ?? ORDER_STATUS[step].label}
            </Button>
          )}
          {canCancel && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="icon" aria-label={`More for order ${o.number}`} disabled={saving}>
                  <MoreHorizontal />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem variant="destructive" onSelect={() => onCancel(o)}>
                  Cancel order
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      )}
    </li>
  );
}

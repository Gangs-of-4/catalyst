import { CalendarX2, MessageCircle, PackageOpen, Phone, Store } from "lucide-react";
import * as React from "react";

import { EmptyState } from "@/components/empty-state";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

import type { Board, BookingsBoard, OrdersBoard, Source } from "./api";

const SOURCE: Record<Source, { label: string; icon: typeof Phone }> = {
  phone: { label: "Phone", icon: Phone },
  whatsapp: { label: "WhatsApp", icon: MessageCircle },
  walk_in: { label: "Walk-in", icon: Store },
};

function SourceTag({ source }: { source: Source }) {
  const s = SOURCE[source] ?? SOURCE.phone;
  return (
    <span className="inline-flex items-center gap-1 text-[13px] text-muted-foreground">
      <s.icon aria-hidden className="size-3.5" /> {s.label}
    </span>
  );
}

/** Today's and tomorrow's slots per resource. New bookings are marked as they arrive. */
function BookingsView({ board, fresh, resourceLabel }: { board: BookingsBoard; fresh: Set<number>; resourceLabel: string }) {
  const [dayIndex, setDayIndex] = React.useState(0);
  const day = board.days[Math.min(dayIndex, board.days.length - 1)];
  if (!day) return null;

  return (
    <div className="flex flex-col gap-4">
      {board.days.length > 1 && (
        <div role="group" aria-label="Day" className="inline-flex w-fit gap-1 rounded-full bg-muted p-1">
          {board.days.map((d, i) => (
            <button
              key={d.date}
              type="button"
              aria-pressed={i === dayIndex}
              onClick={() => setDayIndex(i)}
              className={cn(
                "rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                i === dayIndex ? "bg-background text-foreground shadow-xs" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {d.label}
              <span className="hidden font-normal text-muted-foreground sm:inline"> · {d.short}</span>
            </button>
          ))}
        </div>
      )}

      {day.closed ? (
        <EmptyState icon={CalendarX2} title={`Closed on ${day.short}`} description="Callers hear that you're closed and when you open next." />
      ) : day.columns.length === 0 ? (
        <EmptyState icon={CalendarX2} title={`No ${resourceLabel.toLowerCase()}s yet`} />
      ) : (
        <div className="flex flex-col gap-5">
          {day.columns.map((col) => (
            <section key={col.resource} aria-label={col.resource} className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold">{col.resource}</h3>
              <ul className="grid grid-cols-[repeat(auto-fill,minmax(6.5rem,1fr))] gap-2">
                {col.slots.map((s) => {
                  const isNew = s.booking && fresh.has(s.booking.id);
                  return (
                    <li
                      key={s.time}
                      className={cn(
                        "flex min-h-14 flex-col justify-center rounded-md border px-2.5 py-1.5 text-sm transition-colors",
                        s.state === "booked" && !isNew && "border-primary/20 bg-muted",
                        isNew && "border-live bg-live-soft",
                        s.state === "free" && "border-border bg-background",
                        (s.state === "past" || s.state === "blocked") && "border-transparent bg-surface-soft text-muted-foreground",
                      )}
                    >
                      <span className="font-medium tabular-nums">{s.time}</span>
                      {s.booking ? (
                        <span className="truncate text-[13px]" title={s.booking.name}>
                          {isNew && <span className="font-semibold text-live-text">New · </span>}
                          {s.booking.name}
                        </span>
                      ) : (
                        <span className="text-[13px] text-muted-foreground">
                          {s.state === "free" ? "Free" : s.state === "blocked" ? "Not available" : "Past"}
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

const STATUS_BADGE: Record<string, "neutral" | "live" | "success" | "destructive"> = {
  new: "live",
  confirmed: "neutral",
  dispatched: "neutral",
  delivered: "success",
  cancelled: "destructive",
};

/** Today's orders, newest first. */
function OrdersView({ board, fresh }: { board: OrdersBoard; fresh: Set<number> }) {
  if (!board.orders.length)
    return (
      <EmptyState
        icon={PackageOpen}
        title="No orders yet today"
        description="Place one by phone. It appears here the moment the agent saves it."
      />
    );
  return (
    <ul className="flex flex-col gap-2">
      {board.orders.map((o) => (
        <li
          key={o.id}
          className={cn(
            "flex flex-wrap items-center justify-between gap-x-4 gap-y-1 rounded-md border px-3.5 py-3",
            fresh.has(o.id) ? "border-live bg-live-soft" : "border-border",
          )}
        >
          <div className="flex min-w-0 flex-col">
            <span className="font-semibold">
              {/^\d+$/.test(o.number) ? `#${o.number}` : o.number} · {o.shop}
            </span>
            <span className="text-[13px] text-muted-foreground">
              {o.items} {o.items === 1 ? "item" : "items"} · {o.total}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <SourceTag source={o.source} />
            <Badge variant={STATUS_BADGE[o.status] ?? "neutral"} className="capitalize">
              {o.status}
            </Badge>
          </div>
        </li>
      ))}
    </ul>
  );
}

export function LiveBoard({ board, fresh, resourceLabel }: { board: Board; fresh: Set<number>; resourceLabel: string }) {
  return board.kind === "orders" ? (
    <OrdersView board={board} fresh={fresh} />
  ) : (
    <BookingsView board={board} fresh={fresh} resourceLabel={resourceLabel} />
  );
}

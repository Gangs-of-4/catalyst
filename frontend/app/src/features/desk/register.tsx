import { ChevronDown, MessageCircle, Phone, Plus, Store } from "lucide-react";
import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { type Booking, type Day, type Doctor, formatPhone, type Slot, type Source, type Status, time12 } from "./api";

const SOURCE: Record<Source, { label: string; icon: typeof Phone }> = {
  phone: { label: "Phone", icon: Phone },
  whatsapp: { label: "WhatsApp", icon: MessageCircle },
  walk_in: { label: "Walk-in", icon: Store },
};

const STATUS: Record<Status, { label: string; variant: "neutral" | "live" | "success" | "destructive" }> = {
  booked: { label: "Booked", variant: "neutral" },
  arrived: { label: "Arrived", variant: "live" },
  done: { label: "Done", variant: "success" },
  no_show: { label: "No-show", variant: "destructive" },
  cancelled: { label: "Cancelled", variant: "neutral" },
};

/** What the receptionist can do next from each status. Cancel is separate: it asks first. */
const NEXT: Record<Status, { to: Status; label: string }[]> = {
  booked: [
    { to: "arrived", label: "Arrived" },
    { to: "no_show", label: "No-show" },
  ],
  arrived: [{ to: "done", label: "Done" }],
  no_show: [{ to: "arrived", label: "Arrived late" }],
  done: [],
  cancelled: [],
};

export type RegisterActions = {
  onAdd: (doctor: Doctor, time: string) => void;
  onStatus: (booking: Booking, to: Status) => void;
  onCancel: (booking: Booking) => void;
  /** The booking whose change is being saved, so its buttons don't take a second tap. */
  savingId: number | null;
};

export function SourceTag({ source }: { source: Source }) {
  const s = SOURCE[source] ?? SOURCE.phone;
  return (
    <span className="inline-flex items-center gap-1 text-[13px] text-muted-foreground">
      <s.icon aria-hidden className="size-3.5" /> {s.label}
    </span>
  );
}

export function BookingEntry({ booking: b, actions }: { booking: Booking; actions: RegisterActions }) {
  const saving = actions.savingId === b.id;
  const next = NEXT[b.status] ?? [];
  const canCancel = b.status === "booked" || b.status === "arrived";
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="font-semibold">{b.name}</span>
        {b.status !== "booked" && <Badge variant={STATUS[b.status].variant}>{STATUS[b.status].label}</Badge>}
        <SourceTag source={b.source} />
      </div>
      {(b.phone || b.reason) && (
        <div className="flex flex-col text-[13px] text-muted-foreground">
          {b.phone && (
            <a href={`tel:${b.phone}`} className="w-fit tabular-nums underline-offset-4 hover:underline">
              {formatPhone(b.phone)}
            </a>
          )}
          {b.reason && <span>{b.reason}</span>}
        </div>
      )}
      {(next.length > 0 || canCancel) && (
        <div className="flex flex-wrap gap-2">
          {next.map((n, i) => (
            <Button
              key={n.to}
              size="sm"
              variant={i === 0 ? "default" : "outline"}
              disabled={saving}
              onClick={() => actions.onStatus(b, n.to)}
            >
              {n.label}
            </Button>
          ))}
          {canCancel && (
            <Button size="sm" variant="ghost" className="text-destructive" disabled={saving} onClick={() => actions.onCancel(b)}>
              Cancel
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

function blockedLabel(block: string | null) {
  if (block === "closed") return "Closed";
  if (block === "leave") return "On leave";
  return "Not available";
}

function SlotRow({ slot, doctor, actions }: { slot: Slot; doctor: Doctor; actions: RegisterActions }) {
  const time = (
    <span className={cn("w-[4.5rem] shrink-0 pt-0.5 text-sm font-medium tabular-nums", slot.state !== "booked" && slot.bookings.length === 0 && "text-muted-foreground")}>
      {time12(slot.time)}
    </span>
  );

  if (slot.bookings.length > 0) {
    return (
      <li className={cn("flex gap-3 border-b px-3 py-3 last:border-b-0", slot.bookings.some((b) => b.status === "arrived") && "bg-live-soft/60")}>
        {time}
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          {slot.bookings.map((b) => (
            <BookingEntry key={b.id} booking={b} actions={actions} />
          ))}
          {slot.state === "free" && (
            <AddButton onClick={() => actions.onAdd(doctor, slot.time)} label={`Add at ${time12(slot.time)}`} />
          )}
        </div>
      </li>
    );
  }

  if (slot.state === "free") {
    return (
      <li className="border-b last:border-b-0">
        <button
          type="button"
          onClick={() => actions.onAdd(doctor, slot.time)}
          aria-label={`Add a booking at ${time12(slot.time)} with ${doctor.name}`}
          className="flex min-h-12 w-full items-center gap-3 px-3 py-2 text-left hover:bg-accent focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
        >
          {time}
          <span className="flex-1 text-sm text-muted-foreground">Free</span>
          <span className="inline-flex items-center gap-1 text-sm font-semibold">
            <Plus aria-hidden className="size-4" /> Add
          </span>
        </button>
      </li>
    );
  }

  return (
    <li className="flex min-h-12 items-center gap-3 border-b bg-surface-soft px-3 py-2 last:border-b-0">
      {time}
      <span className="text-sm text-muted-foreground">{slot.state === "past" ? "Past" : blockedLabel(slot.block)}</span>
    </li>
  );
}

function AddButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <Button size="sm" variant="outline" className="w-fit" onClick={onClick} aria-label={label}>
      <Plus aria-hidden /> Add
    </Button>
  );
}

/** One doctor's day as rows. Earlier empty slots fold away so the next patient is near the top. */
export function DoctorDay({
  doctor,
  slots: allSlots,
  actions,
  onlyBooked = false,
}: {
  doctor: Doctor;
  slots: Slot[];
  actions: RegisterActions;
  /** A closed day: show only the bookings made before it closed, not a column of "Closed" rows. */
  onlyBooked?: boolean;
}) {
  const [showEarlier, setShowEarlier] = React.useState(false);
  const slots = onlyBooked ? allSlots.filter((s) => s.bookings.length > 0) : allSlots;
  const hiddenCount = slots.filter((s) => s.past && s.bookings.length === 0).length;
  const visible = showEarlier ? slots : slots.filter((s) => !(s.past && s.bookings.length === 0));

  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      {hiddenCount > 0 && (
        <button
          type="button"
          onClick={() => setShowEarlier((v) => !v)}
          aria-expanded={showEarlier}
          className="flex w-full items-center justify-center gap-1 border-b bg-surface-soft px-3 py-2 text-[13px] font-medium text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
        >
          <ChevronDown aria-hidden className={cn("size-4 transition-transform", showEarlier && "rotate-180")} />
          {showEarlier ? "Hide earlier times" : `Show ${hiddenCount} earlier ${hiddenCount === 1 ? "time" : "times"}`}
        </button>
      )}
      {visible.length === 0 ? (
        <p className="px-3 py-6 text-center text-sm text-muted-foreground">{onlyBooked ? "No bookings." : "No more times today."}</p>
      ) : (
        <ul aria-label={`${doctor.name}'s times`}>
          {visible.map((s) => (
            <SlotRow key={s.time} slot={s} doctor={doctor} actions={actions} />
          ))}
        </ul>
      )}
    </div>
  );
}

const activeCount = (slots: Slot[]) =>
  slots.reduce((n, s) => n + s.bookings.filter((b) => b.status !== "cancelled" && b.status !== "no_show").length, 0);

/**
 * The day's register. Phones: one doctor at a time, switched with tabs. Wide screens: every doctor
 * side by side, like the paper register.
 */
export function Register({
  day,
  activeDoctor,
  onDoctor,
  actions,
  resourceLabel,
  onlyBooked = false,
}: {
  onlyBooked?: boolean;
  day: Day;
  activeDoctor: string | null;
  onDoctor: (id: string) => void;
  actions: RegisterActions;
  resourceLabel: string;
}) {
  const current = day.columns.find((c) => c.doctor.id === activeDoctor) ?? day.columns[0];
  const tabRefs = React.useRef<(HTMLButtonElement | null)[]>([]);

  function onTabKey(e: React.KeyboardEvent, index: number) {
    const last = day.columns.length - 1;
    const to = e.key === "ArrowRight" ? (index === last ? 0 : index + 1) : e.key === "ArrowLeft" ? (index === 0 ? last : index - 1) : null;
    if (to === null) return;
    e.preventDefault();
    const col = day.columns[to];
    if (col) {
      onDoctor(col.doctor.id);
      tabRefs.current[to]?.focus();
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {day.columns.length > 1 && (
        <div role="tablist" aria-label={resourceLabel} className="flex gap-1 overflow-x-auto rounded-lg bg-muted p-1 lg:hidden">
          {day.columns.map((c, i) => {
            const selected = c.doctor.id === current?.doctor.id;
            return (
              <button
                key={c.doctor.id}
                ref={(el) => {
                  tabRefs.current[i] = el;
                }}
                type="button"
                role="tab"
                id={`tab-${c.doctor.id}`}
                aria-selected={selected}
                aria-controls={`panel-${c.doctor.id}`}
                tabIndex={selected ? 0 : -1}
                onClick={() => onDoctor(c.doctor.id)}
                onKeyDown={(e) => onTabKey(e, i)}
                className={cn(
                  "flex min-h-10 flex-1 items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-3 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                  selected ? "bg-background text-foreground shadow-xs" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {c.doctor.name}
                <span className="rounded-full bg-muted px-1.5 text-[12px] tabular-nums text-muted-foreground">{activeCount(c.slots)}</span>
              </button>
            );
          })}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[repeat(auto-fit,minmax(17rem,1fr))]">
        {day.columns.map((c) => {
          const selected = c.doctor.id === current?.doctor.id;
          return (
            <section
              key={c.doctor.id}
              id={`panel-${c.doctor.id}`}
              role={day.columns.length > 1 ? "tabpanel" : undefined}
              aria-labelledby={day.columns.length > 1 ? `tab-${c.doctor.id}` : undefined}
              aria-label={day.columns.length > 1 ? undefined : c.doctor.name}
              className={cn("flex-col gap-2", selected ? "flex" : "hidden lg:flex")}
            >
              <h3 className={cn("text-sm font-semibold", day.columns.length > 1 && "hidden lg:block")}>{c.doctor.name}</h3>
              <DoctorDay doctor={c.doctor} slots={c.slots} actions={actions} onlyBooked={onlyBooked} />
            </section>
          );
        })}
      </div>
    </div>
  );
}

import { AlertCircle, CalendarX2, ChevronLeft, ChevronRight, House, RotateCw } from "lucide-react";
import * as React from "react";
import { Link, useNavigate } from "react-router";
import { toast } from "sonner";

import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  type Booking,
  type Day,
  type Doctor,
  getDay,
  setStatus,
  shiftDate,
  type Status,
  time12,
} from "@/features/desk/api";
import { DeskSide, UrgentBanner } from "@/features/desk/panels";
import { BookingEntry, Register, type RegisterActions } from "@/features/desk/register";
import { useDeskSide } from "@/features/desk/use-desk-side";
import { WalkInDialog, type WalkInTarget } from "@/features/desk/walk-in-dialog";
import { OrderBoard } from "@/features/orders/order-board";
import { usePolling } from "@/hooks/use-polling";
import { ApiError } from "@/lib/api";
import { getMe, type Me } from "@/lib/session";

const POLL_MS = 5000;
const isAbort = (e: unknown) => e instanceof DOMException && e.name === "AbortError";

const STATUS_DONE: Partial<Record<Status, string>> = {
  arrived: "marked arrived",
  done: "marked done",
  no_show: "marked no-show",
  cancelled: "cancelled; the time is free again",
};

/**
 * The receptionist's desk for a business that keeps a schedule (M8, C7): the day's register per
 * doctor, walk-ins, statuses, the inbox and the call log. Mobile first: one doctor per tab on phones.
 * Refreshes every few seconds, and pauses while a form is open so nothing moves under a tap.
 */
export function DeskPage() {
  const navigate = useNavigate();
  const [me, setMe] = React.useState<Me | null>(null);
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [noSchedule, setNoSchedule] = React.useState(false);
  const [attempt, setAttempt] = React.useState(0);

  const [date, setDate] = React.useState<string | null>(null); // null = today, until the backend says which day that is
  const [firstToday, setToday] = React.useState<string | null>(null); // from the first register load
  const [day, setDay] = React.useState<Day | null>(null);
  const [doctorId, setDoctorId] = React.useState<string | null>(null);

  const [walkIn, setWalkIn] = React.useState<WalkInTarget | null>(null);
  const [cancelling, setCancelling] = React.useState<Booking | null>(null);
  const [savingId, setSavingId] = React.useState<number | null>(null);

  // Latest values for the async loaders (a response for a day the receptionist has left is dropped).
  const dateRef = React.useRef(date);
  const dayRef = React.useRef(day);
  React.useEffect(() => {
    dateRef.current = date;
    dayRef.current = day;
  });

  const onAuthError = React.useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && err.status === 401) {
        navigate("/login?next=/desk", { replace: true });
        return true;
      }
      return false;
    },
    [navigate],
  );

  // Who is logged in (and their labels), once.
  React.useEffect(() => {
    const ctrl = new AbortController();
    getMe(ctrl.signal)
      .then(setMe)
      .catch((err: unknown) => {
        if (isAbort(err) || onAuthError(err)) return;
        setLoadError(err instanceof ApiError ? err.detail : "We couldn't load your desk.");
      });
    return () => ctrl.abort();
  }, [attempt, onAuthError]);

  const loadDay = React.useCallback(
    async (signal?: AbortSignal) => {
      const wanted = dateRef.current;
      try {
        const d = await getDay(wanted, signal);
        if (wanted !== dateRef.current) return; // the receptionist moved on to another day meanwhile
        setDay(d);
        if (wanted === null) setToday(d.date);
        setLoadError(null);
      } catch (err) {
        if (isAbort(err) || onAuthError(err)) return;
        if (err instanceof ApiError && err.code === "NOT_FOUND" && err.status === 404) {
          setNoSchedule(true);
          return;
        }
        // Keep showing the last good register; the connection banner covers an unreachable backend.
        if (!dayRef.current) setLoadError(err instanceof ApiError ? err.detail : "We couldn't load the register.");
      }
    },
    [onAuthError],
  );

  const side = useDeskSide(onAuthError);
  const { loadSide } = side;
  // Today as the backend sees it, refreshed with the stats every poll: a desk left open past midnight moves on.
  const today = side.stats?.date ?? firstToday;

  const refresh = React.useCallback(
    async (signal?: AbortSignal) => {
      await Promise.all([loadDay(signal), loadSide(signal)]);
    },
    [loadDay, loadSide],
  );

  const formOpen = walkIn !== null || cancelling !== null;
  usePolling(refresh, POLL_MS, me !== null && !noSchedule && !formOpen);

  // Changing the day loads it straight away rather than on the next tick.
  const firstDate = React.useRef(true);
  React.useEffect(() => {
    if (firstDate.current) {
      firstDate.current = false; // the first load comes from polling
      return;
    }
    const ctrl = new AbortController();
    void loadDay(ctrl.signal);
    return () => ctrl.abort();
  }, [date, loadDay]);

  // After the connection banner reconnects, catch up at once.
  React.useEffect(() => {
    const onBack = () => void refresh();
    window.addEventListener("catalyst:reconnected", onBack);
    return () => window.removeEventListener("catalyst:reconnected", onBack);
  }, [refresh]);

  function goTo(next: string) {
    // The old day stays on screen, dimmed, under its own heading until the new one arrives.
    setDate(next === today ? null : next);
  }

  /** Returns whether it saved, so the cancel dialog only closes on success. */
  async function changeStatus(b: Booking, to: Status): Promise<boolean> {
    setSavingId(b.id);
    try {
      await setStatus(b.id, to);
      toast.success(`${b.name} ${STATUS_DONE[to] ?? "updated"}.`);
      void refresh();
      return true;
    } catch (err) {
      if (!onAuthError(err)) toast.error(err instanceof ApiError ? err.detail : "Couldn't save that. Please try again.");
      return false;
    } finally {
      setSavingId(null);
    }
  }

  async function confirmCancel() {
    if (!cancelling) return;
    if (await changeStatus(cancelling, "cancelled")) setCancelling(null);
  }

  const doctors: Doctor[] = day?.columns.map((c) => c.doctor) ?? [];
  const actions: RegisterActions = {
    onAdd: (doctor, time) => day && setWalkIn({ doctor, time, date: day.date, dayLabel: `${day.label}, ${day.short}` }),
    onStatus: (b, to) => void changeStatus(b, to),
    onCancel: setCancelling,
    savingId,
  };

  const resourceLabel = me?.business.labels.resource_plural ?? "Doctors";
  const header = (
    <AppHeader>
      <Button asChild variant="ghost" size="sm">
        <Link to="/home">
          <House aria-hidden /> Home
        </Link>
      </Button>
    </AppHeader>
  );

  // A business without the bookings module gets 404 from the register: it takes orders instead.
  if (noSchedule && me) return <OrderBoard me={me} header={header} onAuthError={onAuthError} />;

  if (loadError && !day) {
    return (
      <>
        {header}
        <main className="mx-auto max-w-2xl px-4 py-12 sm:px-6">
          <EmptyState
            icon={AlertCircle}
            title="The desk didn't load"
            description={loadError}
            action={
              <Button
                variant="outline"
                onClick={() => {
                  setLoadError(null);
                  setAttempt((n) => n + 1);
                  void refresh();
                }}
              >
                <RotateCw /> Try again
              </Button>
            }
          />
        </main>
      </>
    );
  }

  if (!me || !day) {
    return (
      <>
        {header}
        <main className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 sm:px-6" role="status" aria-label="Loading the desk">
          <div className="h-8 w-1/2 animate-pulse rounded-md bg-muted" />
          <div className="h-10 animate-pulse rounded-lg bg-muted" />
          <div className="h-72 animate-pulse rounded-lg bg-muted" />
        </main>
      </>
    );
  }

  const closedWithBookings = day.columns.some((c) => c.slots.some((sl) => sl.bookings.length > 0));
  const switching = day.date !== (date ?? today);
  const target = date ?? today ?? day.date;

  return (
    <>
      {header}
      <main className="mx-auto grid max-w-6xl gap-8 px-4 py-6 sm:px-6 sm:py-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="flex min-w-0 flex-col gap-4">
          <div className="flex flex-col gap-1">
            <p className="text-sm text-muted-foreground">Front desk</p>
            <h1 className="text-2xl font-semibold leading-tight tracking-tight">{me.business.name}</h1>
            {side.stats && <p className="text-sm text-body">{side.stats.sentence}</p>}
          </div>

          <UrgentBanner count={side.urgent} />

          {/* Day navigation */}
          <div className="flex items-center gap-2">
            <Button size="icon" variant="outline" aria-label="Previous day" onClick={() => goTo(shiftDate(target, -1))}>
              <ChevronLeft />
            </Button>
            <div className="min-w-0 flex-1 text-center sm:flex-none sm:px-2 sm:text-left">
              <p className="truncate font-semibold" aria-live="polite">
                {day.label}
                <span className="font-normal text-muted-foreground">, {day.short}</span>
              </p>
            </div>
            <Button size="icon" variant="outline" aria-label="Next day" onClick={() => goTo(shiftDate(target, 1))}>
              <ChevronRight />
            </Button>
            {target !== today && today && (
              <Button size="sm" variant="ghost" onClick={() => goTo(today)}>
                Today
              </Button>
            )}
            <label className="ml-auto hidden sm:block">
              <span className="sr-only">Pick a day</span>
              <input
                type="date"
                value={target}
                onChange={(e) => e.target.value && goTo(e.target.value)}
                className="h-9 rounded-md border border-input bg-background px-2 text-sm"
              />
            </label>
          </div>

          <div aria-busy={switching} className={switching ? "pointer-events-none flex flex-col gap-4 opacity-50" : "flex flex-col gap-4"}>
          {day.closed && closedWithBookings && (
            <p role="note" className="rounded-lg border border-live/40 bg-live-soft px-3 py-2.5 text-sm text-live-text">
              <span className="font-semibold">Closed on {day.short}.</span> These bookings were made before the day was
              closed. Call them to move or cancel.
            </p>
          )}
          {day.closed && !closedWithBookings ? (
            <EmptyState icon={CalendarX2} title={`Closed on ${day.short}`} description="Callers hear that you're closed and when you open next." />
          ) : day.columns.length === 0 ? (
            <EmptyState icon={CalendarX2} title={`No ${resourceLabel.toLowerCase()} yet`} description="Add them in settings to start taking bookings." />
          ) : (
            <Register
              day={day}
              activeDoctor={doctorId}
              onDoctor={setDoctorId}
              actions={actions}
              resourceLabel={resourceLabel}
              onlyBooked={day.closed}
            />
          )}

          {day.stray.length > 0 && (
            <section aria-labelledby="stray" className="flex flex-col gap-2">
              <h2 id="stray" className="text-sm font-semibold">
                Other bookings this day
              </h2>
              <ul className="flex flex-col divide-y rounded-lg border">
                {day.stray.map((b) => (
                  <li key={b.id} className="flex gap-3 p-3">
                    <span className="w-[4.5rem] shrink-0 pt-0.5 text-sm font-medium tabular-nums">{time12(b.time)}</span>
                    <BookingEntry booking={b} actions={actions} />
                  </li>
                ))}
              </ul>
            </section>
          )}
          </div>
        </div>

        <DeskSide inbox={side.inbox} calls={side.calls} doneId={side.doneId} onDone={(it) => void side.onInboxDone(it)} />
      </main>

      <WalkInDialog
        key={walkIn ? `${walkIn.doctor.id}-${walkIn.date}-${walkIn.time}` : "closed"}
        target={walkIn}
        doctors={doctors}
        onClose={() => setWalkIn(null)}
        onSaved={(t, name) => {
          setWalkIn(null);
          toast.success(`Booked ${name} with ${t.doctor.name} at ${time12(t.time)}.`);
          void refresh();
        }}
      />

      <Dialog open={cancelling !== null} onOpenChange={(open) => !open && savingId === null && setCancelling(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel this booking?</DialogTitle>
            {cancelling && (
              <DialogDescription>
                {cancelling.name} at {time12(cancelling.time)}. The time becomes free again.
              </DialogDescription>
            )}
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCancelling(null)} disabled={savingId !== null}>
              Keep it
            </Button>
            <Button variant="destructive" onClick={() => void confirmCancel()} disabled={savingId !== null}>
              Cancel booking
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

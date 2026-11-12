import { AlertCircle, Loader2, PackageOpen, Plus, RotateCw } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DeskSide, UrgentBanner } from "@/features/desk/panels";
import { useDeskSide } from "@/features/desk/use-desk-side";
import { useMediaQuery } from "@/hooks/use-media-query";
import { usePolling } from "@/hooks/use-polling";
import { ApiError } from "@/lib/api";
import type { Me } from "@/lib/session";
import { cn } from "@/lib/utils";

import { formatInr, getCatalog, getOrders, type Order, type OrderStatus, type Product, setOrderStatus } from "./api";
import { type Draft, draftIsEmpty, draftTotal, emptyDraft } from "./draft";
import { OrderCard } from "./order-card";
import { OrderForm } from "./order-form";

const POLL_MS = 5000;
const isAbort = (e: unknown) => e instanceof DOMException && e.name === "AbortError";

type Filter = "open" | "new" | "confirmed" | "dispatched" | "closed";
const FILTERS: { id: Filter; label: string; test: (s: OrderStatus) => boolean }[] = [
  { id: "open", label: "Open", test: (s) => s === "new" || s === "confirmed" || s === "dispatched" },
  { id: "new", label: "New", test: (s) => s === "new" },
  { id: "confirmed", label: "Confirmed", test: (s) => s === "confirmed" },
  { id: "dispatched", label: "Dispatched", test: (s) => s === "dispatched" },
  { id: "closed", label: "Done", test: (s) => s === "delivered" || s === "cancelled" },
];

const STEP_DONE: Partial<Record<OrderStatus, string>> = {
  confirmed: "confirmed",
  dispatched: "marked dispatched",
  delivered: "marked delivered",
  cancelled: "cancelled",
};

/** The IST calendar day of a timestamp, to count today's orders. */
const istDay = (iso: string) => new Date(iso).toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });

/**
 * The wholesale desk (phase2-plan §6 order board): orders as cards, newest first, one button to move
 * each to its next status, the add-order form, the inbox and calls. Phones: the form opens from a
 * button pinned to the bottom; wide screens: it sits in the right column.
 */
export function OrderBoard({ me, header, onAuthError }: { me: Me; header: React.ReactNode; onAuthError: (err: unknown) => boolean }) {
  const wide = useMediaQuery("(min-width: 1024px)");
  const [orders, setOrders] = React.useState<Order[] | null>(null);
  const [older, setOlder] = React.useState<Order[]>([]);
  const [nextBefore, setNextBefore] = React.useState<number | null>(null);
  const [loadingOlder, setLoadingOlder] = React.useState(false);
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [filter, setFilter] = React.useState<Filter>("open");

  const [products, setProducts] = React.useState<Product[]>([]);
  const [catalogError, setCatalogError] = React.useState<string | null>(null);
  const [draft, setDraft] = React.useState<Draft>(emptyDraft);
  const [sheetOpen, setSheetOpen] = React.useState(false);

  const [savingId, setSavingId] = React.useState<number | null>(null);
  const [cancelling, setCancelling] = React.useState<Order | null>(null);

  const side = useDeskSide(onAuthError);
  const { loadSide } = side;

  const ordersRef = React.useRef(orders);
  React.useEffect(() => {
    ordersRef.current = orders;
  });

  const loadOrders = React.useCallback(
    async (signal?: AbortSignal) => {
      try {
        const page = await getOrders(null, signal);
        setOrders(page.orders);
        // Only the first time: later polls keep the "show older" position the owner reached.
        if (ordersRef.current === null) setNextBefore(page.next_before_id);
        setLoadError(null);
      } catch (err) {
        if (isAbort(err) || onAuthError(err)) return;
        if (ordersRef.current === null) setLoadError(err instanceof ApiError ? err.detail : "We couldn't load your orders.");
      }
    },
    [onAuthError],
  );

  const loadCatalog = React.useCallback(
    async (signal?: AbortSignal) => {
      try {
        const { products: list } = await getCatalog(signal);
        setProducts(list);
        setCatalogError(null);
      } catch (err) {
        if (isAbort(err) || onAuthError(err)) return;
        setCatalogError("Your catalogue didn't load, so products can't be picked yet.");
      }
    },
    [onAuthError],
  );

  const refresh = React.useCallback(
    async (signal?: AbortSignal) => {
      await Promise.all([loadOrders(signal), loadSide(signal)]);
    },
    [loadOrders, loadSide],
  );

  usePolling(refresh, POLL_MS, cancelling === null);

  // The catalogue (names, rates, stock) changes rarely: load it now and again every minute.
  usePolling(loadCatalog, 60_000);

  React.useEffect(() => {
    const onBack = () => {
      void refresh();
      void loadCatalog();
    };
    window.addEventListener("catalyst:reconnected", onBack);
    return () => window.removeEventListener("catalyst:reconnected", onBack);
  }, [refresh, loadCatalog]);

  async function step(o: Order, to: OrderStatus) {
    setSavingId(o.id);
    try {
      await setOrderStatus(o.id, to);
      toast.success(`Order #${o.number} ${STEP_DONE[to] ?? "updated"}.`);
    } catch (err) {
      if (!onAuthError(err)) toast.error(err instanceof ApiError ? err.detail : "Couldn't save that. Please try again.");
    } finally {
      setSavingId(null);
      void loadOrders();
    }
  }

  async function loadMore() {
    if (!nextBefore) return;
    setLoadingOlder(true);
    try {
      const page = await getOrders(nextBefore);
      setOlder((prev) => [...prev, ...page.orders]);
      setNextBefore(page.next_before_id);
    } catch (err) {
      if (!onAuthError(err)) toast.error(err instanceof ApiError ? err.detail : "Couldn't load older orders.");
    } finally {
      setLoadingOlder(false);
    }
  }

  function onSaved(o: Order) {
    setDraft(emptyDraft());
    setSheetOpen(false);
    toast.success(`Order #${o.number} saved for ${o.shop_name}.`);
    void refresh();
  }

  const form = (
    <OrderForm
      draft={draft}
      onDraft={setDraft}
      products={products}
      catalogError={catalogError}
      onSaved={onSaved}
      onCatalogStale={() => void loadCatalog()}
      onAuthError={onAuthError}
      onDiscard={() => {
        setDraft(emptyDraft());
        setSheetOpen(false);
      }}
    />
  );

  if (loadError && orders === null) {
    return (
      <>
        {header}
        <main className="mx-auto max-w-2xl px-4 py-12 sm:px-6">
          <EmptyState
            icon={AlertCircle}
            title="Your orders didn't load"
            description={loadError}
            action={
              <Button variant="outline" onClick={() => void refresh()}>
                <RotateCw /> Try again
              </Button>
            }
          />
        </main>
      </>
    );
  }

  if (orders === null) {
    return (
      <>
        {header}
        <main className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 sm:px-6" role="status" aria-label="Loading your orders">
          <div className="h-8 w-1/2 animate-pulse rounded-md bg-muted" />
          <div className="h-32 animate-pulse rounded-lg bg-muted" />
          <div className="h-32 animate-pulse rounded-lg bg-muted" />
        </main>
      </>
    );
  }

  // Older pages may repeat an order the first page now holds (new orders pushed it down): first page wins.
  const seen = new Set(orders.map((o) => o.id));
  const all = [...orders, ...older.filter((o) => !seen.has(o.id))];
  const active = FILTERS.find((f) => f.id === filter)!;
  const shown = all.filter((o) => active.test(o.status));
  const today = istDay(new Date().toISOString());
  const todays = all.filter((o) => istDay(o.created_at) === today && o.status !== "cancelled");
  const counts = {
    newCount: all.filter((o) => o.status === "new").length,
    todayCount: todays.length,
    todayValue: todays.reduce((s, o) => s + o.total_paise, 0),
  };
  const draftStarted = !draftIsEmpty(draft);

  return (
    <>
      {header}
      <main className="mx-auto grid max-w-6xl gap-8 px-4 pb-28 pt-6 sm:px-6 sm:pt-8 lg:grid-cols-[minmax(0,1fr)_24rem] lg:pb-8">
        <div className="flex min-w-0 flex-col gap-4">
          <div className="flex flex-col gap-1">
            <p className="text-sm text-muted-foreground">Order board</p>
            <h1 className="text-2xl font-semibold leading-tight tracking-tight">{me.business.name}</h1>
          </div>

          <dl className="grid grid-cols-3 divide-x rounded-lg border">
            <div className="flex flex-col gap-0.5 px-3 py-2.5">
              <dt className="text-[13px] text-muted-foreground">New</dt>
              <dd className={cn("text-lg font-semibold tabular-nums", counts.newCount > 0 && "text-live-text")}>{counts.newCount}</dd>
            </div>
            <div className="flex flex-col gap-0.5 px-3 py-2.5">
              <dt className="text-[13px] text-muted-foreground">Today</dt>
              <dd className="text-lg font-semibold tabular-nums">{counts.todayCount}</dd>
            </div>
            <div className="flex min-w-0 flex-col gap-0.5 px-3 py-2.5">
              <dt className="text-[13px] text-muted-foreground">Today&apos;s value</dt>
              <dd className="truncate text-lg font-semibold tabular-nums">{formatInr(counts.todayValue)}</dd>
            </div>
          </dl>

          <UrgentBanner count={side.urgent} />

          <div role="group" aria-label="Show" className="-mx-4 flex gap-1.5 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:px-0 [&::-webkit-scrollbar]:hidden">
            {FILTERS.map((f) => {
              const n = all.filter((o) => f.test(o.status)).length;
              return (
                <button
                  key={f.id}
                  type="button"
                  aria-pressed={filter === f.id}
                  onClick={() => setFilter(f.id)}
                  className={cn(
                    "flex min-h-9 shrink-0 items-center gap-1.5 rounded-full border px-3.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                    filter === f.id ? "border-primary bg-primary text-primary-foreground" : "bg-background text-muted-foreground hover:text-foreground",
                  )}
                >
                  {f.label}
                  <span className="tabular-nums opacity-75">{n}</span>
                </button>
              );
            })}
          </div>

          {shown.length === 0 ? (
            <EmptyState
              icon={PackageOpen}
              title={filter === "open" ? "No open orders" : `No ${active.label.toLowerCase()} orders`}
              description="Orders placed by phone, on WhatsApp or here appear as they come in."
            />
          ) : (
            <ul aria-label="Orders" className="flex flex-col gap-3">
              {shown.map((o) => (
                <OrderCard key={o.id} order={o} saving={savingId === o.id} onStep={(x, to) => void step(x, to)} onCancel={setCancelling} />
              ))}
            </ul>
          )}

          {nextBefore && (
            <Button variant="outline" className="w-fit self-center" onClick={() => void loadMore()} disabled={loadingOlder}>
              {loadingOlder && <Loader2 aria-hidden className="animate-spin" />} Show older orders
            </Button>
          )}
        </div>

        <DeskSide inbox={side.inbox} calls={side.calls} doneId={side.doneId} onDone={(it) => void side.onInboxDone(it)}>
          {wide && (
            <Card className="gap-4 py-5 sm:py-6">
              <CardHeader className="px-5 sm:px-6">
                <CardTitle className="text-lg">Add order</CardTitle>
              </CardHeader>
              <CardContent className="px-5 sm:px-6">{form}</CardContent>
            </Card>
          )}
        </DeskSide>
      </main>

      {!wide && (
        <>
          <div className="fixed inset-x-0 bottom-0 z-30 border-t bg-background/95 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur-sm">
            <Button size="lg" className="w-full" onClick={() => setSheetOpen(true)}>
              <Plus aria-hidden />
              {draftStarted ? `Continue order · ${formatInr(draftTotal(draft))}` : "New order"}
            </Button>
          </div>
          <Dialog open={sheetOpen} onOpenChange={setSheetOpen}>
            <DialogContent className="sm:max-w-lg">
              <DialogHeader>
                <DialogTitle>New order</DialogTitle>
                <DialogDescription>Closing keeps what you typed.</DialogDescription>
              </DialogHeader>
              {form}
            </DialogContent>
          </Dialog>
        </>
      )}

      <Dialog open={cancelling !== null} onOpenChange={(open) => !open && savingId === null && setCancelling(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel this order?</DialogTitle>
            {cancelling && (
              <DialogDescription>
                Order #{cancelling.number} for {cancelling.shop_name} ({cancelling.total}). It can&apos;t be undone.
              </DialogDescription>
            )}
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCancelling(null)} disabled={savingId !== null}>
              Keep it
            </Button>
            <Button
              variant="destructive"
              disabled={savingId !== null}
              onClick={async () => {
                if (!cancelling) return;
                await step(cancelling, "cancelled");
                setCancelling(null);
              }}
            >
              Cancel order
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

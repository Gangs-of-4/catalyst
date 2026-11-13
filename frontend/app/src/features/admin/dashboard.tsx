import { ChevronRight, Info } from "lucide-react";
import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

import {
  type Business,
  type BusinessDetail,
  type Day,
  FEATURE_WORDS,
  getBusinessDetail,
  getOverview,
  type Overview,
  type Scope,
  SOURCE_WORDS,
  type Totals,
} from "./api";
import { BarList, StatTiles, TrendBars } from "./charts";
import { fmt, minutes } from "./format";

const isAbort = (e: unknown) => e instanceof DOMException && e.name === "AbortError";

type Metric = "active_businesses" | "calls" | "call_minutes" | "app_minutes" | "events";
const METRICS: { id: Metric; label: string; unit?: string }[] = [
  { id: "active_businesses", label: "Active businesses" },
  { id: "calls", label: "Calls" },
  { id: "call_minutes", label: "Call minutes", unit: "min" },
  { id: "app_minutes", label: "Time in the app", unit: "min" },
  { id: "events", label: "Everything used" },
];

const SCOPES: { id: Scope; label: string }[] = [
  { id: "real", label: "Real businesses" },
  { id: "demo", label: "Demo" },
  { id: "all", label: "Both" },
];

function Chips<T extends string>({ value, options, onChange, label }: { value: T; options: { id: T; label: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div role="group" aria-label={label} className="-mx-4 flex gap-1.5 overflow-x-auto px-4 [scrollbar-width:none] sm:mx-0 sm:px-0 [&::-webkit-scrollbar]:hidden">
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          aria-pressed={value === o.id}
          onClick={() => onChange(o.id)}
          className={cn(
            "min-h-9 shrink-0 rounded-full border px-3.5 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
            value === o.id ? "border-primary bg-primary text-primary-foreground" : "bg-background text-muted-foreground hover:text-foreground",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3 rounded-lg border bg-card p-4 sm:p-5">
      <div className="flex flex-col gap-0.5">
        <h2 className="text-base font-semibold">{title}</h2>
        {hint && <p className="text-[13px] text-muted-foreground">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

function tilesFor(t: Totals) {
  const records = t.records.bookings + t.records.orders;
  return [
    { label: "Businesses", value: fmt(t.businesses), note: `${fmt(t.active_businesses_7d)} active this week` },
    { label: "People using it", value: fmt(t.users), note: `${fmt(t.active_users_7d)} active this week` },
    { label: "Calls answered", value: fmt(t.calls), note: `${minutes(t.call_minutes)} on calls` },
    { label: "Time in the app", value: minutes(t.app_minutes), note: "owners and staff, counted since tracking began" },
    { label: "Bookings and orders", value: fmt(records), note: `${fmt(t.records.bookings)} bookings · ${fmt(t.records.orders)} orders` },
    { label: "Made by the AI", value: fmt(t.records_by_source.phone ?? 0), note: "on the phone, no person involved" },
    { label: "WhatsApp commands", value: fmt(t.wa_commands), note: "owners running it from WhatsApp" },
    { label: "Feedback", value: fmt(t.feedback), note: "messages to the team" },
  ];
}

/** Real + demo, for the "Both" scope. */
function addTotals(a: Totals, b: Totals): Totals {
  const src = (k: "phone" | "whatsapp" | "walk_in") => (a.records_by_source[k] ?? 0) + (b.records_by_source[k] ?? 0);
  return {
    businesses: a.businesses + b.businesses,
    active_businesses_7d: a.active_businesses_7d + b.active_businesses_7d,
    users: a.users + b.users,
    active_users_7d: a.active_users_7d + b.active_users_7d,
    calls: a.calls + b.calls,
    call_minutes: a.call_minutes + b.call_minutes,
    records: { bookings: a.records.bookings + b.records.bookings, orders: a.records.orders + b.records.orders },
    records_by_source: { phone: src("phone"), whatsapp: src("whatsapp"), walk_in: src("walk_in") },
    wa_commands: a.wa_commands + b.wa_commands,
    feedback: a.feedback + b.feedback,
    app_minutes: a.app_minutes + b.app_minutes,
  };
}

const series = (daily: Day[], m: Metric) => daily.map((d) => ({ date: d.date, value: Number(d[m] ?? 0) }));

/** One business: its numbers, its 28 days, what it used, and its people (no names or emails). */
function BusinessSheet({ business, onClose }: { business: Business | null; onClose: () => void }) {
  const [detail, setDetail] = React.useState<BusinessDetail | null>(null);
  const [problem, setProblem] = React.useState<string | null>(null);
  const [metric, setMetric] = React.useState<Metric>("events");

  React.useEffect(() => {
    if (!business) return;
    const ctrl = new AbortController();
    getBusinessDetail(business.id, ctrl.signal)
      .then(setDetail)
      .catch((err: unknown) => {
        if (isAbort(err)) return;
        setProblem(
          err instanceof ApiError && err.status === 404
            ? "The detail view needs the backend update in issue #56. The numbers below are from the usage list."
            : err instanceof ApiError
              ? err.detail
              : "This business's detail didn't load.",
        );
      });
    return () => ctrl.abort();
  }, [business]);

  return (
    <Dialog open={business !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        {business && (
          <>
            <DialogHeader>
              <DialogTitle>{business.name}</DialogTitle>
              <DialogDescription>
                {business.template} · {business.is_demo ? "demo · " : ""}
                {fmt(business.users)} {business.users === 1 ? "login" : "logins"}
              </DialogDescription>
            </DialogHeader>
            {problem && (
              <p className="flex items-start gap-2 rounded-md bg-muted px-3 py-2 text-[13px]">
                <Info aria-hidden className="mt-0.5 size-4 shrink-0" /> {problem}
              </p>
            )}
            <StatTiles
              tiles={[
                { label: "Bookings and orders", value: fmt(business.records) },
                { label: "Calls", value: fmt(business.calls) },
                { label: "WhatsApp", value: fmt(business.wa_commands) },
                { label: "Logins", value: fmt(business.users) },
              ]}
            />
            {detail && (
              <>
                <div className="flex flex-col gap-2">
                  <Chips value={metric} options={METRICS.filter((m) => m.id !== "active_businesses")} onChange={setMetric} label="Measure" />
                  <TrendBars points={series(detail.daily, metric)} label={METRICS.find((m) => m.id === metric)!.label} unit={METRICS.find((m) => m.id === metric)!.unit} />
                </div>
                <div className="flex flex-col gap-2">
                  <h3 className="text-sm font-semibold">What they used</h3>
                  <BarList rows={detail.features.map((f) => ({ label: FEATURE_WORDS[f.type] ?? f.type, value: f.count }))} emptyText="Nothing used yet." />
                </div>
                <div className="flex flex-col gap-2">
                  <h3 className="text-sm font-semibold">People</h3>
                  {detail.users.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No logins yet.</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <caption className="sr-only">People at {business.name}, counts only</caption>
                        <thead>
                          <tr className="text-left text-[13px] text-muted-foreground">
                            <th scope="col" className="py-1 pr-2 font-medium">Role</th>
                            <th scope="col" className="py-1 pr-2 text-right font-medium">Logins</th>
                            <th scope="col" className="py-1 pr-2 text-right font-medium">Days active</th>
                            <th scope="col" className="py-1 text-right font-medium">Time in app</th>
                          </tr>
                        </thead>
                        <tbody className="tabular-nums">
                          {detail.users.map((u, i) => (
                            <tr key={u.id} className="border-t">
                              <th scope="row" className="py-1.5 pr-2 text-left font-normal capitalize">
                                {u.role} {detail.users.length > 1 ? i + 1 : ""}
                              </th>
                              <td className="py-1.5 pr-2 text-right">{fmt(u.logins)}</td>
                              <td className="py-1.5 pr-2 text-right">{fmt(u.active_days)}</td>
                              <td className="py-1.5 text-right">{minutes(u.app_minutes)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** Totals from the existing business list, for while the overview endpoint (issue #56) isn't live. */
function fallbackTotals(list: Business[]): Totals {
  const weekAgo = new Date(Date.now() - 7 * 86_400_000).toISOString();
  return {
    businesses: list.length,
    active_businesses_7d: list.filter((b) => (b.last_active ?? "") >= weekAgo).length,
    users: list.reduce((n, b) => n + b.users, 0),
    active_users_7d: 0,
    calls: list.reduce((n, b) => n + b.calls, 0),
    call_minutes: 0,
    records: { bookings: list.filter((b) => b.template !== "wholesale").reduce((n, b) => n + b.records, 0), orders: list.filter((b) => b.template === "wholesale").reduce((n, b) => n + b.records, 0) },
    records_by_source: {},
    wa_commands: list.reduce((n, b) => n + b.wa_commands, 0),
    feedback: 0,
    app_minutes: 0,
  };
}

/**
 * The mentor-facing dashboard (issue #56): how many businesses and people used Catalyst, what
 * they used, and how much time it took (call minutes handled by the AI, minutes in the app).
 * Counts only: no names or phone numbers.
 */
export function Dashboard({ businesses, onAuthError }: { businesses: Business[]; onAuthError: (err: unknown) => boolean }) {
  const [scope, setScope] = React.useState<Scope>("real");
  const [metric, setMetric] = React.useState<Metric>("active_businesses");
  const [overview, setOverview] = React.useState<Overview | null>(null);
  const [missing, setMissing] = React.useState(false);
  const [problem, setProblem] = React.useState<string | null>(null);
  const [open, setOpen] = React.useState<Business | null>(null);

  React.useEffect(() => {
    const ctrl = new AbortController();
    getOverview(scope, ctrl.signal)
      .then((o) => {
        setOverview(o);
        setMissing(false);
        setProblem(null);
      })
      .catch((err: unknown) => {
        if (isAbort(err) || onAuthError(err)) return;
        if (err instanceof ApiError && err.status === 404) setMissing(true);
        else setProblem(err instanceof ApiError ? err.detail : "The dashboard didn't load.");
      });
    return () => ctrl.abort();
  }, [scope, onAuthError]);

  const inScope = businesses.filter((b) => (scope === "all" ? true : scope === "demo" ? b.is_demo : !b.is_demo));
  const totals = overview
    ? scope === "demo"
      ? overview.demo
      : scope === "all"
        ? addTotals(overview.real, overview.demo)
        : overview.real
    : fallbackTotals(inScope);
  const daily = overview?.daily ?? [];
  const m = METRICS.find((x) => x.id === metric)!;

  return (
    <div className="flex flex-col gap-4">
      <Chips value={scope} options={SCOPES} onChange={setScope} label="Which businesses" />

      {missing && (
        <p className="flex items-start gap-2 rounded-md bg-muted px-3 py-2.5 text-[13px]">
          <Info aria-hidden className="mt-0.5 size-4 shrink-0" />
          Call minutes, time in the app, daily trends and the feature breakdown arrive with the backend update in issue #56. Until then these
          numbers come from the usage list.
        </p>
      )}
      {problem && (
        <p role="alert" className="rounded-md bg-destructive-soft px-3 py-2.5 text-sm text-destructive-text">
          {problem}
        </p>
      )}

      <StatTiles tiles={tilesFor(totals)} />

      {overview && (
        <>
          <Section title="Day by day" hint="Last 28 days. One measure at a time, so the bars are always comparable.">
            <Chips value={metric} options={METRICS} onChange={setMetric} label="Measure" />
            <TrendBars points={series(daily, metric)} label={m.label} unit={m.unit} summary={metric === "active_businesses" ? "peak" : "total"} />
          </Section>

          <div className="grid gap-4 lg:grid-cols-2">
            <Section title="What they used" hint="Every action counted, all time.">
              <BarList rows={overview.features.map((f) => ({ label: FEATURE_WORDS[f.type] ?? f.type, value: f.count }))} emptyText="Nothing used yet." />
            </Section>
            <Section title="Who made the bookings and orders" hint="How much the AI does on its own.">
              <BarList
                rows={Object.entries(totals.records_by_source).map(([k, v]) => ({ label: SOURCE_WORDS[k] ?? k, value: v ?? 0 }))}
                emptyText="No bookings or orders yet."
              />
            </Section>
          </div>
        </>
      )}

      <Section title="Businesses" hint="Tap one for its own numbers.">
        {inScope.length === 0 ? (
          <p className="text-sm text-muted-foreground">None yet.</p>
        ) : (
          <ul className="flex flex-col divide-y rounded-md border">
            {inScope.map((b) => (
              <li key={b.id}>
                <button
                  type="button"
                  onClick={() => setOpen(b)}
                  className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-accent focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"
                >
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{b.name}</span>
                      {b.is_demo && <Badge variant="live">Demo</Badge>}
                    </span>
                    <span className="text-[13px] tabular-nums text-muted-foreground">
                      {fmt(b.records)} bookings/orders · {fmt(b.calls)} calls · {fmt(b.wa_commands)} WhatsApp
                    </span>
                  </span>
                  <ChevronRight aria-hidden className="size-4 shrink-0 text-muted-foreground" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <BusinessSheet key={open?.id ?? "closed"} business={open} onClose={() => setOpen(null)} />
    </div>
  );
}

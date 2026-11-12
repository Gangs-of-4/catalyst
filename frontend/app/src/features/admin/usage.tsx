import { Download } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { type Business, usageCsvUrl } from "./api";

const shortDay = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
const when = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }) : "Never";

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col">
      <dt className="text-[13px] text-muted-foreground">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

/** Totals across the real (non-demo) businesses, the headline for the program's usage evidence. */
export function UsageTotals({ businesses }: { businesses: Business[] }) {
  const real = businesses.filter((b) => !b.is_demo);
  const sum = (k: "records" | "calls" | "wa_commands") => real.reduce((n, b) => n + b[k], 0);
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-3 rounded-lg border p-4 sm:grid-cols-4">
      <Stat label="Businesses" value={real.length} />
      <Stat label="Bookings and orders" value={sum("records")} />
      <Stat label="Calls" value={sum("calls")} />
      <Stat label="WhatsApp commands" value={sum("wa_commands")} />
    </dl>
  );
}

/** One business: all-time counts and the last 4 weeks. Counts only, never names or numbers. */
export function BusinessCard({ b }: { b: Business }) {
  return (
    <li className="flex flex-col gap-3 rounded-lg border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-0.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold">{b.name}</span>
            <Badge>{b.template}</Badge>
            {b.is_demo && <Badge variant="live">Demo</Badge>}
          </div>
          <span className="text-[13px] text-muted-foreground">
            {b.users} {b.users === 1 ? "login" : "logins"} · last active {when(b.last_active)}
          </span>
        </div>
        <Button asChild size="sm" variant="ghost" className="shrink-0">
          <a href={usageCsvUrl(b.id)} download aria-label={`Download usage CSV for ${b.name}`}>
            <Download aria-hidden /> CSV
          </a>
        </Button>
      </div>

      <dl className="grid grid-cols-3 gap-3">
        <Stat label="Bookings and orders" value={b.records} />
        <Stat label="Calls" value={b.calls} />
        <Stat label="WhatsApp" value={b.wa_commands} />
      </dl>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">Last 4 weeks for {b.name}</caption>
          <thead>
            <tr className="text-left text-[13px] text-muted-foreground">
              <th scope="col" className="py-1 pr-2 font-medium">
                Week
              </th>
              <th scope="col" className="py-1 pr-2 text-right font-medium">
                Events
              </th>
              <th scope="col" className="py-1 pr-2 text-right font-medium">
                Records
              </th>
              <th scope="col" className="py-1 pr-2 text-right font-medium">
                Calls
              </th>
              <th scope="col" className="py-1 text-right font-medium">
                <abbr title="WhatsApp commands" className="no-underline sm:hidden">
                  WA
                </abbr>
                <span className="hidden sm:inline">WhatsApp</span>
              </th>
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {b.weeks.map((w) => (
              <tr key={w.week_start} className="border-t">
                <th scope="row" className="py-1.5 pr-2 text-left font-normal">
                  {shortDay(w.week_start)}
                </th>
                <td className="py-1.5 pr-2 text-right">{w.events}</td>
                <td className="py-1.5 pr-2 text-right">{w.records}</td>
                <td className="py-1.5 pr-2 text-right">{w.calls}</td>
                <td className="py-1.5 text-right">{w.wa_commands}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </li>
  );
}

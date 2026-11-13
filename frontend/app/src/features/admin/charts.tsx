import * as React from "react";

import { cn } from "@/lib/utils";

import { fmt } from "./format";

/**
 * Chart pieces for the admin dashboard, following the dataviz method: one series per chart (no
 * second axis), one hue in ink tokens (no palette to validate), thin marks with 4px rounded ends on
 * the baseline and a 2px gap, a recessive grid, a hover/tap tooltip, and a table view so nothing
 * depends on seeing the bars.
 */

const shortDay = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short" });

export type Point = { date: string; value: number };

/** Daily bars for one measure. Hover, tap or focus a day to read it; "Show as table" lists every day. */
export function TrendBars({
  points,
  label,
  unit,
  summary = "total",
}: {
  points: Point[];
  label: string;
  unit?: string;
  /** "total" adds the days up (calls, minutes); "peak" shows the busiest day (a daily count of businesses can't be added up). */
  summary?: "total" | "peak";
}) {
  const [active, setActive] = React.useState<number | null>(null);
  const [table, setTable] = React.useState(false);
  const max = Math.max(1, ...points.map((p) => p.value));
  const total = points.reduce((s, p) => s + p.value, 0);
  const shown = active !== null ? points[active] : null;
  const say = (p: Point) => `${shortDay(p.date)}: ${fmt(p.value)}${unit ? ` ${unit}` : ""}`;

  return (
    <figure className="flex flex-col gap-3">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-sm text-muted-foreground">
          {label}, last {points.length} days{summary === "peak" ? ", most in one day" : ""}:{" "}
          <span className="font-semibold text-foreground tabular-nums">{fmt(summary === "peak" ? max : total)}</span>
          {unit ? ` ${unit}` : ""}
        </span>
        <button
          type="button"
          onClick={() => setTable((t) => !t)}
          className="text-[13px] font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline focus-visible:outline-2 focus-visible:outline-ring"
        >
          {table ? "Show as chart" : "Show as table"}
        </button>
      </figcaption>

      {table ? (
        <div className="max-h-64 overflow-y-auto rounded-md border">
          <table className="w-full text-sm">
            <caption className="sr-only">{label} per day</caption>
            <thead className="sticky top-0 bg-background">
              <tr className="text-left text-[13px] text-muted-foreground">
                <th scope="col" className="px-3 py-1.5 font-medium">
                  Day
                </th>
                <th scope="col" className="px-3 py-1.5 text-right font-medium">
                  {label}
                </th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {[...points].reverse().map((p) => (
                <tr key={p.date} className="border-t">
                  <th scope="row" className="px-3 py-1 text-left font-normal">
                    {shortDay(p.date)}
                  </th>
                  <td className="px-3 py-1 text-right">{fmt(p.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex flex-col gap-1">
          {/* The reading for the day under the finger or pointer; announced politely. */}
          <p aria-live="polite" className="h-5 text-[13px] font-medium tabular-nums">
            {shown ? say(shown) : <span className="text-muted-foreground">Tap or point at a day</span>}
          </p>
          <div className="relative h-36" onMouseLeave={() => setActive(null)}>
            {/* Recessive grid: the top value and the baseline. */}
            <span className="pointer-events-none absolute inset-x-0 top-0 border-t border-dashed border-border" />
            <span className="pointer-events-none absolute -top-2.5 right-0 bg-background pl-1 text-[11px] tabular-nums text-muted-foreground">
              {fmt(max)}
            </span>
            <div className="absolute inset-0 flex items-end gap-[2px]" role="list" aria-label={`${label} per day`}>
              {points.map((p, i) => (
                <button
                  key={p.date}
                  type="button"
                  role="listitem"
                  aria-label={say(p)}
                  onMouseEnter={() => setActive(i)}
                  onFocus={() => setActive(i)}
                  onBlur={() => setActive(null)}
                  onClick={() => setActive(i)}
                  className="group flex h-full min-w-0 flex-1 items-end focus-visible:outline-2 focus-visible:outline-ring"
                >
                  <span
                    className={cn(
                      "w-full rounded-t-[4px] bg-foreground/70 transition-colors",
                      active === i ? "bg-foreground" : "group-hover:bg-foreground/90",
                      p.value === 0 && "bg-foreground/15",
                    )}
                    style={{ height: p.value === 0 ? 2 : `${Math.max(3, (p.value / max) * 100)}%` }}
                  />
                </button>
              ))}
            </div>
            <span className="pointer-events-none absolute inset-x-0 bottom-0 border-t border-foreground/30" />
          </div>
          <div className="flex justify-between text-[11px] tabular-nums text-muted-foreground">
            {points.length > 0 && <span>{shortDay(points[0]!.date)}</span>}
            {points.length > 2 && <span>{shortDay(points[Math.floor(points.length / 2)]!.date)}</span>}
            {points.length > 1 && <span>{shortDay(points[points.length - 1]!.date)}</span>}
          </div>
        </div>
      )}
    </figure>
  );
}

/** Sorted horizontal bars with the name and number written out: "what they used". */
export function BarList({ rows, emptyText }: { rows: { label: string; value: number }[]; emptyText: string }) {
  const sorted = [...rows].filter((r) => r.value > 0).sort((a, b) => b.value - a.value);
  const max = Math.max(1, ...sorted.map((r) => r.value));
  if (sorted.length === 0) return <p className="text-sm text-muted-foreground">{emptyText}</p>;
  return (
    <ul className="flex flex-col gap-2.5">
      {sorted.map((r) => (
        <li key={r.label} className="flex flex-col gap-1">
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="min-w-0">{r.label}</span>
            <span className="shrink-0 font-semibold tabular-nums">{fmt(r.value)}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted" aria-hidden>
            <div className="h-full rounded-full bg-foreground/70" style={{ width: `${(r.value / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Headline numbers as tiles (21st.dev "Stats cards", adapted: hairline grid, a plain-words note, no fake trend %). */
export function StatTiles({ tiles }: { tiles: { label: string; value: string; note?: string }[] }) {
  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-4">
      {tiles.map((t) => (
        <div key={t.label} className="flex flex-col gap-1 bg-card p-4">
          <dt className="text-[13px] font-medium text-muted-foreground">{t.label}</dt>
          <dd className="text-2xl font-semibold tracking-tight tabular-nums sm:text-3xl">{t.value}</dd>
          {t.note && <dd className="text-[12px] text-muted-foreground">{t.note}</dd>}
        </div>
      ))}
    </dl>
  );
}


import { CheckCheck, PhoneOff, ShieldAlert, Siren } from "lucide-react";
import type * as React from "react";

import { EmptyState } from "@/components/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { type Call, formatPhone, type InboxItem } from "./api";

const REASON: Record<string, string> = {
  unanswered_question: "Question we couldn't answer",
  staff_request: "Wants to talk to staff",
  failover: "The agent had a problem",
  red_flag: "Red flag",
  grey_zone: "Possibly medical",
  caller_request: "Asked for a person",
  other: "Other",
};

const OUTCOME: Record<string, string> = {
  booked: "Booked",
  changed: "Changed",
  escalated: "Sent to a person",
  callback: "Callback",
  answered: "Answered",
  hung_up: "Hung up",
};

const clock = (iso: string) => new Date(iso).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });

function kindLabel(it: InboxItem) {
  if (it.kind === "escalation") return "Needs a doctor";
  if (it.kind === "ops") return "For our team";
  return it.urgent ? "Urgent callback" : "Callback";
}

/** Callbacks and anything sent to a person. Urgent first (the backend orders them). */
export function InboxPanel({ items, onDone, doneId }: { items: InboxItem[]; onDone: (it: InboxItem) => void; doneId: number | null }) {
  if (items.length === 0) {
    return <EmptyState icon={CheckCheck} title="Nothing waiting" description="Callbacks and calls sent to a person show up here." />;
  }
  return (
    <ul className="flex flex-col gap-2">
      {items.map((it) => {
        const urgent = Boolean(it.urgent) || it.kind === "escalation";
        return (
          <li key={it.id} className={cn("flex flex-col gap-2 rounded-lg border p-3", urgent && "border-destructive/40 bg-destructive-soft")}>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={urgent ? "destructive" : "neutral"}>{kindLabel(it)}</Badge>
              <span className="text-[13px] text-muted-foreground">{clock(it.created_at)}</span>
            </div>
            <div className="text-sm">
              <span className="font-semibold">{it.name || "No name"}</span>
              {it.phone && (
                <>
                  {" · "}
                  <a href={`tel:${it.phone}`} className="tabular-nums underline-offset-4 hover:underline">
                    {formatPhone(it.phone)}
                  </a>
                </>
              )}
            </div>
            {it.reason && <p className="text-[13px] text-muted-foreground">{REASON[it.reason] ?? it.reason}</p>}
            {it.note && <p className="text-sm">{it.note}</p>}
            <Button size="sm" variant="outline" className="w-fit" disabled={doneId === it.id} onClick={() => onDone(it)}>
              Mark done
            </Button>
          </li>
        );
      })}
    </ul>
  );
}

/** The latest calls the front desk took, with a summary and the transcript on tap. */
export function CallsPanel({ calls }: { calls: Call[] }) {
  if (calls.length === 0) {
    return <EmptyState icon={PhoneOff} title="No calls yet" description="Calls the front desk answers appear here." />;
  }
  return (
    <ul className="flex flex-col divide-y rounded-lg border">
      {calls.map((c) => (
        <li key={c.id} className="flex flex-col gap-1.5 p-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-semibold">{c.outcome ? (OUTCOME[c.outcome] ?? c.outcome) : "In progress"}</span>
            <span className="text-[13px] text-muted-foreground">
              {new Date(c.started_at).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" })}
            </span>
          </div>
          {Boolean(c.safety_review) && (
            <p className="flex items-start gap-1.5 text-[13px] font-medium text-destructive-text">
              <ShieldAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
              Check this call: the agent may have said “{c.safety_hits.join("”, “")}”
            </p>
          )}
          {c.summary && <p className="text-sm text-body">{c.summary}</p>}
          {c.transcript && (
            <details className="text-sm">
              <summary className="cursor-pointer text-[13px] font-medium text-muted-foreground hover:text-foreground">Transcript</summary>
              <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-2.5 font-sans text-[13px]">{c.transcript}</pre>
            </details>
          )}
        </li>
      ))}
    </ul>
  );
}

/** The inbox and recent calls, as the desk's side column (right on wide screens, below on phones). */
export function DeskSide({
  inbox,
  calls,
  doneId,
  onDone,
  children,
}: {
  inbox: InboxItem[];
  calls: Call[];
  doneId: number | null;
  onDone: (it: InboxItem) => void;
  /** Anything that sits above the inbox in this column (the order board's add-order form). */
  children?: React.ReactNode;
}) {
  return (
    <aside className="flex flex-col gap-8 lg:sticky lg:top-24 lg:max-h-[calc(100dvh-7rem)] lg:self-start lg:overflow-y-auto">
      {children}
      <section id="inbox" aria-labelledby="inbox-title" className="flex scroll-mt-20 flex-col gap-3">
        <h2 id="inbox-title" className="text-lg font-semibold">
          Inbox {inbox.length > 0 && <span className="text-muted-foreground">({inbox.length})</span>}
        </h2>
        <InboxPanel items={inbox} onDone={onDone} doneId={doneId} />
      </section>
      <section aria-labelledby="calls-title" className="flex flex-col gap-3">
        <h2 id="calls-title" className="text-lg font-semibold">
          Recent calls
        </h2>
        <CallsPanel calls={calls} />
      </section>
    </aside>
  );
}

/** The red strip on phones that jumps down to the inbox when something urgent is waiting. */
export function UrgentBanner({ count }: { count: number }) {
  if (count === 0) return null;
  return (
    <a
      href="#inbox"
      className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive-soft px-3 py-2.5 text-sm font-semibold text-destructive-text lg:hidden"
    >
      <Siren aria-hidden className="size-4" />
      {count} urgent {count === 1 ? "item needs" : "items need"} you. See the inbox.
    </a>
  );
}

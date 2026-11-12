import { AlertCircle, Download, Loader2, MessageSquare, RotateCw, Shield } from "lucide-react";
import * as React from "react";

import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { Field } from "@/components/field";
import { PasswordInput } from "@/components/password-input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { adminLogin, type Business, FEEDBACK_CSV_URL, type FeedbackRow, getBusinesses, getFeedback } from "@/features/admin/api";
import { DecisionDialog, FeedbackCard } from "@/features/admin/feedback";
import { BusinessCard, UsageTotals } from "@/features/admin/usage";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

type Tab = "usage" | "feedback";
type FeedbackFilter = "all" | "undecided";
const isAbort = (e: unknown) => e instanceof DOMException && e.name === "AbortError";

/** The team's password. ADMIN_PASSWORD on the server; its own cookie, never the owner's. */
function AdminLogin({ onIn }: { onIn: () => void }) {
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!password) {
      setError("Enter the admin password.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await adminLogin(password);
      onIn();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Couldn't log in. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-md px-4 py-12 sm:px-6">
      <Card className="gap-5">
        <CardHeader className="flex-row items-center gap-3">
          <span className="flex size-9 items-center justify-center rounded-md bg-muted">
            <Shield aria-hidden className="size-[18px]" />
          </span>
          <CardTitle className="text-lg">Team admin</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
            <Field label="Admin password" error={error ?? undefined}>
              <PasswordInput value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
            </Field>
            <Button type="submit" size="lg" disabled={busy}>
              {busy && <Loader2 aria-hidden className="animate-spin" />} Log in
            </Button>
            <p className="text-[13px] text-muted-foreground">
              For the Catalyst team only. After too many wrong tries it locks for 15 minutes.
            </p>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}

/**
 * The team's admin page (M8, C10): every business's usage evidence (counts only) and the feedback
 * log with decisions, plus the CSV downloads the program asks for. Separate login from owners.
 */
export function AdminPage() {
  const [state, setState] = React.useState<"loading" | "login" | "error" | "ready">("loading");
  const [error, setError] = React.useState<string | null>(null);
  const [businesses, setBusinesses] = React.useState<Business[]>([]);
  const [feedback, setFeedback] = React.useState<FeedbackRow[]>([]);
  const [tab, setTab] = React.useState<Tab>("usage");
  const [filter, setFilter] = React.useState<FeedbackFilter>("undecided");
  const [deciding, setDeciding] = React.useState<FeedbackRow | null>(null);
  const [attempt, setAttempt] = React.useState(0);

  const onAuthError = React.useCallback((err: unknown) => {
    if (err instanceof ApiError && err.status === 401) {
      setState("login");
      return true;
    }
    return false;
  }, []);

  React.useEffect(() => {
    const ctrl = new AbortController();
    Promise.all([getBusinesses(ctrl.signal), getFeedback(ctrl.signal)])
      .then(([b, f]) => {
        setBusinesses(b.businesses);
        setFeedback(f.feedback);
        setState("ready");
      })
      .catch((err: unknown) => {
        if (isAbort(err) || onAuthError(err)) return;
        setError(err instanceof ApiError ? err.detail : "The admin page didn't load.");
        setState("error");
      });
    return () => ctrl.abort();
  }, [attempt, onAuthError]);

  const reload = () => {
    setState("loading");
    setAttempt((n) => n + 1);
  };

  const header = <AppHeader />;

  if (state === "login") {
    return (
      <>
        {header}
        <AdminLogin onIn={reload} />
      </>
    );
  }
  if (state === "error") {
    return (
      <>
        {header}
        <main className="mx-auto max-w-2xl px-4 py-12 sm:px-6">
          <EmptyState
            icon={AlertCircle}
            title="The admin page didn't load"
            description={error ?? undefined}
            action={
              <Button variant="outline" onClick={reload}>
                <RotateCw /> Try again
              </Button>
            }
          />
        </main>
      </>
    );
  }
  if (state === "loading") {
    return (
      <>
        {header}
        <main className="mx-auto flex max-w-4xl flex-col gap-4 px-4 py-8 sm:px-6" role="status" aria-label="Loading">
          <div className="h-8 w-1/3 animate-pulse rounded-md bg-muted" />
          <div className="h-24 animate-pulse rounded-lg bg-muted" />
          <div className="h-48 animate-pulse rounded-lg bg-muted" />
        </main>
      </>
    );
  }

  const undecided = feedback.filter((f) => !f.decision).length;
  const shownFeedback = filter === "undecided" ? feedback.filter((f) => !f.decision) : feedback;
  const sorted = [...businesses].sort((a, b) => Number(a.is_demo) - Number(b.is_demo) || (b.last_active ?? "").localeCompare(a.last_active ?? ""));

  return (
    <>
      {header}
      <main className="mx-auto flex max-w-4xl flex-col gap-5 px-4 py-6 sm:px-6 sm:py-8">
        <h1 className="text-2xl font-semibold leading-tight tracking-tight">Team admin</h1>

        <div role="tablist" aria-label="Admin" className="flex gap-1 rounded-lg bg-muted p-1">
          {(
            [
              { id: "usage", label: "Usage" },
              { id: "feedback", label: `Feedback${undecided ? ` (${undecided})` : ""}` },
            ] as const
          ).map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              id={`tab-${t.id}`}
              aria-selected={tab === t.id}
              aria-controls={`panel-${t.id}`}
              onClick={() => setTab(t.id)}
              className={cn(
                "flex min-h-10 flex-1 items-center justify-center rounded-md px-3 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                tab === t.id ? "bg-background text-foreground shadow-xs" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === "usage" ? (
          <section id="panel-usage" role="tabpanel" aria-labelledby="tab-usage" className="flex flex-col gap-4">
            <UsageTotals businesses={businesses} />
            <p className="text-[13px] text-muted-foreground">Totals leave out the demo businesses. Counts only: no names or phone numbers.</p>
            {sorted.length === 0 ? (
              <EmptyState icon={Shield} title="No businesses yet" />
            ) : (
              <ul aria-label="Businesses" className="flex flex-col gap-3">
                {sorted.map((b) => (
                  <BusinessCard key={b.id} b={b} />
                ))}
              </ul>
            )}
          </section>
        ) : (
          <section id="panel-feedback" role="tabpanel" aria-labelledby="tab-feedback" className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div role="group" aria-label="Show" className="flex gap-1.5">
                {(
                  [
                    { id: "undecided", label: `Undecided ${undecided}` },
                    { id: "all", label: `All ${feedback.length}` },
                  ] as const
                ).map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    aria-pressed={filter === f.id}
                    onClick={() => setFilter(f.id)}
                    className={cn(
                      "min-h-9 rounded-full border px-3.5 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                      filter === f.id ? "border-primary bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
              <Button asChild size="sm" variant="outline">
                <a href={FEEDBACK_CSV_URL} download>
                  <Download aria-hidden /> Feedback CSV
                </a>
              </Button>
            </div>
            {shownFeedback.length === 0 ? (
              <EmptyState
                icon={MessageSquare}
                title={filter === "undecided" ? "Everything has a decision" : "No feedback yet"}
                description="Owners send feedback from their desk and home pages."
              />
            ) : (
              <ul aria-label="Feedback" className="flex flex-col gap-3">
                {shownFeedback.map((f) => (
                  <FeedbackCard key={f.id} row={f} onDecide={setDeciding} />
                ))}
              </ul>
            )}
          </section>
        )}
      </main>

      <DecisionDialog
        key={deciding?.id ?? "closed"}
        row={deciding}
        onClose={() => setDeciding(null)}
        onSaved={(row) => {
          setFeedback((list) => list.map((x) => (x.id === row.id ? row : x)));
          setDeciding(null);
        }}
        onAuthError={onAuthError}
      />
    </>
  );
}

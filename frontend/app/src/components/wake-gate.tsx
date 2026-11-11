import { CloudOff, RotateCw } from "lucide-react";
import * as React from "react";

import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { recentlyHealthy, waitForBackend } from "@/lib/health";

type GateState = "checking" | "waking" | "ready" | "down";

type WakeGateProps = {
  children: React.ReactNode;
  /** For tests: how long to keep trying, and when to show "waking up". */
  budgetMs?: number;
  wakingAfterMs?: number;
};

function WakingScreen() {
  const [seconds, setSeconds] = React.useState(0);
  React.useEffect(() => {
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <main className="mx-auto flex max-w-md flex-col items-center gap-5 px-4 py-20 text-center sm:px-6">
      <span className="relative flex size-14 items-center justify-center" aria-hidden>
        <span className="absolute inset-0 animate-ping rounded-full bg-live-soft" />
        <span className="relative size-4 rounded-full bg-live" />
      </span>
      <div className="flex flex-col gap-2" role="status" aria-live="polite">
        <h1 className="text-[28px] font-semibold leading-tight tracking-tight">Waking up your front desk…</h1>
        <p className="text-body">
          Our server rests when nobody&apos;s using it. The first visit can take up to a minute.
        </p>
      </div>
      <div className="h-1.5 w-56 overflow-hidden rounded-full bg-muted" aria-hidden>
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-1000 ease-linear"
          style={{ width: `${Math.min(95, (seconds / 60) * 100)}%` }}
        />
      </div>
      <p className="text-[13px] tabular-nums text-muted-foreground">{seconds} s</p>
    </main>
  );
}

/**
 * Shows a "waking up" screen until the backend answers /healthz, then renders the page.
 * Skips the check when the backend answered in the last two minutes, so moving between pages
 * doesn't flash it. After the budget it offers a retry.
 */
/** False only for a deployed build with no backend behind /api (set by build.mjs). */
const backendConfigured = () => import.meta.env.VITE_BACKEND_CONFIGURED !== "0";

export function WakeGate({ children, budgetMs, wakingAfterMs }: WakeGateProps) {
  if (!backendConfigured()) return <NotConnected />;
  return (
    <Gate budgetMs={budgetMs} wakingAfterMs={wakingAfterMs}>
      {children}
    </Gate>
  );
}

/** A deploy with no backend yet: say so straight away, rather than "waking up" for 90 s. */
function NotConnected() {
  return (
    <>
      <AppHeader />
      <main className="mx-auto max-w-2xl px-4 py-16 sm:px-6">
        <EmptyState
          icon={CloudOff}
          title="This site isn't connected to a server yet"
          description="Signup, login and the test page need our server, which isn't set up for this site yet. Please check back soon."
        />
      </main>
    </>
  );
}

function Gate({ children, budgetMs, wakingAfterMs }: WakeGateProps) {
  const [state, setState] = React.useState<GateState>(() => (recentlyHealthy() ? "ready" : "checking"));
  const [attempt, setAttempt] = React.useState(0);
  const skipFirst = React.useRef(state === "ready");

  React.useEffect(() => {
    if (skipFirst.current) {
      skipFirst.current = false;
      return;
    }
    const ctrl = new AbortController();
    waitForBackend({
      signal: ctrl.signal,
      budgetMs,
      wakingAfterMs,
      onWaking: () => setState((s) => (s === "checking" ? "waking" : s)),
    }).then((ok) => {
      if (!ctrl.signal.aborted) setState(ok ? "ready" : "down");
    });
    return () => ctrl.abort();
  }, [attempt, budgetMs, wakingAfterMs]);

  if (state === "ready") return <>{children}</>;
  return (
    <>
      <AppHeader />
      {state === "waking" && <WakingScreen />}
      {state === "down" && (
        <main className="mx-auto max-w-2xl px-4 py-16 sm:px-6">
          <EmptyState
            icon={CloudOff}
            title="Catalyst isn't responding"
            description="Our server didn't wake up in time. Try again in a moment."
            action={
              <Button
                variant="outline"
                onClick={() => {
                  setState("checking");
                  setAttempt((n) => n + 1);
                }}
              >
                <RotateCw /> Try again
              </Button>
            }
          />
        </main>
      )}
      {/* "checking": a quick answer is the usual case, so show nothing rather than flash a screen. */}
    </>
  );
}

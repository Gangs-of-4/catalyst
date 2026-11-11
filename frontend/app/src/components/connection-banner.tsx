import { CloudOff, Loader2 } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { useOnline } from "@/hooks/use-online";
import { onConnectionTrouble } from "@/lib/api";
import { pingHealth } from "@/lib/health";

/** Seconds between retries: quick at first, then every 30 s. */
const BACKOFF_S = [2, 4, 8, 15, 30];

/**
 * A banner while the backend can't be reached mid-session (phase2-plan §6 "a banner slides in if the
 * backend is unreachable"). It retries /healthz with backoff and says so when it's back. While the
 * browser itself is offline, OfflineBanner shows instead.
 */
export function ConnectionBanner() {
  const online = useOnline();
  const [trouble, setTrouble] = React.useState(false);
  const [countdown, setCountdown] = React.useState(BACKOFF_S[0]!);
  const [checking, setChecking] = React.useState(false);
  const step = React.useRef(0);
  const inTrouble = React.useRef(false);

  React.useEffect(
    () =>
      onConnectionTrouble(() => {
        if (inTrouble.current) return;
        inTrouble.current = true;
        step.current = 0;
        setCountdown(BACKOFF_S[0]!);
        setTrouble(true);
      }),
    [],
  );

  const check = React.useCallback(async () => {
    setChecking(true);
    const ok = await pingHealth(8000);
    setChecking(false);
    if (ok) {
      inTrouble.current = false;
      setTrouble(false);
      toast.success("Connected again.");
      window.dispatchEvent(new Event("catalyst:reconnected"));
    } else {
      step.current = Math.min(step.current + 1, BACKOFF_S.length - 1);
      setCountdown(BACKOFF_S[step.current]!);
    }
  }, []);

  // Count down to the next retry, only while there's trouble, we're online and not mid-check.
  React.useEffect(() => {
    if (!trouble || !online || checking) return;
    const t = setTimeout(() => {
      if (countdown <= 1) void check();
      else setCountdown((c) => c - 1);
    }, 1000);
    return () => clearTimeout(t);
  }, [trouble, online, checking, countdown, check]);

  if (!trouble || !online) return null;
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 bg-live-soft px-4 py-2.5 text-center text-sm text-live-text"
    >
      <span className="inline-flex items-center gap-2 font-medium">
        <CloudOff aria-hidden className="size-4 shrink-0" />
        Can&apos;t reach Catalyst right now.
      </span>
      <span className="inline-flex items-center gap-2">
        {checking ? (
          <>
            <Loader2 aria-hidden className="size-4 animate-spin" /> Checking…
          </>
        ) : (
          <>
            Retrying in {countdown} s.
            <button
              type="button"
              onClick={() => void check()}
              className="font-semibold underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            >
              Retry now
            </button>
          </>
        )}
      </span>
    </div>
  );
}

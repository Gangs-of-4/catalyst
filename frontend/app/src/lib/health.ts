/**
 * Is the backend awake? The free backend host sleeps when idle and takes up to a minute to wake
 * (phase2-plan §5 "Cold starts", VERIFY). Pages ping /healthz first and show a "waking up" state
 * instead of failing. /healthz is forwarded to the backend like /api (ADR-0041).
 */

/** After a good ping, skip further checks for this long. */
const HEALTHY_FOR_MS = 120_000;
let lastHealthy = 0;

export const markHealthy = () => {
  lastHealthy = Date.now();
};
export const recentlyHealthy = () => Date.now() - lastHealthy < HEALTHY_FOR_MS;
/** For tests. */
export const resetHealth = () => {
  lastHealthy = 0;
};

function sleep(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve) => {
    const onAbort = () => {
      clearTimeout(t);
      resolve();
    };
    const t = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

/**
 * "up": the backend answered. "down": no answer yet (asleep, waking, unreachable), so keep trying.
 * "none": /healthz is a 404, so nothing forwards to a backend at all (no rewrite: a deploy before
 * M10, or a misconfigured one). Waiting can't fix that, so callers stop at once (review on #26).
 */
export type BackendState = "up" | "down" | "none";

/** One ping: true if /healthz answers 2xx within `timeoutMs`. */
export async function pingHealth(timeoutMs = 8000, signal?: AbortSignal): Promise<boolean> {
  return (await pingHealthState(timeoutMs, signal)) === "up";
}

/** One ping, telling "nothing to reach" (404) apart from "not answering yet". */
export async function pingHealthState(timeoutMs = 8000, signal?: AbortSignal): Promise<BackendState> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  const onAbort = () => ctrl.abort();
  signal?.addEventListener("abort", onAbort);
  try {
    const res = await fetch("/healthz", { signal: ctrl.signal, cache: "no-store" });
    if (res.ok) {
      markHealthy();
      return "up";
    }
    return res.status === 404 ? "none" : "down";
  } catch {
    return "down";
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }
}

export type WaitOptions = {
  signal?: AbortSignal;
  /** Called once if the backend isn't answering quickly, i.e. it's probably waking up. */
  onWaking?: () => void;
  /** Give up after this long. */
  budgetMs?: number;
  /** Treat a slow first answer as "waking" after this long. */
  wakingAfterMs?: number;
  pingTimeoutMs?: number;
};

/** Ping until the backend answers or the budget runs out. "none" (404) returns at once. */
export async function waitForBackend({
  signal,
  onWaking,
  budgetMs = 90_000,
  wakingAfterMs = 1500,
  pingTimeoutMs = 8000,
}: WaitOptions = {}): Promise<BackendState> {
  if (recentlyHealthy()) return "up";
  const start = Date.now();
  let waking = false;
  const reportWaking = () => {
    if (!waking) {
      waking = true;
      onWaking?.();
    }
  };
  const wakingTimer = setTimeout(reportWaking, wakingAfterMs);
  try {
    let delay = 1000;
    while (!signal?.aborted) {
      const state = await pingHealthState(pingTimeoutMs, signal);
      if (state !== "down") return state; // up, or nothing to wait for
      if (signal?.aborted || Date.now() - start + delay > budgetMs) return "down";
      reportWaking();
      await sleep(delay, signal);
      delay = Math.min(delay * 2, 5000);
    }
    return "down";
  } finally {
    clearTimeout(wakingTimer);
  }
}

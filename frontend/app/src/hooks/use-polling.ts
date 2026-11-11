import { useEffect, useRef } from "react";

/**
 * Run `fn` now and then every `intervalMs`, while `enabled`. Pauses while the tab is hidden and runs
 * once when it comes back, so a background tab doesn't keep hitting the backend.
 */
export function usePolling(fn: (signal: AbortSignal) => unknown, intervalMs: number, enabled = true) {
  const fnRef = useRef(fn);
  useEffect(() => {
    fnRef.current = fn;
  });

  useEffect(() => {
    if (!enabled) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let ctrl = new AbortController();
    let stopped = false;

    const tick = async () => {
      if (stopped) return;
      if (document.visibilityState === "visible") {
        ctrl = new AbortController();
        try {
          await fnRef.current(ctrl.signal);
        } catch {
          // The caller shows its own error state; polling just carries on.
        }
      }
      if (!stopped) timer = setTimeout(tick, intervalMs);
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        clearTimeout(timer);
        void tick();
      }
    };

    void tick();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      stopped = true;
      clearTimeout(timer);
      ctrl.abort();
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [intervalMs, enabled]);
}

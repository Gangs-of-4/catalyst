import { useEffect } from "react";

import { api, ApiError } from "@/lib/api";

export const PING_MS = 60_000;
const INTERACTIONS = ["pointerdown", "keydown", "wheel", "touchstart"] as const;

/**
 * Counts time in the app for the team's dashboard (issue #56): once a minute, only while the tab is
 * visible and the person tapped, typed or scrolled in that minute, it sends `POST /api/activity`
 * (no body: just "this person was active this minute"). It stops for the rest of the visit if the
 * backend doesn't have the endpoint yet (404) or the person isn't logged in (401).
 */
export function useActivityPing(enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    let lastInteraction = 0;
    let stopped = false;
    const mark = () => {
      lastInteraction = Date.now();
    };
    INTERACTIONS.forEach((e) => window.addEventListener(e, mark, { passive: true }));

    const timer = setInterval(() => {
      if (stopped || document.visibilityState !== "visible" || Date.now() - lastInteraction > PING_MS) return;
      api("/api/activity", { method: "POST" }).catch((err: unknown) => {
        if (err instanceof ApiError && [401, 403, 404, 405].includes(err.status)) stopped = true;
        // Anything else (a network blip): try again next minute. Never shown to the person.
      });
    }, PING_MS);

    return () => {
      clearInterval(timer);
      INTERACTIONS.forEach((e) => window.removeEventListener(e, mark));
    };
  }, [enabled]);
}

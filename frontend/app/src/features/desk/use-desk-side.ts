import * as React from "react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";

import { type Call, getCalls, getInbox, getStats, type InboxItem, markDone, type Stats } from "./api";

/**
 * The panels every desk shares, whatever the board: the inbox, recent calls and today's numbers.
 * `onAuthError` returns true when it handled a 401 (sent the owner to login).
 */
export function useDeskSide(onAuthError: (err: unknown) => boolean) {
  const [inbox, setInbox] = React.useState<InboxItem[]>([]);
  const [calls, setCalls] = React.useState<Call[]>([]);
  const [stats, setStats] = React.useState<Stats | null>(null);
  const [doneId, setDoneId] = React.useState<number | null>(null);

  const loadSide = React.useCallback(
    async (signal?: AbortSignal) => {
      const results = await Promise.allSettled([getInbox(signal), getCalls(signal), getStats(signal)]);
      const [i, c, s] = results;
      if (i.status === "fulfilled") setInbox(i.value);
      if (c.status === "fulfilled") setCalls(c.value);
      if (s.status === "fulfilled") setStats(s.value);
      results.forEach((r) => r.status === "rejected" && onAuthError(r.reason));
    },
    [onAuthError],
  );

  const onInboxDone = React.useCallback(
    async (it: InboxItem) => {
      setDoneId(it.id);
      try {
        await markDone(it.id);
        setInbox((items) => items.filter((x) => x.id !== it.id));
      } catch (err) {
        if (!onAuthError(err)) toast.error(err instanceof ApiError ? err.detail : "Couldn't mark it done. Please try again.");
      } finally {
        setDoneId(null);
        void loadSide();
      }
    },
    [loadSide, onAuthError],
  );

  const urgent = inbox.filter((it) => Boolean(it.urgent) || it.kind === "escalation").length;
  return { inbox, calls, stats, doneId, urgent, loadSide, onInboxDone };
}

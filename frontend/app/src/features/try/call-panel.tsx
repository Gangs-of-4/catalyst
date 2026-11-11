import { Loader2, MicOff, Phone, PhoneOff } from "lucide-react";

import { cn } from "@/lib/utils";

import type { CallProblem, CallState, Line } from "./use-call";

const BARS = 24;

function mmss(total: number) {
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

type CallPanelProps = {
  state: CallState;
  speaking: "assistant" | "user" | null;
  volume: number;
  seconds: number;
  maxSeconds: number;
  lines: Line[];
  problem: CallProblem | null;
  onStart: () => void;
  onStop: () => void;
};

/**
 * The big call button, a live level meter and timer, and the transcript.
 * Pattern from 21st.dev "AI Voice Input" (button + timer + level bars), driven by the real call
 * volume instead of random heights, and restyled to DESIGN.md.
 */
export function CallPanel({
  state,
  speaking,
  volume,
  seconds,
  maxSeconds,
  lines,
  problem,
  onStart,
  onStop,
}: CallPanelProps) {
  const busy = state === "checking" || state === "connecting" || state === "ending";
  const inCall = state === "live" || state === "ending";
  const status =
    state === "checking" || state === "connecting"
      ? "Connecting… allow the microphone if your browser asks."
      : state === "ending"
        ? "Ending the call…"
        : state === "live"
          ? speaking === "assistant"
            ? "Your front desk is speaking…"
            : "Listening… go ahead and speak."
          : "Press the button and talk, like a caller would.";

  return (
    <div className="flex flex-col items-center gap-4 text-center">
      <button
        type="button"
        onClick={inCall ? onStop : onStart}
        disabled={busy}
        aria-label={inCall ? "End the call" : "Talk to your front desk"}
        className={cn(
          "relative flex size-24 items-center justify-center rounded-full text-primary-foreground transition-colors focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring disabled:cursor-wait sm:size-28",
          inCall ? "bg-destructive hover:bg-destructive/90" : "bg-primary hover:bg-primary/90",
        )}
        style={inCall ? { boxShadow: `0 0 0 ${4 + volume * 14}px var(--live-soft)` } : undefined}
      >
        {busy ? (
          <Loader2 aria-hidden className="size-9 animate-spin" />
        ) : inCall ? (
          <PhoneOff aria-hidden className="size-9" />
        ) : (
          <Phone aria-hidden className="size-9" />
        )}
      </button>

      <p className="text-lg font-semibold">{inCall ? "End the call" : "Talk to your front desk"}</p>

      <div className="flex flex-col items-center gap-2" aria-hidden>
        <span className={cn("font-mono text-sm tabular-nums", inCall ? "text-foreground" : "text-muted-foreground")}>
          {mmss(seconds)} / {mmss(maxSeconds)}
        </span>
        <div className="flex h-6 items-center gap-[3px]">
          {Array.from({ length: BARS }, (_, i) => {
            const fromCentre = Math.abs(i - (BARS - 1) / 2) / (BARS / 2);
            const h = inCall ? Math.max(0.12, volume * (1 - fromCentre * 0.7)) : 0.12;
            return (
              <span
                key={i}
                className={cn("w-[3px] rounded-full transition-[height] duration-150", inCall ? "bg-live" : "bg-border")}
                style={{ height: `${Math.round(h * 100)}%` }}
              />
            );
          })}
        </div>
      </div>

      <p role="status" aria-live="polite" className="min-h-6 text-sm text-body">
        {status}
      </p>

      {problem && (
        <div
          role="alert"
          className={cn(
            "flex w-full items-start gap-2.5 rounded-md px-4 py-3 text-left text-sm",
            problem.kind === "minutes" || problem.kind === "voice"
              ? "bg-muted text-foreground"
              : "bg-destructive-soft text-destructive-text",
          )}
        >
          {problem.kind === "mic" && <MicOff aria-hidden className="mt-0.5 size-4 shrink-0" />}
          <p>{problem.message}</p>
        </div>
      )}

      {lines.length > 0 && (
        <ol aria-label="What was said" className="flex max-h-72 w-full flex-col gap-2 overflow-y-auto text-left">
          {lines.map((l) => (
            <li
              key={l.id}
              className={cn(
                "max-w-[85%] rounded-lg px-3 py-2 text-sm",
                l.role === "assistant" ? "self-start bg-muted" : "self-end bg-primary text-primary-foreground",
              )}
            >
              <span className="sr-only">{l.role === "assistant" ? "Front desk: " : "You: "}</span>
              {l.text}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

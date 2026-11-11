import * as React from "react";

import { ApiError } from "@/lib/api";
import { recentlyHealthy, waitForBackend } from "@/lib/health";
import { CallCancelled, requestMicrophone, startCall, type CallRole, type VoiceCall } from "@/lib/voice";

import { startCheck, type TryInfo } from "./api";

export type CallState = "idle" | "waking" | "checking" | "connecting" | "live" | "ending";

/** Why a call can't start or stopped, each with its own one-line fix on the page. */
export type CallProblem =
  | { kind: "mic"; message: string }
  | { kind: "minutes"; message: string }
  | { kind: "voice"; message: string }
  | { kind: "other"; message: string };

export type Line = { id: number; role: CallRole; text: string };

const DEFAULT_MAX_SECONDS = 180;

/** One web call to this business's assistant: the cap check, then the voice SDK. */
export function useCall(info: TryInfo | null, onCallEnded: () => void) {
  const [state, setState] = React.useState<CallState>("idle");
  const [speaking, setSpeaking] = React.useState<CallRole | null>(null);
  const [volume, setVolume] = React.useState(0);
  const [lines, setLines] = React.useState<Line[]>([]);
  const [seconds, setSeconds] = React.useState(0);
  const [maxSeconds, setMaxSeconds] = React.useState(DEFAULT_MAX_SECONDS);
  const [problem, setProblem] = React.useState<CallProblem | null>(null);
  const callRef = React.useRef<VoiceCall | null>(null);
  /** The start in progress (cap check, connecting). Aborted when the page closes or on Cancel. */
  const pendingRef = React.useRef<AbortController | null>(null);
  const stopTimerRef = React.useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const lineId = React.useRef(0);
  const endedRef = React.useRef(onCallEnded);
  React.useEffect(() => {
    endedRef.current = onCallEnded;
  });

  // Count the call's length while it's live.
  React.useEffect(() => {
    if (state !== "live") return;
    const t = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [state]);

  // If the page goes away: cancel a start that's still in progress, hang up a live call.
  React.useEffect(
    () => () => {
      pendingRef.current?.abort();
      callRef.current?.stop();
      clearTimeout(stopTimerRef.current);
    },
    [],
  );

  const finish = React.useCallback(() => {
    callRef.current = null;
    setState("idle");
    setSpeaking(null);
    setVolume(0);
    endedRef.current();
  }, []);

  const start = React.useCallback(async () => {
    if (!info?.voice || state !== "idle") return;
    const ctrl = new AbortController();
    pendingRef.current = ctrl;
    const cancelled = () => ctrl.signal.aborted;
    setProblem(null);
    setLines([]);
    setSeconds(0);
    // Wake the backend before the call if it hasn't answered lately (phase2-plan §5, cold starts).
    if (!recentlyHealthy()) {
      setState("waking");
      const backend = await waitForBackend({ signal: ctrl.signal });
      if (cancelled()) return;
      if (backend === "none") {
        setState("idle");
        setProblem({ kind: "other", message: "This site isn't connected to a server yet, so calls can't start here." });
        return;
      }
      if (backend !== "up") {
        setState("idle");
        setProblem({ kind: "other", message: "Catalyst isn't responding right now. Please try again in a minute." });
        return;
      }
    }
    setState("checking");
    // Microphone first: /start counts the call, so a denied mic mustn't use up a daily call.
    try {
      await requestMicrophone();
    } catch {
      if (cancelled()) return;
      setState("idle");
      setProblem({
        kind: "mic",
        message: "Your browser blocked the microphone. Allow it from the lock icon next to the address, then try again.",
      });
      return;
    }
    try {
      const { max_call_seconds } = await startCheck(info.public_id);
      if (cancelled()) return;
      setMaxSeconds(max_call_seconds || DEFAULT_MAX_SECONDS);
    } catch (err) {
      if (cancelled()) return;
      setState("idle");
      if (err instanceof ApiError && err.code === "MINUTES_USED_UP") setProblem({ kind: "minutes", message: err.detail });
      else if (err instanceof ApiError && err.code === "VOICE_NOT_CONFIGURED")
        setProblem({ kind: "voice", message: err.detail });
      else
        setProblem({ kind: "other", message: err instanceof ApiError ? err.detail : "The call couldn't start." });
      return;
    }
    if (cancelled()) return;
    setState("connecting");
    try {
      const call = await startCall(info.voice.public_key, info.voice.assistant_id, {
        onLive: () => setState("live"),
        onEnded: finish,
        onSpeaking: setSpeaking,
        onVolume: setVolume,
        onTranscript: (role, text) => setLines((ls) => [...ls, { id: ++lineId.current, role, text }]),
        onError: (message) => {
          setProblem({ kind: "other", message });
          finish();
        },
      }, ctrl.signal);
      if (cancelled()) {
        call.stop(); // belt and braces: never keep a call the page no longer wants
        return;
      }
      callRef.current = call;
    } catch (err) {
      if (cancelled() || err instanceof CallCancelled) return;
      setState("idle");
      setProblem({ kind: "other", message: err instanceof Error ? err.message : "The call couldn't start." });
    } finally {
      if (pendingRef.current === ctrl) pendingRef.current = null;
    }
  }, [info, state, finish]);

  /** Cancel a start that hasn't connected yet (the button reads "Cancel" meanwhile). */
  const cancel = React.useCallback(() => {
    pendingRef.current?.abort();
    pendingRef.current = null;
    setState("idle");
    setProblem(null);
  }, []);

  const stop = React.useCallback(() => {
    const call = callRef.current;
    if (!call) return;
    setState("ending");
    call.stop();
    // If the SDK never reports the hang-up, don't leave the page stuck on "Ending…".
    clearTimeout(stopTimerRef.current);
    stopTimerRef.current = setTimeout(() => {
      if (callRef.current === call) finish();
    }, 4000);
  }, [finish]);

  return { state, speaking, volume, lines, seconds, maxSeconds, problem, start, stop, cancel };
}

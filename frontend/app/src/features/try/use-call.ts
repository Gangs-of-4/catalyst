import * as React from "react";

import { ApiError } from "@/lib/api";
import { MicBlockedError, startCall, type CallRole, type VoiceCall } from "@/lib/voice";

import { startCheck, type TryInfo } from "./api";

export type CallState = "idle" | "checking" | "connecting" | "live" | "ending";

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

  // Hang up if the page goes away mid-call.
  React.useEffect(() => () => callRef.current?.stop(), []);

  const finish = React.useCallback(() => {
    callRef.current = null;
    setState("idle");
    setSpeaking(null);
    setVolume(0);
    endedRef.current();
  }, []);

  const start = React.useCallback(async () => {
    if (!info?.voice || state !== "idle") return;
    setProblem(null);
    setLines([]);
    setSeconds(0);
    setState("checking");
    try {
      const { max_call_seconds } = await startCheck(info.public_id);
      setMaxSeconds(max_call_seconds || DEFAULT_MAX_SECONDS);
    } catch (err) {
      setState("idle");
      if (err instanceof ApiError && err.code === "MINUTES_USED_UP") setProblem({ kind: "minutes", message: err.detail });
      else if (err instanceof ApiError && err.code === "VOICE_NOT_CONFIGURED")
        setProblem({ kind: "voice", message: err.detail });
      else
        setProblem({ kind: "other", message: err instanceof ApiError ? err.detail : "The call couldn't start." });
      return;
    }
    setState("connecting");
    try {
      callRef.current = await startCall(info.voice.public_key, info.voice.assistant_id, {
        onLive: () => setState("live"),
        onEnded: finish,
        onSpeaking: setSpeaking,
        onVolume: setVolume,
        onTranscript: (role, text) => setLines((ls) => [...ls, { id: ++lineId.current, role, text }]),
        onError: (message) => {
          setProblem({ kind: "other", message });
          finish();
        },
      });
    } catch (err) {
      setState("idle");
      setProblem(
        err instanceof MicBlockedError || (err instanceof Error && err.name === "MicBlockedError")
          ? {
              kind: "mic",
              message:
                "Your browser blocked the microphone. Allow it from the lock icon next to the address, then try again.",
            }
          : { kind: "other", message: err instanceof Error ? err.message : "The call couldn't start." },
      );
    }
  }, [info, state, finish]);

  const stop = React.useCallback(() => {
    const call = callRef.current;
    if (!call) return;
    setState("ending");
    call.stop();
    // If the SDK never reports the hang-up, don't leave the page stuck on "Ending…".
    setTimeout(() => {
      if (callRef.current === call) finish();
    }, 4000);
  }, [finish]);

  return { state, speaking, volume, lines, seconds, maxSeconds, problem, start, stop };
}

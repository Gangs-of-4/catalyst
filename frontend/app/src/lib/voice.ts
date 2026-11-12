/**
 * The browser side of a voice web call. The only file that touches the Vapi Web SDK, so the voice
 * platform can change behind it (the frontend twin of the backend's VoiceOrchestrator, ADR-0029).
 * The SDK (with its WebRTC dependency) loads only when a call starts, so pages stay light.
 */

export type CallRole = "assistant" | "user";

export type CallEvents = {
  onLive: () => void;
  onEnded: () => void;
  onSpeaking: (who: CallRole) => void;
  onVolume: (level: number) => void;
  onTranscript: (role: CallRole, text: string) => void;
  onError: (message: string) => void;
};

export type VoiceCall = { stop: () => void };

/** Thrown before a call starts when the browser won't give us the microphone. */
export class MicBlockedError extends Error {
  constructor() {
    super("The microphone is blocked.");
    this.name = "MicBlockedError";
  }
}

/**
 * Ask for the microphone. Call this before the cap check (`POST /api/try/{id}/start`), so a denied
 * microphone never uses up one of the business's daily calls, and the denial gets a clear message
 * instead of a vague SDK error. Throws MicBlockedError.
 */
export async function requestMicrophone() {
  if (!navigator.mediaDevices?.getUserMedia) throw new MicBlockedError();
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((t) => t.stop());
  } catch {
    throw new MicBlockedError();
  }
}

type VapiMessage = { type?: string; transcriptType?: string; transcript?: string; role?: string };

function errorText(e: unknown): string {
  const any = e as { errorMsg?: string; message?: string; error?: { message?: string } } | undefined;
  return String(any?.errorMsg || any?.message || any?.error?.message || "The call couldn't connect.");
}

/** Thrown when a pending start is cancelled (the page closed, or the owner pressed Cancel). */
export class CallCancelled extends Error {
  constructor() {
    super("The call was cancelled.");
    this.name = "CallCancelled";
  }
}

type VapiClass = typeof import("@vapi-ai/web").default;

/**
 * The Vapi class from the SDK module, whichever shape the bundler gives it. `@vapi-ai/web` is
 * CommonJS (`exports.default = Vapi`), and Vite's production build hands a dynamic import of it
 * back as `{ default: { default: Vapi } }`, so `new mod.default()` failed on the live site with
 * "i is not a constructor". The dev server and the tests give `{ default: Vapi }`.
 */
export function vapiClass(mod: unknown): VapiClass {
  let found: unknown = mod;
  for (let i = 0; i < 3 && typeof found !== "function"; i++) {
    found = (found as { default?: unknown } | undefined)?.default;
  }
  if (typeof found !== "function") throw new Error("The voice library didn't load. Reload the page.");
  return found as VapiClass;
}

/**
 * Start the web call. Call `requestMicrophone()` first. Aborting `signal` cancels a pending start
 * and hangs up a call that connects afterwards, so closing the page mid-connect never leaves a call
 * running in the background with the microphone on (review on #25).
 */
export async function startCall(
  publicKey: string,
  assistantId: string,
  events: CallEvents,
  signal?: AbortSignal,
): Promise<VoiceCall> {
  const Vapi = vapiClass(await import("@vapi-ai/web"));
  if (signal?.aborted) throw new CallCancelled();
  const vapi = new Vapi(publicKey);
  vapi.on("call-start", events.onLive);
  vapi.on("call-end", events.onEnded);
  vapi.on("speech-start", () => events.onSpeaking("assistant"));
  vapi.on("speech-end", () => events.onSpeaking("user"));
  vapi.on("volume-level", (v: number) => events.onVolume(Math.min(1, Math.max(0, v))));
  vapi.on("message", (m: VapiMessage) => {
    if (m?.type === "transcript" && m.transcriptType === "final" && m.transcript) {
      events.onTranscript(m.role === "assistant" ? "assistant" : "user", m.transcript);
    }
  });
  vapi.on("error", (e: unknown) => events.onError(errorText(e)));
  const stop = () => void vapi.stop();
  signal?.addEventListener("abort", stop, { once: true });
  try {
    await vapi.start(assistantId);
  } catch (err) {
    signal?.removeEventListener("abort", stop);
    throw signal?.aborted ? new CallCancelled() : err;
  }
  if (signal?.aborted) {
    stop(); // connected after the page asked to cancel: hang up at once
    throw new CallCancelled();
  }
  return { stop };
}

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

/** Ask for the microphone first, so a denial gets a clear message instead of a vague SDK error. */
async function ensureMicrophone() {
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

export async function startCall(publicKey: string, assistantId: string, events: CallEvents): Promise<VoiceCall> {
  await ensureMicrophone();
  const { default: Vapi } = await import("@vapi-ai/web");
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
  await vapi.start(assistantId);
  return { stop: () => void vapi.stop() };
}

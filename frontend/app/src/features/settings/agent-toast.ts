import { toast } from "sonner";

/** The backend's agent sentence without its leading "Saved." / "Saved, but", for use after another lead-in. */
function withoutSaved(agent: string): string {
  const rest = agent.replace(/^Saved\.\s*/i, "").replace(/^Saved, but\s*/i, "");
  return rest.charAt(0).toUpperCase() + rest.slice(1);
}

/**
 * Show the backend's sentence about the voice agent after a save (contracts.md §6.1 `agent`). It
 * already says "Saved…", so a plain save shows it as is, never with another "Saved." in front; a
 * failed update is a warning, not a success. `lead` replaces "Saved" for other actions ("Added.").
 */
export function agentToast(agent: string, lead?: string) {
  const text = lead ? `${lead} ${withoutSaved(agent)}` : agent;
  if (/fail/i.test(agent)) toast.warning(text);
  else toast.success(text);
}

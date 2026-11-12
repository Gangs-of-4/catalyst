import { Loader2, RotateCcw, TriangleAlert } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

import { agentToast } from "./agent-toast";
import { getInstructions, type Rejected, saveInstructions, undoInstructions } from "./api";

type Props = {
  onAuthError: (err: unknown) => boolean;
  /** Tells the page there's unsaved text, so leaving asks first. */
  onDirtyChange: (dirty: boolean) => void;
};

/**
 * "Agent ko aur kya batana hai?": the owner's own instructions (contracts.md §6.1). Each line is
 * screened; accepted lines become the new version, rejected ones are listed with the reason and
 * left for the owner to rewrite. It has its own Save (a separate endpoint) and an Undo.
 */
export function InstructionsSection({ onAuthError, onDirtyChange }: Props) {
  const [saved, setSaved] = React.useState<string | null>(null);
  const [text, setText] = React.useState("");
  const [max, setMax] = React.useState(500);
  const [hasVersion, setHasVersion] = React.useState(false);
  const [rejected, setRejected] = React.useState<Rejected[]>([]);
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState<"save" | "undo" | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const id = React.useId();

  React.useEffect(() => {
    const ctrl = new AbortController();
    getInstructions(ctrl.signal)
      .then((r) => {
        setSaved(r.text);
        setText(r.text);
        setMax(r.max_chars);
        setHasVersion(r.version_id !== null);
        setRejected(r.rejected ?? []); // also lines rejected from WhatsApp, not only this page
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (!onAuthError(err)) setLoadError(err instanceof ApiError ? err.detail : "Your instructions didn't load.");
      });
    return () => ctrl.abort();
  }, [onAuthError]);

  const dirty = saved !== null && text.trim() !== saved.trim();
  React.useEffect(() => onDirtyChange(dirty), [dirty, onDirtyChange]);

  async function onSave() {
    setBusy("save");
    setError(null);
    try {
      const r = await saveInstructions(text.trim());
      setRejected(r.rejected);
      if (r.version_id === null && r.rejected.length > 0) {
        // Every line was rejected: nothing changed, keep the text so it can be rewritten.
        toast.error(r.agent);
        return;
      }
      const now = r.accepted.join("\n");
      setSaved(now);
      setText(now);
      setHasVersion(r.version_id !== null);
      agentToast(r.agent, r.rejected.length ? "Saved the other lines." : undefined);
    } catch (err) {
      if (!onAuthError(err)) setError(err instanceof ApiError ? err.detail : "Couldn't save. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  async function onUndo() {
    setBusy("undo");
    setError(null);
    try {
      const r = await undoInstructions();
      setSaved(r.text);
      setText(r.text);
      setRejected([]);
      setHasVersion(r.version_id !== null);
      agentToast(r.agent, "Back to the earlier version.");
    } catch (err) {
      if (onAuthError(err)) return;
      if (err instanceof ApiError && err.status === 404) setHasVersion(false);
      setError(err instanceof ApiError ? err.detail : "Couldn't undo. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  if (loadError) return <p className="text-sm text-destructive">{loadError}</p>;
  if (saved === null) return <div className="h-32 animate-pulse rounded-lg bg-muted" role="status" aria-label="Loading your instructions" />;

  const over = text.length > max;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        <label htmlFor={id} className="text-sm font-medium">
          Agent ko aur kya batana hai?
        </label>
        <p id={`${id}-hint`} className="text-[13px] leading-snug text-muted-foreground">
          One instruction per line, e.g. &ldquo;Naye patients ko pehli baar aane par ID laane ko kahiye.&rdquo; Lines about medicines or
          doses, prices or offers, pretending to be a person, or turning off safety aren&apos;t saved.
        </p>
        <Textarea
          id={id}
          value={text}
          onChange={(e) => setText(e.target.value)}
          aria-describedby={`${id}-hint ${id}-count`}
          aria-invalid={over || error ? true : undefined}
          className="min-h-28"
        />
        <p id={`${id}-count`} aria-live="polite" className={cn("self-end text-[13px] tabular-nums", over ? "font-medium text-destructive" : "text-muted-foreground")}>
          {text.length}/{max}
        </p>
      </div>

      {rejected.length > 0 && (
        <div role="alert" className="flex flex-col gap-2 rounded-lg border border-live/40 bg-live-soft px-3 py-2.5 text-sm text-live-text">
          <p className="flex items-center gap-1.5 font-semibold">
            <TriangleAlert aria-hidden className="size-4" /> {rejected.length === 1 ? "This line wasn't saved" : "These lines weren't saved"}
          </p>
          <ul className="flex flex-col gap-1.5">
            {rejected.map((r, i) => (
              <li key={i}>
                <span className="font-medium">&ldquo;{r.line}&rdquo;</span>
                <span className="block text-[13px]">{r.reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm font-medium text-destructive">
          {error}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <Button onClick={() => void onSave()} disabled={!dirty || over || busy !== null}>
          {busy === "save" && <Loader2 aria-hidden className="animate-spin" />} Save instructions
        </Button>
        {hasVersion && (
          <Button variant="ghost" onClick={() => void onUndo()} disabled={busy !== null}>
            {busy === "undo" ? <Loader2 aria-hidden className="animate-spin" /> : <RotateCcw aria-hidden />} Undo last change
          </Button>
        )}
      </div>
    </div>
  );
}

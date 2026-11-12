import { Loader2, MessageSquarePlus } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { Field } from "@/components/field";
import { Fieldset } from "@/components/fieldset";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

/** The feedback types (contracts.md §3.1), in the words an owner would use. */
const TYPES = [
  { id: "bug", label: "Something isn't working" },
  { id: "feature", label: "I wish it could…" },
  { id: "usability", label: "Hard to use" },
  { id: "data_integration", label: "My data or other apps" },
  { id: "pricing_business", label: "Price or business" },
] as const;
type FeedbackType = (typeof TYPES)[number]["id"];

const ROLES = ["Owner", "Doctor", "Receptionist", "Staff"] as const;
const MAX = 2000;

type Draft = { name: string; role: string; type: FeedbackType | ""; text: string };

const sendFeedback = (d: Draft) =>
  api<{ id: number; saved: boolean }>("/api/feedback", {
    method: "POST",
    body: { person_name: d.name.trim(), person_role: d.role.trim(), text: d.text.trim(), type: d.type },
  });

/**
 * "Send feedback" for logged-in owners and staff (contracts.md §6.1 `POST /api/feedback`). It goes
 * to the team's feedback log on /admin. What was typed survives closing the sheet until it's sent.
 */
export function FeedbackButton({ defaultName = "", className }: { defaultName?: string; className?: string }) {
  const [open, setOpen] = React.useState(false);
  const [draft, setDraft] = React.useState<Draft>({ name: defaultName, role: "Owner", type: "", text: "" });
  const [errors, setErrors] = React.useState<Record<string, string>>({});
  const [problem, setProblem] = React.useState<string | null>(null);
  const [sending, setSending] = React.useState(false);

  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft((d) => ({ ...d, [k]: v }));
  const typeRefs = React.useRef<(HTMLButtonElement | null)[]>([]);

  function onTypeKey(e: React.KeyboardEvent) {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!step) return;
    e.preventDefault();
    const at = TYPES.findIndex((t) => t.id === draft.type);
    const next = (Math.max(at, 0) + (at < 0 && step > 0 ? 0 : step) + TYPES.length) % TYPES.length;
    set("type", TYPES[next]!.id);
    typeRefs.current[next]?.focus();
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!draft.name.trim()) errs.person_name = "Write your name.";
    if (!draft.role.trim()) errs.person_role = "Say what you do there.";
    if (!draft.type) errs.type = "Pick what it's about.";
    if (draft.text.trim().length < 3) errs.text = "Tell us a little more.";
    setErrors(errs);
    setProblem(null);
    if (Object.keys(errs).length) return;
    setSending(true);
    try {
      await sendFeedback(draft);
      setDraft({ name: draft.name, role: draft.role, type: "", text: "" }); // keep who they are for next time
      setOpen(false);
      toast.success("Thank you. The team reads every message.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setProblem("You've been logged out. Log in again, then send; your message is kept here.");
      else if (err instanceof ApiError) {
        setErrors(err.fields);
        setProblem(Object.keys(err.fields).length ? null : err.detail);
      } else setProblem("Couldn't send it. Please try again.");
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <Button variant="ghost" size="sm" className={className} onClick={() => setOpen(true)}>
        <MessageSquarePlus aria-hidden /> Feedback
      </Button>
      <Dialog open={open} onOpenChange={(o) => !sending && setOpen(o)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Send feedback</DialogTitle>
            <DialogDescription>A problem, an idea, anything. It goes straight to the Catalyst team.</DialogDescription>
          </DialogHeader>
          <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
            <Fieldset legend="What's it about?" error={errors.type}>
              {/* Radio-group keyboard pattern: one Tab stop, arrow keys move and select. */}
              <div role="radiogroup" aria-label="What's it about?" className="flex flex-wrap gap-2" onKeyDown={onTypeKey}>
                {TYPES.map((t, i) => (
                  <button
                    key={t.id}
                    ref={(el) => {
                      typeRefs.current[i] = el;
                    }}
                    type="button"
                    role="radio"
                    aria-checked={draft.type === t.id}
                    tabIndex={draft.type === t.id || (!draft.type && i === 0) ? 0 : -1}
                    onClick={() => set("type", t.id)}
                    className={cn(
                      "min-h-9 rounded-full border px-3.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
                      draft.type === t.id ? "border-primary bg-primary text-primary-foreground" : "bg-background hover:bg-accent",
                    )}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </Fieldset>
            <Field label="Your message" error={errors.text}>
              <Textarea value={draft.text} onChange={(e) => set("text", e.target.value)} maxLength={MAX} className="min-h-28" />
            </Field>
            <p className="-mt-3 self-end text-[13px] tabular-nums text-muted-foreground">
              {draft.text.length}/{MAX}
            </p>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Your name" error={errors.person_name}>
                <Input value={draft.name} onChange={(e) => set("name", e.target.value)} maxLength={80} autoComplete="name" />
              </Field>
              <Field label="You are" error={errors.person_role}>
                <Input value={draft.role} onChange={(e) => set("role", e.target.value)} maxLength={60} list="feedback-roles" />
              </Field>
              <datalist id="feedback-roles">
                {ROLES.map((r) => (
                  <option key={r} value={r} />
                ))}
              </datalist>
            </div>
            {problem && (
              <p role="alert" className="rounded-md bg-destructive-soft px-3 py-2.5 text-sm text-destructive-text">
                {problem}
              </p>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)} disabled={sending}>
                Back
              </Button>
              <Button type="submit" disabled={sending}>
                {sending && <Loader2 aria-hidden className="animate-spin" />} Send
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

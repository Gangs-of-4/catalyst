import { Loader2 } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { Field } from "@/components/field";
import { Fieldset } from "@/components/fieldset";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { ApiError } from "@/lib/api";

import { type Decision, DECISION_WORDS, decideFeedback, type FeedbackRow, TYPE_WORDS } from "./api";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

export function FeedbackCard({ row, onDecide }: { row: FeedbackRow; onDecide: (row: FeedbackRow) => void }) {
  return (
    <li className="flex flex-col gap-2 rounded-lg border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge>{TYPE_WORDS[row.type] ?? row.type}</Badge>
        {row.decision ? (
          <Badge variant={row.decision === "shipped" ? "success" : row.decision === "wont_do" ? "destructive" : "neutral"}>
            {DECISION_WORDS[row.decision]}
          </Badge>
        ) : (
          <Badge variant="live">Undecided</Badge>
        )}
        <span className="text-[13px] text-muted-foreground">{day(row.created_at)}</span>
      </div>
      <p className="text-sm font-medium">
        {row.business} — {row.person_name} <span className="font-normal text-muted-foreground">({row.person_role})</span>
      </p>
      <p className="whitespace-pre-wrap text-sm text-body">{row.text}</p>
      {(row.decision_reason || row.shipped_on || row.evidence_url || row.partner_reaction) && (
        <dl className="grid gap-1 border-t pt-2 text-[13px]">
          {row.decision_reason && (
            <div>
              <dt className="inline text-muted-foreground">Why: </dt>
              <dd className="inline">{row.decision_reason}</dd>
            </div>
          )}
          {row.shipped_on && (
            <div>
              <dt className="inline text-muted-foreground">Shipped on: </dt>
              <dd className="inline">{row.shipped_on}</dd>
            </div>
          )}
          {row.evidence_url && (
            <div className="truncate">
              <dt className="inline text-muted-foreground">Evidence: </dt>
              <dd className="inline">
                <a href={row.evidence_url} target="_blank" rel="noreferrer noopener" className="underline underline-offset-4">
                  {row.evidence_url}
                </a>
              </dd>
            </div>
          )}
          {row.partner_reaction && (
            <div>
              <dt className="inline text-muted-foreground">Their reaction: </dt>
              <dd className="inline">{row.partner_reaction}</dd>
            </div>
          )}
        </dl>
      )}
      <Button size="sm" variant="outline" className="w-fit" onClick={() => onDecide(row)}>
        {row.decision ? "Change decision" : "Decide"}
      </Button>
    </li>
  );
}

/** Record what the team decided about one piece of feedback (contracts.md §6.1 `PUT /api/admin/feedback/{id}`). */
export function DecisionDialog({
  row,
  onClose,
  onSaved,
  onAuthError,
}: {
  row: FeedbackRow | null;
  onClose: () => void;
  onSaved: (row: FeedbackRow) => void;
  onAuthError: (err: unknown) => boolean;
}) {
  const [decision, setDecision] = React.useState<Decision | "">(row?.decision ?? "");
  const [reason, setReason] = React.useState(row?.decision_reason ?? "");
  const [shippedOn, setShippedOn] = React.useState(row?.shipped_on ?? "");
  const [evidence, setEvidence] = React.useState(row?.evidence_url ?? "");
  const [reaction, setReaction] = React.useState(row?.partner_reaction ?? "");
  const [errors, setErrors] = React.useState<Record<string, string>>({});
  const [problem, setProblem] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!row) return;
    const errs: Record<string, string> = {};
    if (decision === "wont_do" && !reason.trim()) errs.decision_reason = "Say why it won't be done.";
    if (evidence.trim() && !/^https:\/\/\S+$/.test(evidence.trim())) errs.evidence_url = "Evidence must be a link starting with https://.";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setSaving(true);
    setProblem(null);
    try {
      const saved = await decideFeedback(row.id, {
        decision: decision || null,
        decision_reason: reason.trim(),
        shipped_on: shippedOn || null,
        evidence_url: evidence.trim(),
        partner_reaction: reaction.trim(),
      });
      onSaved(saved);
      toast.success("Decision saved.");
    } catch (err) {
      if (onAuthError(err)) return;
      if (err instanceof ApiError) {
        setErrors(err.fields);
        setProblem(Object.keys(err.fields).length ? null : err.detail);
      } else {
        setProblem("Couldn't save. Please try again.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={row !== null} onOpenChange={(open) => !open && !saving && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Decision</DialogTitle>
          {row && (
            <DialogDescription>
              {row.business} — {row.person_name}: &ldquo;{row.text.length > 120 ? `${row.text.slice(0, 120)}…` : row.text}&rdquo;
            </DialogDescription>
          )}
        </DialogHeader>
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
          <Fieldset legend="What we decided" error={errors.decision}>
            <RadioGroup value={decision || "none"} onValueChange={(v) => setDecision(v === "none" ? "" : (v as Decision))} className="grid grid-cols-2 gap-3">
              {/* "Undecided" clears a decision recorded by mistake (the backend takes decision: null). */}
              <div className="flex items-center gap-2">
                <RadioGroupItem value="none" id="decision-none" />
                <Label htmlFor="decision-none">Undecided</Label>
              </div>
              {(Object.keys(DECISION_WORDS) as Decision[]).map((d) => (
                <div key={d} className="flex items-center gap-2">
                  <RadioGroupItem value={d} id={`decision-${d}`} />
                  <Label htmlFor={`decision-${d}`}>{DECISION_WORDS[d]}</Label>
                </div>
              ))}
            </RadioGroup>
          </Fieldset>
          <Field label="Why" optional={decision !== "wont_do"} error={errors.decision_reason}>
            <Input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Shipped on" optional error={errors.shipped_on}>
              <Input type="date" value={shippedOn} onChange={(e) => setShippedOn(e.target.value)} />
            </Field>
            <Field label="Evidence link" optional error={errors.evidence_url} hint="A PR or screenshot, https:// only">
              <Input value={evidence} onChange={(e) => setEvidence(e.target.value)} inputMode="url" maxLength={500} />
            </Field>
          </div>
          <Field label="Their reaction" optional error={errors.partner_reaction}>
            <Textarea value={reaction} onChange={(e) => setReaction(e.target.value)} maxLength={1000} className="min-h-16" />
          </Field>
          {problem && (
            <p role="alert" className="rounded-md bg-destructive-soft px-3 py-2.5 text-sm text-destructive-text">
              {problem}
            </p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={onClose} disabled={saving}>
              Back
            </Button>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 aria-hidden className="animate-spin" />} Save decision
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

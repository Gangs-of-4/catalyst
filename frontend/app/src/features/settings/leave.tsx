import { CalendarOff, Loader2, X } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";

import { Field } from "@/components/field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";

import { agentToast } from "./agent-toast";
import { addBlock, type Block, removeBlock } from "./api";

/** Today in India as YYYY-MM-DD, for the date picker's minimum (the backend refuses past dates). */
const todayIst = () => new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });

type Props = {
  blocks: Block[];
  onBlocks: (b: Block[]) => void;
  /** Doctors as saved (with ids): a doctor added but not saved yet can't take leave. */
  doctors: { id: string; name: string }[];
  onAuthError: (err: unknown) => boolean;
};

/**
 * Leave days and holidays (bookings template). Each add or remove saves straight away and
 * re-syncs the assistant, so callers stop being offered those days; it isn't part of the page's
 * Save bar.
 */
export function LeaveSection({ blocks, onBlocks, doctors, onAuthError }: Props) {
  const [date, setDate] = React.useState("");
  const [who, setWho] = React.useState(""); // "" = the whole clinic
  const [error, setError] = React.useState<string | null>(null);
  const [adding, setAdding] = React.useState(false);
  const [removingId, setRemovingId] = React.useState<number | null>(null);

  async function onAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!date) {
      setError("Pick a date.");
      return;
    }
    setError(null);
    setAdding(true);
    try {
      const r = await addBlock(date, who || null);
      onBlocks(r.blocks);
      setDate("");
      agentToast(r.agent, r.note ? `Added. ${r.note}` : "Added.");
    } catch (err) {
      if (!onAuthError(err)) setError(err instanceof ApiError ? err.detail : "Couldn't add it. Please try again.");
    } finally {
      setAdding(false);
    }
  }

  async function onRemove(b: Block) {
    setRemovingId(b.id);
    try {
      const r = await removeBlock(b.id);
      onBlocks(r.blocks);
      agentToast(r.agent, "Removed. Those times are open again.");
    } catch (err) {
      if (onAuthError(err)) return;
      if (err instanceof ApiError && err.status === 404) onBlocks(blocks.filter((x) => x.id !== b.id));
      toast.error(err instanceof ApiError ? err.detail : "Couldn't remove it. Please try again.");
    } finally {
      setRemovingId(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {blocks.length === 0 ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <CalendarOff aria-hidden className="size-4" /> No leave or holidays coming up.
        </p>
      ) : (
        <ul aria-label="Upcoming leave and holidays" className="flex flex-col divide-y rounded-lg border">
          {blocks.map((b) => (
            <li key={b.id} className="flex min-h-12 items-center justify-between gap-3 px-3 py-2">
              <span className="text-sm">{b.label}</span>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Remove ${b.label}`}
                disabled={removingId === b.id}
                onClick={() => void onRemove(b)}
              >
                {removingId === b.id ? <Loader2 className="animate-spin" /> : <X />}
              </Button>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={onAdd} noValidate className="flex flex-col gap-3 rounded-lg bg-surface-soft p-3 sm:flex-row sm:items-end">
        <Field label="Date" error={error ?? undefined} className="sm:w-44">
          <Input type="date" value={date} min={todayIst()} onChange={(e) => setDate(e.target.value)} />
        </Field>
        <Field label="Who" className="sm:flex-1">
          <select value={who} onChange={(e) => setWho(e.target.value)} className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm">
            <option value="">Whole clinic (holiday)</option>
            {doctors.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} (leave)
              </option>
            ))}
          </select>
        </Field>
        <Button type="submit" variant="outline" disabled={adding} className="sm:mb-px">
          {adding && <Loader2 aria-hidden className="animate-spin" />} Add
        </Button>
      </form>
      <p className="text-[13px] text-muted-foreground">
        Saves straight away. Bookings already on that day stay; the desk shows them so they can be moved.
      </p>
    </div>
  );
}

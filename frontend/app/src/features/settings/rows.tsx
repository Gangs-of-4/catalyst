import { Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";

function RowError({ id, error }: { id: string; error?: string }) {
  if (!error) return null;
  return (
    <p id={id} role="alert" className="text-[13px] font-medium text-destructive">
      {error}
    </p>
  );
}

/**
 * Editable list of one-line values (doctors, red-flag words, WhatsApp numbers), edited by row index
 * so a row keeps whatever else it carries (a doctor's id). `errorKey(i)` names each row's error.
 */
export function TextRows({
  values,
  onChange,
  onRemove,
  onAdd,
  label,
  addLabel,
  errors,
  errorKey,
  max = 20,
  inputMode,
  placeholder,
}: {
  values: string[];
  /** Row i now reads `value`. */
  onChange: (i: number, value: string) => void;
  onRemove: (i: number) => void;
  onAdd: () => void;
  /** Accessible name of row i ("WhatsApp number 1"). */
  label: (i: number) => string;
  addLabel: string;
  errors: Record<string, string>;
  errorKey: (i: number) => string;
  max?: number;
  inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
  placeholder?: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      {values.map((v, i) => {
        const err = errors[errorKey(i)];
        const errId = `${errorKey(i)}-error`;
        return (
          <div key={i} className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <Input
                value={v}
                onChange={(e) => onChange(i, e.target.value)}
                aria-label={label(i)}
                aria-invalid={err ? true : undefined}
                aria-describedby={err ? errId : undefined}
                inputMode={inputMode}
                placeholder={placeholder}
                autoComplete="off"
              />
              <Button variant="ghost" size="icon" aria-label={`Remove ${label(i).toLowerCase()}`} onClick={() => onRemove(i)}>
                <X />
              </Button>
            </div>
            <RowError id={errId} error={err} />
          </div>
        );
      })}
      {values.length < max && (
        <Button variant="ghost" size="sm" className="self-start px-2" onClick={onAdd}>
          <Plus /> {addLabel}
        </Button>
      )}
    </div>
  );
}

/** Editable list of two-part rows: a service and its fee, or a question and its answer. */
export function PairRows<T extends Record<string, string>>({
  values,
  onChange,
  keys,
  labels,
  addLabel,
  errors,
  errorPrefix,
  max = 20,
  multiline = false,
  empty,
}: {
  values: T[];
  onChange: (v: T[]) => void;
  keys: [keyof T & string, keyof T & string];
  /** Accessible names for row i's two inputs. */
  labels: (i: number) => [string, string];
  addLabel: string;
  errors: Record<string, string>;
  /** Errors are `${errorPrefix}.${i}.${key}`, as the API names them. */
  errorPrefix: string;
  max?: number;
  /** The second part is a longer answer (FAQs). */
  multiline?: boolean;
  empty: T;
}) {
  const [k1, k2] = keys;
  return (
    <div className="flex flex-col gap-3">
      {values.map((row, i) => {
        const [l1, l2] = labels(i);
        const e1 = errors[`${errorPrefix}.${i}.${k1}`];
        const e2 = errors[`${errorPrefix}.${i}.${k2}`];
        const set = (k: keyof T, v: string) => onChange(values.map((x, j) => (j === i ? { ...x, [k]: v } : x)));
        const second = {
          value: row[k2],
          "aria-label": l2,
          "aria-invalid": e2 ? true : undefined,
          "aria-describedby": e2 ? `${errorPrefix}-${i}-${k2}-error` : undefined,
        } as const;
        return (
          <div key={i} className={multiline ? "flex flex-col gap-2 rounded-lg border p-3" : "flex flex-col gap-1"}>
            <div className={multiline ? "flex items-start gap-2" : "flex items-center gap-2"}>
              <div className={multiline ? "flex min-w-0 flex-1 flex-col gap-2" : "grid min-w-0 flex-1 grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] gap-2"}>
                <Input
                  value={row[k1]}
                  onChange={(e) => set(k1, e.target.value)}
                  aria-label={l1}
                  aria-invalid={e1 ? true : undefined}
                  aria-describedby={e1 ? `${errorPrefix}-${i}-${k1}-error` : undefined}
                  autoComplete="off"
                />
                {multiline ? (
                  <Textarea {...second} onChange={(e) => set(k2, e.target.value)} className="min-h-16" />
                ) : (
                  <Input {...second} onChange={(e) => set(k2, e.target.value)} autoComplete="off" />
                )}
              </div>
              <Button variant="ghost" size="icon" aria-label={`Remove ${l1.toLowerCase()}`} onClick={() => onChange(values.filter((_, j) => j !== i))}>
                <X />
              </Button>
            </div>
            <RowError id={`${errorPrefix}-${i}-${k1}-error`} error={e1} />
            <RowError id={`${errorPrefix}-${i}-${k2}-error`} error={e2} />
          </div>
        );
      })}
      {values.length < max && (
        <Button variant="ghost" size="sm" className="self-start px-2" onClick={() => onChange([...values, { ...empty }])}>
          <Plus /> {addLabel}
        </Button>
      )}
    </div>
  );
}

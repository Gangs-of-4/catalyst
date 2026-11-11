import { Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import { type FieldErrors, type Hours, MAX_HOURS_ROWS } from "./model";

type HoursEditorProps = {
  value: Hours[];
  onChange: (hours: Hours[]) => void;
  errors: FieldErrors;
};

/** Opening-time rows ("10:00 to 14:00"), 1 to 4 of them, e.g. a morning and an evening session. */
export function HoursEditor({ value, onChange, errors }: HoursEditorProps) {
  const set = (i: number, patch: Partial<Hours>) =>
    onChange(value.map((h, j) => (j === i ? { ...h, ...patch } : h)));

  return (
    <div className="flex flex-col gap-2">
      {value.map((h, i) => {
        const error = errors[`business.hours.${i}`];
        const errorId = error ? `hours-${i}-error` : undefined;
        return (
          <div key={i} className="flex flex-col gap-1">
            <div className="flex items-center gap-1.5 sm:gap-2">
              <Input
                type="time"
                aria-label={`Session ${i + 1} opens at`}
                value={h.start}
                onChange={(e) => set(i, { start: e.target.value })}
                aria-invalid={error ? true : undefined}
                aria-describedby={errorId}
                className="min-w-0 flex-1 px-2.5 sm:max-w-36 sm:flex-none sm:px-3.5"
              />
              <span className="text-sm text-muted-foreground">to</span>
              <Input
                type="time"
                aria-label={`Session ${i + 1} closes at`}
                value={h.end}
                onChange={(e) => set(i, { end: e.target.value })}
                aria-invalid={error ? true : undefined}
                aria-describedby={errorId}
                className="min-w-0 flex-1 px-2.5 sm:max-w-36 sm:flex-none sm:px-3.5"
              />
              {value.length > 1 && (
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={`Remove session ${i + 1}`}
                  onClick={() => onChange(value.filter((_, j) => j !== i))}
                >
                  <X />
                </Button>
              )}
            </div>
            {error && (
              <p id={errorId} role="alert" className="text-[13px] font-medium text-destructive">
                {error}
              </p>
            )}
          </div>
        );
      })}
      {value.length < MAX_HOURS_ROWS && (
        <Button
          variant="ghost"
          size="sm"
          className="self-start px-2"
          onClick={() => onChange([...value, { start: "17:00", end: "20:00" }])}
        >
          <Plus /> Add another session
        </Button>
      )}
    </div>
  );
}

import { cn } from "@/lib/utils";

import { WEEKDAYS } from "./model";

const FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

type WeekdayPickerProps = {
  /** 0 = Monday … 6 = Sunday. */
  value: number[];
  onChange: (days: number[]) => void;
};

/** Toggle chips for the days the business is closed. */
export function WeekdayPicker({ value, onChange }: WeekdayPickerProps) {
  const toggle = (d: number) =>
    onChange(value.includes(d) ? value.filter((x) => x !== d) : [...value, d].sort((a, b) => a - b));
  return (
    <div className="flex flex-wrap gap-2">
      {WEEKDAYS.map((label, d) => {
        const on = value.includes(d);
        return (
          <button
            key={label}
            type="button"
            aria-pressed={on}
            aria-label={`Closed on ${FULL[d]}`}
            onClick={() => toggle(d)}
            className={cn(
              "h-10 min-w-12 rounded-md border px-3 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
              on
                ? "border-primary bg-primary text-primary-foreground"
                : "border-input bg-background text-foreground hover:bg-accent",
            )}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

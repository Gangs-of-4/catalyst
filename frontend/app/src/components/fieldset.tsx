import * as React from "react";

import { cn } from "@/lib/utils";

type FieldsetProps = {
  legend: React.ReactNode;
  hint?: React.ReactNode;
  /** One error for the whole group (e.g. "Add at least one doctor"). */
  error?: string;
  className?: string;
  children: React.ReactNode;
};

/** A labelled group of controls (radio cards, day chips, list rows) with one hint and one error. */
function Fieldset({ legend, hint, error, className, children }: FieldsetProps) {
  const id = React.useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  return (
    <fieldset
      aria-describedby={[hintId, errorId].filter(Boolean).join(" ") || undefined}
      aria-invalid={error ? true : undefined}
      className={cn("flex min-w-0 flex-col gap-2", className)}
    >
      <legend className="mb-0.5 text-sm font-medium text-foreground">{legend}</legend>
      {hint && (
        <p id={hintId} className="-mt-1 text-[13px] leading-snug text-muted-foreground">
          {hint}
        </p>
      )}
      {children}
      {error && (
        <p id={errorId} role="alert" className="text-[13px] font-medium leading-snug text-destructive">
          {error}
        </p>
      )}
    </fieldset>
  );
}

export { Fieldset };

import * as React from "react";

import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

type FieldProps = {
  /** Visible label. Every control has one (DESIGN.md §6). */
  label: React.ReactNode;
  /** Short help shown under the control. */
  hint?: React.ReactNode;
  /** Error for this field; show the API's `fields[name]` text as-is (contracts.md §6). */
  error?: string;
  /** Marks the label "Optional" instead of starring required fields. */
  optional?: boolean;
  className?: string;
  /** A single control element (Input, Textarea, select…). Field wires its id and aria props. */
  children: React.ReactElement<React.InputHTMLAttributes<HTMLElement>>;
};

/** Label + control + hint + error, with the aria wiring done once. */
function Field({ label, hint, error, optional, className, children }: FieldProps) {
  const autoId = React.useId();
  const id = children.props.id ?? autoId;
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [children.props["aria-describedby"], hintId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div data-slot="field" className={cn("flex flex-col gap-1.5", className)}>
      <Label htmlFor={id}>
        {label}
        {optional && <span className="ml-1.5 font-normal text-muted-foreground">Optional</span>}
      </Label>
      {React.cloneElement(children, {
        id,
        "aria-describedby": describedBy,
        "aria-invalid": error ? true : children.props["aria-invalid"],
      })}
      {hint && (
        <p id={hintId} className="text-[13px] leading-snug text-muted-foreground">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="text-[13px] font-medium leading-snug text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

export { Field };

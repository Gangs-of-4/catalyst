import { Package, Stethoscope, Store } from "lucide-react";

import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { cn } from "@/lib/utils";

import { hasModule, type Template } from "./model";

/** One line per module, written for the owner. Chosen by module, never by template name (ADR-0033). */
function describe(t: Template): string {
  if (hasModule(t, "bookings"))
    return `Callers book ${t.labels.booking?.toLowerCase() ?? "appointment"}s with your ${
      t.labels.resource_plural?.toLowerCase() ?? "team"
    }, even while you're busy.`;
  if (hasModule(t, "orders")) return "Shops place and check orders by phone, even at 9 pm.";
  return "Your calls answered politely, every time.";
}

function iconFor(t: Template) {
  if (hasModule(t, "bookings")) return Stethoscope;
  if (hasModule(t, "orders")) return Package;
  return Store;
}

type TemplatePickerProps = {
  templates: Template[];
  value: string;
  onChange: (template: string) => void;
  invalid?: boolean;
};

/** The template choice as large radio cards (pattern from 21st.dev "Icon Card Radio Group", restyled). */
export function TemplatePicker({ templates, value, onChange, invalid }: TemplatePickerProps) {
  return (
    <RadioGroup
      value={value}
      onValueChange={onChange}
      aria-label="Type of business"
      aria-invalid={invalid || undefined}
      className="grid-cols-1 sm:grid-cols-2"
    >
      {templates.map((t) => {
        const Icon = iconFor(t);
        const id = `template-${t.template}`;
        const selected = value === t.template;
        return (
          <label
            key={t.template}
            htmlFor={id}
            className={cn(
              "relative flex cursor-pointer flex-col gap-3 rounded-lg border bg-card p-4 pr-12 transition-colors hover:bg-surface-soft",
              selected ? "border-primary ring-1 ring-primary" : invalid ? "border-destructive" : "border-border",
            )}
          >
            <RadioGroupItem value={t.template} id={id} className="absolute right-4 top-4" />
            <span className="flex size-9 items-center justify-center rounded-md border bg-background">
              <Icon aria-hidden className="size-[18px]" />
            </span>
            <span className="flex flex-col gap-0.5">
              <span className="font-semibold">{t.label}</span>
              <span className="text-sm text-muted-foreground">{describe(t)}</span>
            </span>
          </label>
        );
      })}
    </RadioGroup>
  );
}

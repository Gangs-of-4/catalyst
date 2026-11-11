import * as React from "react";

import { cn } from "@/lib/utils";

const controlBase =
  "w-full min-w-0 rounded-md border border-input bg-background px-3.5 text-base text-foreground placeholder:text-muted-foreground transition-colors disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-ring aria-invalid:border-destructive aria-invalid:focus-visible:outline-destructive";

function Input({ className, type = "text", ...props }: React.ComponentProps<"input">) {
  return (
    <input
      data-slot="input"
      type={type}
      className={cn(controlBase, "h-10 py-2 file:border-0 file:bg-transparent file:text-sm", className)}
      {...props}
    />
  );
}

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(controlBase, "min-h-24 py-2.5 leading-normal", className)}
      {...props}
    />
  );
}

export { Input, Textarea };

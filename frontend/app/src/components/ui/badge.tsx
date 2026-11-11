import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex w-fit items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-[13px] font-medium [&_svg]:size-3.5",
  {
    variants: {
      variant: {
        neutral: "bg-muted text-foreground",
        live: "bg-live-soft text-live-text",
        success: "bg-success-soft text-success-text",
        destructive: "bg-destructive-soft text-destructive-text",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

function Badge({ className, variant, ...props }: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };

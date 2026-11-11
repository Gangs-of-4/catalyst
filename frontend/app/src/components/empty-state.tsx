import type { LucideIcon } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

type EmptyStateProps = {
  icon: LucideIcon;
  title: string;
  /** Why it's empty, in one line. */
  description?: React.ReactNode;
  /** The next action, usually one Button. */
  action?: React.ReactNode;
  className?: string;
};

function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      data-slot="empty-state"
      className={cn(
        "flex flex-col items-center gap-3 rounded-lg border border-dashed px-6 py-10 text-center",
        className,
      )}
    >
      <span className="flex size-11 items-center justify-center rounded-full bg-muted">
        <Icon aria-hidden className="size-5 text-foreground" />
      </span>
      <div className="flex max-w-sm flex-col gap-1">
        <p className="font-semibold">{title}</p>
        {description && <p className="text-sm text-muted-foreground">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export { EmptyState };

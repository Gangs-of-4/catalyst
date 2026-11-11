import { cn } from "@/lib/utils";

/** The Catalyst mark + wordmark. Brand is "Catalyst" only (DESIGN.md). */
function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-[17px] font-semibold tracking-tight", className)}>
      <svg aria-hidden viewBox="0 0 32 32" className="size-7">
        <rect width="32" height="32" rx="8" fill="var(--primary)" />
        <path
          d="M21.5 11.2A7 7 0 1 0 21.5 20.8"
          fill="none"
          stroke="var(--primary-foreground)"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <circle cx="22.5" cy="16" r="2" fill="var(--live)" />
      </svg>
      Catalyst
    </span>
  );
}

export { Logo };

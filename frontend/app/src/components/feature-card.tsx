import type { LucideIcon } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

export type Feature = {
  title: string;
  icon: LucideIcon;
  description: React.ReactNode;
};

/**
 * One cell of a feature grid: icon, title, short description, with a faint grid pattern behind.
 * Adapted from 21st.dev "Grid Feature Cards" (efferd): no animation library, a pattern that stays
 * put between renders, and text sized for phones (DESIGN.md).
 */
export function FeatureCard({ feature, className, ...props }: React.ComponentProps<"div"> & { feature: Feature }) {
  const [squares] = React.useState(randomSquares);
  const Icon = feature.icon;
  return (
    <div className={cn("relative overflow-hidden p-6", className)} {...props}>
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-0 -ml-20 -mt-2 h-full w-full [mask-image:linear-gradient(white,transparent)]"
      >
        <div className="absolute inset-0 bg-gradient-to-r from-foreground/5 to-foreground/[0.01] [mask-image:radial-gradient(farthest-side_at_top,white,transparent)]">
          <GridPattern
            width={20}
            height={20}
            x="-12"
            y="4"
            squares={squares}
            className="absolute inset-0 h-full w-full fill-foreground/5 stroke-foreground/20 mix-blend-overlay"
          />
        </div>
      </div>
      <Icon aria-hidden className="relative size-6 text-foreground" strokeWidth={1.5} />
      <h3 className="relative mt-6 text-base font-semibold">{feature.title}</h3>
      <p className="relative mt-1.5 text-sm text-muted-foreground">{feature.description}</p>
    </div>
  );
}

function GridPattern({
  width,
  height,
  x,
  y,
  squares,
  ...props
}: React.ComponentProps<"svg"> & { width: number; height: number; x: string; y: string; squares: number[][] }) {
  const id = React.useId();
  return (
    <svg aria-hidden {...props}>
      <defs>
        <pattern id={id} width={width} height={height} patternUnits="userSpaceOnUse" x={x} y={y}>
          <path d={`M.5 ${height}V.5H${width}`} fill="none" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" strokeWidth={0} fill={`url(#${id})`} />
      <svg x={x} y={y} className="overflow-visible">
        {squares.map(([sx, sy], i) => (
          <rect key={i} strokeWidth="0" width={width + 1} height={height + 1} x={sx! * width} y={sy! * height} />
        ))}
      </svg>
    </svg>
  );
}

function randomSquares(): number[][] {
  return Array.from({ length: 5 }, () => [Math.floor(Math.random() * 4) + 7, Math.floor(Math.random() * 6) + 1]);
}

/** A dashed grid of feature cells: 1 column on phones, more on wider screens. */
export function FeatureGrid({ features, className }: { features: Feature[]; className?: string }) {
  return (
    <div className={cn("grid grid-cols-1 divide-y divide-dashed border border-dashed sm:grid-cols-3 sm:divide-x sm:divide-y-0", className)}>
      {features.map((f) => (
        <FeatureCard key={f.title} feature={f} />
      ))}
    </div>
  );
}

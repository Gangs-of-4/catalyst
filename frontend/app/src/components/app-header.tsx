import * as React from "react";
import { Logo } from "@/components/logo";
import { cn } from "@/lib/utils";

type AppHeaderProps = {
  /** Right-hand side: nav links, account menu, the main action. */
  children?: React.ReactNode;
  className?: string;
};

function AppHeader({ children, className }: AppHeaderProps) {
  return (
    <header className={cn("sticky top-0 z-40 border-b bg-background/95 backdrop-blur-sm", className)}>
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        {/* A full page load on purpose: during M8, "/" may still be an old static page. */}
        <a href="/" className="rounded-md" aria-label="Catalyst home">
          <Logo />
        </a>
        {children && <div className="flex items-center gap-2">{children}</div>}
      </div>
    </header>
  );
}

export { AppHeader };

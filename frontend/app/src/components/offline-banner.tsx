import { WifiOff } from "lucide-react";

import { useOnline } from "@/hooks/use-online";

/** A full-width notice while the browser is offline. Renders nothing when online. */
function OfflineBanner() {
  const online = useOnline();
  if (online) return null;
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center justify-center gap-2 bg-live-soft px-4 py-2.5 text-center text-sm font-medium text-live-text"
    >
      <WifiOff aria-hidden className="size-4 shrink-0" />
      You're offline. Changes won't save until you're back.
    </div>
  );
}

export { OfflineBanner };

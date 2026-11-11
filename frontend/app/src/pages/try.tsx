import { AlertCircle, Compass, MicOff, RotateCw, Sparkles } from "lucide-react";
import * as React from "react";
import { Navigate, useParams } from "react-router";

import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { boardIds, getBoard, getTryInfo, type Board, type TryInfo } from "@/features/try/api";
import { CallPanel } from "@/features/try/call-panel";
import { LiveBoard } from "@/features/try/live-board";
import { useCall } from "@/features/try/use-call";
import { usePolling } from "@/hooks/use-polling";
import { ApiError } from "@/lib/api";
import { NotFoundPage } from "@/pages/not-found";

const POLL_LIVE_MS = 3000;
const POLL_IDLE_MS = 10000;

/**
 * The public test page for one business (phase2-plan §6 "Test page", contracts §6 /api/try).
 * Talk to the front desk on the left; watch the register or order board update on the right.
 */
export function TryPage() {
  const { publicId = "" } = useParams();
  const [info, setInfo] = React.useState<TryInfo | null>(null);
  const [loadError, setLoadError] = React.useState<{ notFound: boolean; message: string } | null>(null);
  const [attempt, setAttempt] = React.useState(0);
  const [board, setBoard] = React.useState<Board | null>(null);
  const [boardError, setBoardError] = React.useState(false);
  const [fresh, setFresh] = React.useState<Set<number>>(() => new Set());
  const seen = React.useRef<Set<number> | null>(null);

  React.useEffect(() => {
    const ctrl = new AbortController();
    getTryInfo(publicId, ctrl.signal)
      .then((i) => {
        setInfo(i);
        document.title = `Talk to ${i.name} · Catalyst`;
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setLoadError({
          notFound: err instanceof ApiError && err.status === 404,
          message: err instanceof ApiError ? err.detail : "This page didn't load.",
        });
      });
    return () => ctrl.abort();
  }, [publicId, attempt]);

  const refreshBoard = React.useCallback(
    async (signal?: AbortSignal) => {
      try {
        const b = await getBoard(publicId, signal);
        const ids = boardIds(b);
        if (seen.current) {
          const added = [...ids].filter((id) => !seen.current!.has(id));
          if (added.length) setFresh((f) => new Set([...f, ...added]));
        }
        seen.current = ids;
        setBoard(b);
        setBoardError(false);
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setBoardError(true);
      }
    },
    [publicId],
  );

  const call = useCall(info, () => void refreshBoard());
  const live = call.state !== "idle";
  usePolling(refreshBoard, live ? POLL_LIVE_MS : POLL_IDLE_MS, !!info);

  if (loadError) {
    return (
      <>
        <AppHeader />
        <main className="mx-auto max-w-2xl px-4 py-12 sm:px-6">
          {loadError.notFound ? (
            <EmptyState
              icon={Compass}
              title="This front desk doesn't exist"
              description="Check the link. It may be old or mistyped."
            />
          ) : (
            <EmptyState
              icon={AlertCircle}
              title="This page didn't load"
              description={loadError.message}
              action={
                <Button
                  variant="outline"
                  onClick={() => {
                    setLoadError(null);
                    setAttempt((n) => n + 1);
                  }}
                >
                  <RotateCw /> Try again
                </Button>
              }
            />
          )}
        </main>
      </>
    );
  }

  if (!info) {
    return (
      <>
        <AppHeader />
        <main className="mx-auto grid max-w-6xl gap-6 px-4 py-10 sm:px-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]" role="status" aria-label="Loading">
          <div className="h-96 animate-pulse rounded-lg bg-muted" />
          <div className="h-96 animate-pulse rounded-lg bg-muted" />
        </main>
      </>
    );
  }

  const tenant = info.labels.tenant ?? "Business";
  const isOrders = info.modules.includes("orders");
  const boardTitle = isOrders ? "Today's orders" : `${info.labels.booking ?? "Appointment"} register`;

  return (
    <>
      <AppHeader />
      <main className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-8 sm:px-6 sm:py-12">
        <div className="flex flex-col gap-1">
          <p className="text-[13px] font-medium text-muted-foreground">
            {tenant}
            {info.city ? ` · ${info.city}` : ""} · Test page
          </p>
          <h1 className="text-[28px] font-semibold leading-tight tracking-tight">{info.name}</h1>
        </div>

        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
          <Card>
            <CardContent className="flex flex-col gap-6">
              {info.voice ? (
                <CallPanel
                  state={call.state}
                  speaking={call.speaking}
                  volume={call.volume}
                  seconds={call.seconds}
                  maxSeconds={call.maxSeconds}
                  lines={call.lines}
                  problem={call.problem}
                  onStart={() => void call.start()}
                  onStop={call.stop}
                />
              ) : (
                <EmptyState
                  icon={MicOff}
                  title="The voice agent isn't switched on yet"
                  description="Your details are saved. Once the agent is switched on for this business, you can talk to it here."
                />
              )}

              {info.try_saying.length > 0 && (
                <div className="flex flex-col gap-2 border-t pt-5">
                  <p className="flex items-center gap-1.5 text-sm font-semibold">
                    <Sparkles aria-hidden className="size-4" /> Try saying
                  </p>
                  <ul className="flex flex-wrap gap-2">
                    {info.try_saying.map((line) => (
                      <li key={line} className="rounded-full bg-muted px-3 py-1.5 text-sm">
                        &ldquo;{line}&rdquo;
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
              <div className="flex flex-col gap-1.5">
                <CardTitle>{boardTitle}</CardTitle>
                <CardDescription>Updates while you talk. Names are shortened; phone numbers are never shown.</CardDescription>
              </div>
              {live && <Badge variant="live">Live</Badge>}
            </CardHeader>
            <CardContent>
              {board ? (
                <LiveBoard board={board} fresh={fresh} resourceLabel={info.labels.resource ?? "Doctor"} />
              ) : boardError ? (
                <EmptyState
                  icon={AlertCircle}
                  title="The board didn't load"
                  description="It tries again in a few seconds."
                />
              ) : (
                <div className="h-48 animate-pulse rounded-md bg-muted" role="status" aria-label="Loading the board" />
              )}
              {board && boardError && (
                <p role="status" className="mt-3 text-[13px] text-muted-foreground">
                  Couldn&apos;t refresh just now. Showing the last update.
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </>
  );
}

/** /demo/clinic and /demo/wholesale open the demo businesses' test pages (phase2-plan §6). */
export function DemoRedirect() {
  const { template = "" } = useParams();
  if (!/^[a-z]+$/.test(template)) return <NotFoundPage />;
  return <Navigate to={`/b/demo-${template}/try`} replace />;
}

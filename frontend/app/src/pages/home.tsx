import { AlertCircle, Building2, Loader2, LogOut, Phone, RotateCw, UserRound } from "lucide-react";
import * as React from "react";
import { Link, useNavigate } from "react-router";
import { toast } from "sonner";

import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { getMe, logout, type Me } from "@/lib/session";

/**
 * The owner's signed-in home (M8 task 3). Small on purpose: later tasks add the desk, settings and
 * test page here as they're built. Logged-out visitors are sent to /login and come back after.
 */
export function HomePage() {
  const navigate = useNavigate();
  const [me, setMe] = React.useState<Me | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [attempt, setAttempt] = React.useState(0);
  const [leaving, setLeaving] = React.useState(false);

  React.useEffect(() => {
    const ctrl = new AbortController();
    getMe(ctrl.signal)
      .then((m) => {
        setMe(m);
        setError(null);
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (err instanceof ApiError && err.status === 401) {
          navigate("/login?next=/home", { replace: true });
          return;
        }
        setError(err instanceof ApiError ? err.detail : "We couldn't load your account.");
      });
    return () => ctrl.abort();
  }, [attempt, navigate]);

  async function onLogout() {
    setLeaving(true);
    try {
      await logout();
    } catch {
      // The cookie may already be gone; either way the owner wants to be on the login page.
    }
    toast.success("You're logged out.");
    navigate("/login", { replace: true });
  }

  const header = (
    <AppHeader>
      {me && (
        <Button variant="ghost" size="sm" onClick={onLogout} disabled={leaving}>
          {leaving ? <Loader2 aria-hidden className="animate-spin" /> : <LogOut aria-hidden />} Log out
        </Button>
      )}
    </AppHeader>
  );

  if (error) {
    return (
      <>
        {header}
        <main className="mx-auto max-w-2xl px-4 py-12 sm:px-6">
          <EmptyState
            icon={AlertCircle}
            title="Your account didn't load"
            description={error}
            action={
              <Button variant="outline" onClick={() => setAttempt((n) => n + 1)}>
                <RotateCw /> Try again
              </Button>
            }
          />
        </main>
      </>
    );
  }

  if (!me) {
    return (
      <>
        {header}
        <main className="mx-auto flex max-w-2xl flex-col gap-4 px-4 py-12 sm:px-6" role="status" aria-label="Loading">
          <div className="h-9 w-2/3 animate-pulse rounded-md bg-muted" />
          <div className="h-40 animate-pulse rounded-lg bg-muted" />
        </main>
      </>
    );
  }

  const tenant = me.business.labels.tenant ?? "Business";
  return (
    <>
      {header}
      <main className="mx-auto flex max-w-2xl flex-col gap-6 px-4 py-10 sm:px-6 sm:py-14">
        <div className="flex flex-col gap-1">
          <p className="text-sm text-muted-foreground">Hello, {me.user.name.split(" ")[0]}</p>
          <h1 className="text-[28px] font-semibold leading-tight tracking-tight">{me.business.name}</h1>
        </div>

        <Card className="gap-4 border-primary/15">
          <CardHeader className="flex-row items-center gap-3">
            <span className="flex size-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <Phone aria-hidden className="size-[18px]" />
            </span>
            <CardTitle className="text-base">Talk to your front desk</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm text-body">
              Call it the way a {(me.business.labels.contact ?? "customer").toLowerCase()} would, and watch the
              booking or order appear as you talk.
            </p>
            <Button asChild size="lg" className="w-full sm:w-fit">
              <Link to={`/b/${encodeURIComponent(me.business.public_id)}/try`}>Open your test page</Link>
            </Button>
          </CardContent>
        </Card>

        <div className="grid gap-4 sm:grid-cols-2">
          <Card className="gap-4">
            <CardHeader className="flex-row items-center gap-3">
              <span className="flex size-9 items-center justify-center rounded-md bg-muted">
                <Building2 aria-hidden className="size-[18px]" />
              </span>
              <CardTitle className="text-base">Your {tenant.toLowerCase()}</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="flex flex-col gap-2 text-sm">
                <div>
                  <dt className="text-muted-foreground">Name</dt>
                  <dd className="font-medium">{me.business.name}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Type</dt>
                  <dd className="font-medium">{tenant}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>

          <Card className="gap-4">
            <CardHeader className="flex-row items-center gap-3">
              <span className="flex size-9 items-center justify-center rounded-md bg-muted">
                <UserRound aria-hidden className="size-[18px]" />
              </span>
              <CardTitle className="text-base">Your account</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="flex flex-col gap-2 text-sm">
                <div>
                  <dt className="text-muted-foreground">Name</dt>
                  <dd className="font-medium">{me.user.name}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Email</dt>
                  <dd className="break-all font-medium">{me.user.email}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        </div>
      </main>
    </>
  );
}

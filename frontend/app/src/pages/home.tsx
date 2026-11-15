import { AlertCircle, Building2, CalendarDays, Loader2, LogOut, Phone, RotateCw, Settings, UserRound } from "lucide-react";
import * as React from "react";
import { Link, useNavigate } from "react-router";
import { toast } from "sonner";

import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { Field } from "@/components/field";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { FeedbackButton } from "@/features/feedback/feedback-button";
import { useActivityPing } from "@/hooks/use-activity-ping";
import { ApiError } from "@/lib/api";
import { getMe, logout, updateProfile, type Me } from "@/lib/session";

function EditAccountDialog({
  open,
  onOpenChange,
  currentName,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentName: string;
  onSaved: (newName: string) => void;
}) {
  const [name, setName] = React.useState(currentName);
  const [currentPassword, setCurrentPassword] = React.useState("");
  const [newPassword, setNewPassword] = React.useState("");
  const [confirmPassword, setConfirmPassword] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [errors, setErrors] = React.useState<Record<string, string>>({});
  const [problem, setProblem] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setName(currentName);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setErrors({});
      setProblem(null);
    }
  }, [open, currentName]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErrors({});
    setProblem(null);

    const newErrors: Record<string, string> = {};
    if (!name.trim()) {
      newErrors.name = "Enter your name.";
    }
    if (newPassword || currentPassword) {
      if (!currentPassword) {
        newErrors.currentPassword = "Enter your current password.";
      }
      if (newPassword.length < 8) {
        newErrors.newPassword = "Password must be at least 8 characters.";
      }
      if (newPassword !== confirmPassword) {
        newErrors.confirmPassword = "Passwords do not match.";
      }
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setSaving(true);
    try {
      const payload: { name?: string; current_password?: string; new_password?: string } = {};
      if (name.trim() !== currentName) {
        payload.name = name.trim();
      }
      if (newPassword) {
        payload.current_password = currentPassword;
        payload.new_password = newPassword;
      }
      if (Object.keys(payload).length === 0) {
        onOpenChange(false);
        return;
      }
      const res = await updateProfile(payload);
      toast.success("Account updated.");
      onSaved(res.user.name);
      onOpenChange(false);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.fields) {
          setErrors({
            ...(err.fields.name ? { name: err.fields.name } : {}),
            ...(err.fields.current_password ? { currentPassword: err.fields.current_password } : {}),
            ...(err.fields.new_password ? { newPassword: err.fields.new_password } : {}),
          });
        }
        setProblem(err.detail);
      } else {
        setProblem("Could not update account.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit account</DialogTitle>
          <DialogDescription>Update your display name or change your password.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 pt-2">
          {problem && (
            <div role="alert" className="rounded-md bg-destructive-soft p-3 text-sm text-destructive-text">
              {problem}
            </div>
          )}
          <Field label="Your name" error={errors.name}>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={80}
              autoComplete="name"
              disabled={saving}
            />
          </Field>

          <div className="flex flex-col gap-3 rounded-lg border bg-muted/30 p-3.5">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Change password (optional)</p>
            <Field label="Current password" error={errors.currentPassword}>
              <Input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                autoComplete="current-password"
                disabled={saving}
              />
            </Field>
            <Field label="New password" error={errors.newPassword} hint="At least 8 characters">
              <Input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
                disabled={saving}
              />
            </Field>
            <Field label="Confirm new password" error={errors.confirmPassword}>
              <Input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
                disabled={saving}
              />
            </Field>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 aria-hidden className="mr-2 size-4 animate-spin" />} Save changes
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/**
 * The owner's signed-in home (M8 task 3). Small on purpose: later tasks add the desk, settings and
 * test page here as they're built. Logged-out visitors are sent to /login and come back after.
 */
export function HomePage() {
  const navigate = useNavigate();
  useActivityPing(); // time in the app, for the team's dashboard (issue #56)
  const [me, setMe] = React.useState<Me | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [attempt, setAttempt] = React.useState(0);
  const [leaving, setLeaving] = React.useState(false);
  const [editOpen, setEditOpen] = React.useState(false);

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
      {me && <FeedbackButton defaultName={me.user.name} />}
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

        <Card className="gap-4">
          <CardHeader className="flex-row items-center gap-3">
            <span className="flex size-9 items-center justify-center rounded-md bg-muted">
              <CalendarDays aria-hidden className="size-[18px]" />
            </span>
            <CardTitle className="text-base">Your front desk</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm text-body">
              Today&apos;s {(me.business.labels.booking ?? "booking").toLowerCase()}s, walk-ins, callbacks and the calls
              your front desk took.
            </p>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button asChild variant="outline" size="lg" className="w-full sm:w-fit">
                <Link to="/desk">Open the desk</Link>
              </Button>
              <Button asChild variant="ghost" size="lg" className="w-full sm:w-fit">
                <Link to="/settings">
                  <Settings aria-hidden /> Settings
                </Link>
              </Button>
            </div>
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
            <CardHeader className="flex-row items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <span className="flex size-9 items-center justify-center rounded-md bg-muted">
                  <UserRound aria-hidden className="size-[18px]" />
                </span>
                <CardTitle className="text-base">Your account</CardTitle>
              </div>
              <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
                Edit
              </Button>
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

      <EditAccountDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        currentName={me.user.name}
        onSaved={(newName) => {
          setMe((prev) => (prev ? { ...prev, user: { ...prev.user, name: newName } } : prev));
        }}
      />
    </>
  );
}

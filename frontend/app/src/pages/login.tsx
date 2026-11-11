import { AlertCircle, Loader2 } from "lucide-react";
import * as React from "react";
import { useNavigate, useSearchParams } from "react-router";

import { AppHeader } from "@/components/app-header";
import { Field } from "@/components/field";
import { PasswordInput } from "@/components/password-input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { getMe, login, safeNext } from "@/lib/session";

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/** Owner login (contracts.md §6 `POST /api/login`). Wrong email and wrong password look the same. */
export function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [errors, setErrors] = React.useState<{ email?: string; password?: string }>({});
  const [formError, setFormError] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState(false);
  const emailRef = React.useRef<HTMLInputElement>(null);

  // Already logged in? Go straight on.
  React.useEffect(() => {
    const ctrl = new AbortController();
    getMe(ctrl.signal)
      .then(() => navigate(next, { replace: true }))
      .catch(() => {});
    return () => ctrl.abort();
  }, [navigate, next]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    const found: typeof errors = {};
    if (!EMAIL.test(email.trim())) found.email = "Enter an email like name@example.com.";
    if (!password) found.password = "Please fill in your password.";
    setErrors(found);
    if (found.email || found.password) {
      setFormError(null);
      (found.email ? emailRef.current : document.getElementById("login-password"))?.focus();
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      await login(email, password);
      navigate(next, { replace: true });
    } catch (err) {
      // The server's sentence says what to do: wrong details, or locked for 15 minutes.
      setFormError(err instanceof ApiError ? err.detail : "Something went wrong. Please try again.");
      if (err instanceof ApiError && err.code === "UNAUTHENTICATED") setPassword("");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <AppHeader>
        <span className="hidden text-sm text-muted-foreground sm:inline">New to Catalyst?</span>
        <Button asChild variant="outline" size="sm">
          <a href="/signup">Set up your front desk</a>
        </Button>
      </AppHeader>
      <main className="mx-auto max-w-md px-4 py-12 sm:px-6 sm:py-16">
        <Card>
          <CardHeader>
            <CardTitle className="text-[28px] font-semibold leading-tight tracking-tight">Log in</CardTitle>
            <CardDescription className="text-base">To your business&apos;s front desk.</CardDescription>
          </CardHeader>
          <CardContent>
            <form noValidate onSubmit={onSubmit} className="flex flex-col gap-5" aria-busy={submitting}>
              <Field label="Email" error={errors.email}>
                <Input
                  ref={emailRef}
                  type="email"
                  inputMode="email"
                  autoComplete="email"
                  autoFocus
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setErrors((x) => ({ ...x, email: undefined }));
                  }}
                />
              </Field>
              <Field label="Password" error={errors.password}>
                <PasswordInput
                  id="login-password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    setErrors((x) => ({ ...x, password: undefined }));
                  }}
                />
              </Field>

              {formError && (
                <div
                  role="alert"
                  className="flex items-start gap-2.5 rounded-md bg-destructive-soft px-4 py-3 text-sm text-destructive-text"
                >
                  <AlertCircle aria-hidden className="mt-0.5 size-4 shrink-0" />
                  <p>{formError}</p>
                </div>
              )}

              <Button type="submit" size="lg" disabled={submitting} className="w-full">
                {submitting ? (
                  <>
                    <Loader2 aria-hidden className="animate-spin" /> Logging in…
                  </>
                ) : (
                  "Log in"
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
        <p className="mt-6 text-center text-sm text-muted-foreground">
          New here?{" "}
          <a href="/signup" className="font-medium text-foreground underline underline-offset-4">
            Set up your front desk
          </a>{" "}
          in about two minutes.
        </p>
      </main>
    </>
  );
}

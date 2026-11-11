import { AlertCircle, Loader2, Plus, RotateCw, X } from "lucide-react";
import * as React from "react";
import { useSearchParams } from "react-router";

import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { Field } from "@/components/field";
import { Fieldset } from "@/components/fieldset";
import { PasswordInput } from "@/components/password-input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { CONSENT_TEXT } from "@/features/signup/consent";
import { HoursEditor } from "@/features/signup/hours-editor";
import {
  type FieldErrors,
  hasModule,
  initialForm,
  MAX_DOCTORS,
  MAX_INSTRUCTIONS,
  remapErrors,
  SLOT_CHOICES,
  type SignupForm,
  type SignupResponse,
  switchTemplate,
  type Template,
  toPayload,
  validate,
} from "@/features/signup/model";
import { SignupSuccess } from "@/features/signup/success";
import { TemplatePicker } from "@/features/signup/template-picker";
import { WeekdayPicker } from "@/features/signup/weekday-picker";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

const selectClass =
  "h-10 w-full max-w-48 rounded-md border border-input bg-background px-3 text-base text-foreground focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-ring";

function Section({
  step,
  title,
  description,
  children,
}: {
  step: number;
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  const id = `section-${step}`;
  return (
    <Card aria-labelledby={id} role="group">
      <CardHeader>
        <p className="text-[13px] font-medium text-muted-foreground">Step {step} of 3</p>
        <CardTitle id={id}>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="flex flex-col gap-5">{children}</CardContent>
    </Card>
  );
}

/** Focus the first invalid control so keyboard and screen-reader users land on the problem. */
function focusFirstError(form: HTMLFormElement | null) {
  requestAnimationFrame(() => {
    const el = form?.querySelector<HTMLElement>('[aria-invalid="true"]');
    if (!el) return;
    const target = el.matches("input, textarea, select, button")
      ? el
      : el.querySelector<HTMLElement>("input, textarea, select, button");
    (target ?? el).focus({ preventScroll: true });
    (target ?? el).scrollIntoView({ block: "center", behavior: "smooth" });
  });
}

/**
 * Self-serve signup: an account and a business in one step (phase2-plan §6 "Onboarding",
 * contracts.md §6 `POST /api/signup`). Three short sections, then a success screen.
 */
export function SignupPage() {
  const [params] = useSearchParams();
  const [templates, setTemplates] = React.useState<Template[] | null>(null);
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [loadAttempt, setLoadAttempt] = React.useState(0);
  const [form, setForm] = React.useState<SignupForm>(() => initialForm());
  const [errors, setErrors] = React.useState<FieldErrors>({});
  const [formError, setFormError] = React.useState<{ code: string; detail: string } | null>(null);
  const [submitting, setSubmitting] = React.useState(false);
  const [optionalOpen, setOptionalOpen] = React.useState(false);
  const [done, setDone] = React.useState<SignupResponse | null>(null);
  const formRef = React.useRef<HTMLFormElement>(null);

  // Load the templates (labels, modules and form defaults) once, with a retry on failure.
  React.useEffect(() => {
    const ctrl = new AbortController();
    api<{ templates: Template[] }>("/api/templates", { signal: ctrl.signal })
      .then(({ templates: list }) => {
        setTemplates(list);
        setLoadError(null);
        const wanted = list.find((t) => t.template === params.get("template")) ?? list[0];
        if (wanted) setForm((f) => (f.business.template ? f : switchTemplate(f, wanted)));
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setLoadError(err instanceof ApiError ? err.detail : "We couldn't load the signup form.");
      });
    return () => ctrl.abort();
  }, [loadAttempt, params]);

  const template = templates?.find((t) => t.template === form.business.template);
  const labels = template?.labels ?? {};
  const resource = labels.resource ?? "Doctor";
  const resourcePlural = labels.resource_plural ?? "Doctors";
  const bookingLabel = labels.booking ?? "Appointment";

  /** Apply a change and clear the errors it fixes (exact key, or every key under `clearPrefix`). */
  const edit = (clear: string | string[], change: (f: SignupForm) => SignupForm) => {
    setForm(change);
    const keys = Array.isArray(clear) ? clear : [clear];
    setErrors((prev) => {
      const next = Object.fromEntries(
        Object.entries(prev).filter(([k]) => !keys.some((c) => k === c || k.startsWith(`${c}.`))),
      );
      return Object.keys(next).length === Object.keys(prev).length ? prev : next;
    });
  };
  const setUser = (key: keyof SignupForm["user"], value: string) =>
    edit(`user.${key}`, (f) => ({ ...f, user: { ...f.user, [key]: value } }));
  const setBusiness = <K extends keyof SignupForm["business"]>(key: K, value: SignupForm["business"][K]) =>
    edit(`business.${key}`, (f) => ({ ...f, business: { ...f.business, [key]: value } }));

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    // The button is never disabled without a reason; if the templates didn't load, say so here.
    if (!templates) {
      setFormError(
        loadError
          ? {
              code: "NOT_LOADED",
              detail:
                "The form didn't finish loading, so it can't be sent yet. Press \"Try again\" under \"What kind of business is it?\".",
            }
          : { code: "LOADING", detail: "The form is still loading. Wait a moment, then press the button again." },
      );
      document.getElementById("templates-retry")?.focus();
      return;
    }
    const found = validate(form, template);
    if (found["faqs"] || Object.keys(found).some((k) => k.startsWith("faqs.") || k === "instructions"))
      setOptionalOpen(true);
    if (Object.keys(found).length || !template) {
      setErrors(found);
      setFormError({ code: "VALIDATION", detail: "Please fix the highlighted fields." });
      focusFirstError(formRef.current);
      return;
    }
    setSubmitting(true);
    setFormError(null);
    const { body, rowMaps } = toPayload(form, template);
    try {
      const res = await api<SignupResponse>("/api/signup", { method: "POST", body });
      setDone(res);
      window.scrollTo({ top: 0 });
    } catch (err) {
      const apiErr =
        err instanceof ApiError
          ? err
          : new ApiError(0, { code: "INTERNAL", detail: "Something went wrong. Please try again." });
      const fields = remapErrors(apiErr.fields, rowMaps);
      if (Object.keys(fields).some((k) => k.startsWith("faqs") || k === "instructions")) setOptionalOpen(true);
      setErrors(fields);
      setFormError({ code: apiErr.code, detail: apiErr.detail });
      focusFirstError(formRef.current);
    } finally {
      setSubmitting(false);
    }
  }

  const header = (
    <AppHeader>
      <span className="hidden text-sm text-muted-foreground sm:inline">Already have an account?</span>
      <Button asChild variant="outline" size="sm">
        <a href="/login">Log in</a>
      </Button>
    </AppHeader>
  );

  if (done && template) {
    return (
      <>
        {header}
        <main className="mx-auto max-w-2xl px-4 py-10 sm:px-6 sm:py-14">
          <SignupSuccess
            businessName={form.business.name.trim()}
            publicId={done.public_id}
            template={template}
            agent={done.agent}
          />
        </main>
      </>
    );
  }

  const optionalErrors = Object.keys(errors).some((k) => k.startsWith("faqs") || k === "instructions");

  return (
    <>
      {header}
      <main className="mx-auto flex max-w-2xl flex-col gap-8 px-4 py-10 sm:px-6 sm:py-14">
        <div className="flex flex-col gap-2">
          <h1 className="text-[28px] font-semibold leading-tight tracking-tight">Set up your front desk</h1>
          <p className="text-body">
            About two minutes. Your agent starts with these details, and you can change any of them later.
          </p>
        </div>

        <form ref={formRef} noValidate onSubmit={onSubmit} className="flex flex-col gap-6" aria-busy={submitting}>
          <Section step={1} title="You" description="You'll log in with this email.">
            <Field label="Your name" error={errors["user.name"]}>
              <Input autoComplete="name" value={form.user.name} onChange={(e) => setUser("name", e.target.value)} />
            </Field>
            <Field label="Email" error={errors["user.email"]}>
              <Input
                type="email"
                autoComplete="email"
                inputMode="email"
                value={form.user.email}
                onChange={(e) => setUser("email", e.target.value)}
              />
            </Field>
            <Field label="Password" hint="At least 8 characters." error={errors["user.password"]}>
              <PasswordInput
                autoComplete="new-password"
                value={form.user.password}
                onChange={(e) => setUser("password", e.target.value)}
              />
            </Field>
          </Section>

          <Section step={2} title="Your business" description="What callers hear when they ask where and when.">
            <Fieldset legend="What kind of business is it?" error={errors["business.template"]}>
              {templates ? (
                <TemplatePicker
                  templates={templates}
                  value={form.business.template}
                  invalid={!!errors["business.template"]}
                  onChange={(name) => {
                    const t = templates.find((x) => x.template === name);
                    if (t) edit(["business.template", "details"], (f) => switchTemplate(f, t));
                  }}
                />
              ) : loadError ? (
                <EmptyState
                  icon={AlertCircle}
                  title="The form didn't load"
                  description={loadError}
                  action={
                    <Button id="templates-retry" variant="outline" onClick={() => setLoadAttempt((n) => n + 1)}>
                      <RotateCw /> Try again
                    </Button>
                  }
                />
              ) : (
                <div className="grid gap-3 sm:grid-cols-2" aria-label="Loading business types" role="status">
                  {[0, 1].map((i) => (
                    <div key={i} className="h-[120px] animate-pulse rounded-lg bg-muted" />
                  ))}
                </div>
              )}
            </Fieldset>

            <Field
              label={`${labels.tenant ?? "Business"} name`}
              hint="As callers know it, e.g. the name on your board."
              error={errors["business.name"]}
            >
              <Input
                autoComplete="organization"
                value={form.business.name}
                onChange={(e) => setBusiness("name", e.target.value)}
              />
            </Field>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="City" optional error={errors["business.city"]}>
                <Input
                  autoComplete="address-level2"
                  value={form.business.city}
                  onChange={(e) => setBusiness("city", e.target.value)}
                />
              </Field>
              <Field label="Landmark" optional error={errors["business.landmark"]}>
                <Input
                  placeholder="e.g. Near the main bus stand"
                  value={form.business.landmark}
                  onChange={(e) => setBusiness("landmark", e.target.value)}
                />
              </Field>
            </div>
            <Field label="Address" error={errors["business.address"]}>
              <Input
                autoComplete="street-address"
                value={form.business.address}
                onChange={(e) => setBusiness("address", e.target.value)}
              />
            </Field>

            <Fieldset
              legend="Opening hours"
              hint="Add a second session if you close for lunch."
              error={errors["business.hours"]}
            >
              <HoursEditor
                value={form.business.hours}
                errors={errors}
                onChange={(hours) => setBusiness("hours", hours)}
              />
            </Fieldset>

            <Fieldset legend="Closed on" hint="Tap the days you're closed every week." error={errors["business.closed_weekdays"]}>
              <WeekdayPicker
                value={form.business.closed_weekdays}
                onChange={(days) => setBusiness("closed_weekdays", days)}
              />
            </Fieldset>

            <Field
              label="Your WhatsApp number"
              hint="You'll get alerts here and can control the agent from WhatsApp. Only this number can send it commands."
              error={errors["business.owner_whatsapp"]}
            >
              <Input
                type="tel"
                inputMode="tel"
                autoComplete="tel-national"
                placeholder="10-digit mobile number"
                value={form.business.owner_whatsapp}
                onChange={(e) => setBusiness("owner_whatsapp", e.target.value)}
              />
            </Field>

            <Fieldset legend="Agent's voice" error={errors["business.voice"]}>
              <RadioGroup
                value={form.business.voice}
                onValueChange={(v) => setBusiness("voice", v === "male" ? "male" : "female")}
                className="flex flex-wrap gap-x-6 gap-y-3"
              >
                {(["female", "male"] as const).map((v) => (
                  <div key={v} className="flex items-center gap-2.5">
                    <RadioGroupItem value={v} id={`voice-${v}`} />
                    <Label htmlFor={`voice-${v}`} className="font-normal">
                      {v === "female" ? "Female voice" : "Male voice"}
                    </Label>
                  </div>
                ))}
              </RadioGroup>
            </Fieldset>
          </Section>

          {template && hasModule(template, "bookings") && (
            <Section
              step={3}
              title={`${resourcePlural} and services`}
              description="Prefilled for a typical clinic. Check it matches yours."
            >
              <Fieldset
                legend={resourcePlural}
                hint="Callers can ask for them by name."
                error={errors["details.doctors"]}
              >
                {form.bookings.doctors.map((d, i) => (
                  <div key={i} className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                      <Input
                        aria-label={`${resource} ${i + 1} name`}
                        placeholder={`e.g. ${resource} A`}
                        value={d.name}
                        aria-invalid={errors[`details.doctors.${i}.name`] ? true : undefined}
                        aria-describedby={errors[`details.doctors.${i}.name`] ? `doctor-${i}-error` : undefined}
                        onChange={(e) =>
                          edit(["details.doctors"], (f) => ({
                            ...f,
                            bookings: {
                              ...f.bookings,
                              doctors: f.bookings.doctors.map((x, j) => (j === i ? { name: e.target.value } : x)),
                            },
                          }))
                        }
                      />
                      {form.bookings.doctors.length > 1 && (
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Remove ${resource.toLowerCase()} ${i + 1}`}
                          onClick={() =>
                            edit("details.doctors", (f) => ({
                              ...f,
                              bookings: { ...f.bookings, doctors: f.bookings.doctors.filter((_, j) => j !== i) },
                            }))
                          }
                        >
                          <X />
                        </Button>
                      )}
                    </div>
                    {errors[`details.doctors.${i}.name`] && (
                      <p id={`doctor-${i}-error`} role="alert" className="text-[13px] font-medium text-destructive">
                        {errors[`details.doctors.${i}.name`]}
                      </p>
                    )}
                  </div>
                ))}
                {form.bookings.doctors.length < MAX_DOCTORS && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="self-start px-2"
                    onClick={() =>
                      edit("details.doctors", (f) => ({
                        ...f,
                        bookings: { ...f.bookings, doctors: [...f.bookings.doctors, { name: "" }] },
                      }))
                    }
                  >
                    <Plus /> Add another {resource.toLowerCase()}
                  </Button>
                )}
              </Fieldset>

              <Fieldset
                legend="Services and fees"
                hint="The agent quotes only these. Leave a row empty to skip it."
                error={errors["details.services"]}
              >
                {form.bookings.services.map((s, i) => {
                  const nameErr = errors[`details.services.${i}.name`];
                  const feeErr = errors[`details.services.${i}.fee`];
                  const setRow = (patch: Partial<typeof s>) =>
                    edit(`details.services.${i}`, (f) => ({
                      ...f,
                      bookings: {
                        ...f.bookings,
                        services: f.bookings.services.map((x, j) => (j === i ? { ...x, ...patch } : x)),
                      },
                    }));
                  return (
                    <div key={i} className="flex flex-col gap-1">
                      <div className="flex flex-wrap items-center gap-2 sm:flex-nowrap">
                        <Input
                          aria-label={`Service ${i + 1}`}
                          className="basis-full sm:basis-auto"
                          placeholder="e.g. Consultation"
                          value={s.name}
                          aria-invalid={nameErr ? true : undefined}
                          aria-describedby={nameErr ? `service-${i}-error` : undefined}
                          onChange={(e) => setRow({ name: e.target.value })}
                        />
                        <Input
                          aria-label={`Service ${i + 1} fee`}
                          placeholder="₹300"
                          value={s.fee}
                          aria-invalid={feeErr ? true : undefined}
                          aria-describedby={feeErr ? `service-${i}-error` : undefined}
                          onChange={(e) => setRow({ fee: e.target.value })}
                          className="min-w-0 flex-1 sm:max-w-28"
                        />
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Remove service ${i + 1}`}
                          onClick={() =>
                            edit("details.services", (f) => ({
                              ...f,
                              bookings: { ...f.bookings, services: f.bookings.services.filter((_, j) => j !== i) },
                            }))
                          }
                        >
                          <X />
                        </Button>
                      </div>
                      {(nameErr || feeErr) && (
                        <p id={`service-${i}-error`} role="alert" className="text-[13px] font-medium text-destructive">
                          {nameErr ?? feeErr}
                        </p>
                      )}
                    </div>
                  );
                })}
                <Button
                  variant="ghost"
                  size="sm"
                  className="self-start px-2"
                  onClick={() =>
                    edit("details.services", (f) => ({
                      ...f,
                      bookings: { ...f.bookings, services: [...f.bookings.services, { name: "", fee: "" }] },
                    }))
                  }
                >
                  <Plus /> Add a service
                </Button>
              </Fieldset>

              <Field label={`${bookingLabel} length`} error={errors["details.slot_min"]}>
                <select
                  className={selectClass}
                  value={form.bookings.slot_min}
                  onChange={(e) =>
                    edit("details.slot_min", (f) => ({
                      ...f,
                      bookings: { ...f.bookings, slot_min: Number(e.target.value) },
                    }))
                  }
                >
                  {[...new Set([...SLOT_CHOICES, form.bookings.slot_min])]
                    .sort((a, b) => a - b)
                    .map((m) => (
                      <option key={m} value={m}>
                        {m} minutes
                      </option>
                    ))}
                </select>
              </Field>

              <Field
                label="What should callers do in an emergency?"
                hint="The agent reads this out when a caller describes an emergency. It never gives medical advice."
                error={errors["details.emergency_instruction"]}
              >
                <Textarea
                  rows={4}
                  value={form.bookings.emergency_instruction}
                  onChange={(e) =>
                    edit("details.emergency_instruction", (f) => ({
                      ...f,
                      bookings: { ...f.bookings, emergency_instruction: e.target.value },
                    }))
                  }
                />
              </Field>
            </Section>
          )}

          {template && hasModule(template, "orders") && (
            <Section step={3} title="Orders" description="What the agent tells shops about ordering from you.">
              <Field label="Minimum order" optional hint="e.g. ₹2,000" error={errors["details.min_order"]}>
                <Input
                  value={form.orders.min_order}
                  onChange={(e) =>
                    edit("details.min_order", (f) => ({ ...f, orders: { ...f.orders, min_order: e.target.value } }))
                  }
                />
              </Field>
              <Field
                label="Where do you deliver?"
                optional
                hint="e.g. Anywhere in the city, or a list of areas."
                error={errors["details.delivery_area"]}
              >
                <Input
                  value={form.orders.delivery_area}
                  onChange={(e) =>
                    edit("details.delivery_area", (f) => ({
                      ...f,
                      orders: { ...f.orders, delivery_area: e.target.value },
                    }))
                  }
                />
              </Field>
              <p className="text-sm text-muted-foreground">You&apos;ll add your products and rates after signing up.</p>
            </Section>
          )}

          <details
            open={optionalOpen || optionalErrors}
            onToggle={(e) => setOptionalOpen((e.currentTarget as HTMLDetailsElement).open)}
            className="group rounded-lg border bg-card"
          >
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-lg px-6 py-4 font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring sm:px-8 [&::-webkit-details-marker]:hidden">
              <span>
                Optional, fill in later
                <span className="block text-sm font-normal text-muted-foreground">
                  Common questions, and anything else the agent should know
                </span>
              </span>
              <Plus aria-hidden className="size-5 shrink-0 transition-transform group-open:rotate-45" />
            </summary>
            <div className="flex flex-col gap-6 px-6 pb-6 sm:px-8 sm:pb-8">
              <Fieldset legend="Common questions" hint="The agent answers these word for word.">
                {form.faqs.map((q, i) => {
                  const setRow = (patch: Partial<typeof q>) =>
                    edit(`faqs.${i}`, (f) => ({ ...f, faqs: f.faqs.map((x, j) => (j === i ? { ...x, ...patch } : x)) }));
                  const qErr = errors[`faqs.${i}.q`];
                  const aErr = errors[`faqs.${i}.a`];
                  return (
                    <div key={i} className="flex flex-col gap-2 rounded-md border p-3">
                      <div className="flex items-start gap-2">
                        <div className="flex flex-1 flex-col gap-2">
                          <Input
                            aria-label={`Question ${i + 1}`}
                            placeholder="e.g. Is there parking?"
                            value={q.q}
                            aria-invalid={qErr ? true : undefined}
                            aria-describedby={qErr ? `faq-${i}-error` : undefined}
                            onChange={(e) => setRow({ q: e.target.value })}
                          />
                          <Textarea
                            aria-label={`Answer ${i + 1}`}
                            placeholder="e.g. Yes, free parking behind the building."
                            rows={2}
                            className="min-h-16"
                            value={q.a}
                            aria-invalid={aErr ? true : undefined}
                            aria-describedby={aErr ? `faq-${i}-error` : undefined}
                            onChange={(e) => setRow({ a: e.target.value })}
                          />
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={`Remove question ${i + 1}`}
                          onClick={() => edit("faqs", (f) => ({ ...f, faqs: f.faqs.filter((_, j) => j !== i) }))}
                        >
                          <X />
                        </Button>
                      </div>
                      {(qErr || aErr) && (
                        <p id={`faq-${i}-error`} role="alert" className="text-[13px] font-medium text-destructive">
                          {qErr ?? aErr}
                        </p>
                      )}
                    </div>
                  );
                })}
                <Button
                  variant="ghost"
                  size="sm"
                  className="self-start px-2"
                  onClick={() => edit("faqs", (f) => ({ ...f, faqs: [...f.faqs, { q: "", a: "" }] }))}
                >
                  <Plus /> Add a question
                </Button>
              </Fieldset>

              <Field
                label={
                  <>
                    Anything else the agent should know? <span lang="hi-Latn">(Agent ko aur kya batana hai?)</span>
                  </>
                }
                optional
                hint={
                  <span className="flex justify-between gap-3">
                    <span>Plain words, e.g. &quot;Pehle Hindi mein baat karo.&quot; It can never override safety rules.</span>
                    <span
                      aria-live="polite"
                      className={cn(
                        "shrink-0 tabular-nums",
                        form.instructions.length > MAX_INSTRUCTIONS && "font-medium text-destructive",
                      )}
                    >
                      {form.instructions.length}/{MAX_INSTRUCTIONS}
                    </span>
                  </span>
                }
                error={errors["instructions"]}
              >
                <Textarea
                  rows={3}
                  value={form.instructions}
                  onChange={(e) => edit("instructions", (f) => ({ ...f, instructions: e.target.value }))}
                />
              </Field>
            </div>
          </details>

          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1.5">
              <div className="flex items-start gap-3">
                <Checkbox
                  id="consent"
                  checked={form.business.consent}
                  aria-invalid={errors["business.consent"] ? true : undefined}
                  aria-describedby={errors["business.consent"] ? "consent-error" : undefined}
                  onCheckedChange={(v) => setBusiness("consent", v === true)}
                  className="mt-0.5"
                />
                <Label htmlFor="consent" className="font-normal text-body">
                  {CONSENT_TEXT}
                </Label>
              </div>
              {errors["business.consent"] && (
                <p id="consent-error" role="alert" className="pl-8 text-[13px] font-medium text-destructive">
                  {errors["business.consent"]}
                </p>
              )}
            </div>

            {formError && (
              <div
                role="alert"
                className="flex items-start gap-2.5 rounded-md bg-destructive-soft px-4 py-3 text-sm text-destructive-text"
              >
                <AlertCircle aria-hidden className="mt-0.5 size-4 shrink-0" />
                <p>
                  {formError.detail}
                  {formError.code === "EMAIL_TAKEN" && (
                    <>
                      {" "}
                      <a href="/login" className="font-semibold underline underline-offset-2">
                        Go to login
                      </a>
                    </>
                  )}
                </p>
              </div>
            )}

            <Button type="submit" size="lg" disabled={submitting} className="w-full sm:w-auto sm:self-end">
              {submitting ? (
                <>
                  <Loader2 aria-hidden className="animate-spin" /> Setting up your front desk…
                </>
              ) : (
                "Create my front desk"
              )}
            </Button>
          </div>
        </form>
      </main>
    </>
  );
}

import { AlertCircle, House, Loader2, RotateCw } from "lucide-react";
import * as React from "react";
import { Link, useNavigate } from "react-router";

import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { Field } from "@/components/field";
import { Fieldset } from "@/components/fieldset";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { type Block, getSettings, saveSettings } from "@/features/settings/api";
import { agentToast } from "@/features/settings/agent-toast";
import { CatalogueSection } from "@/features/settings/catalogue";
import { InstructionsSection } from "@/features/settings/instructions";
import { LeaveSection } from "@/features/settings/leave";
import { check, type Form, formErrors, isDirty, MAX_DOCTORS, SLOT_CHOICES, toBody, toForm } from "@/features/settings/model";
import { PairRows, TextRows } from "@/features/settings/rows";
import { HoursEditor } from "@/features/signup/hours-editor";
import { WeekdayPicker } from "@/features/signup/weekday-picker";
import { useActivityPing } from "@/hooks/use-activity-ping";
import { ApiError } from "@/lib/api";
import { getMe } from "@/lib/session";
import { cn } from "@/lib/utils";

const isAbort = (e: unknown) => e instanceof DOMException && e.name === "AbortError";

function Section({ id, title, hint, children }: { id: string; title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="flex scroll-mt-32 flex-col gap-4 rounded-lg border bg-card p-4 sm:p-6">
      <div className="flex flex-col gap-1">
        <h2 id={`${id}-title`} className="text-lg font-semibold">
          {title}
        </h2>
        {hint && <p className="text-sm text-muted-foreground">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

/**
 * The owner's settings (M8, C12): one page, every section stacked, one Save that rebuilds the
 * prompt and re-syncs only this business's assistant. The Save bar appears once something
 * changed; leaving with unsaved changes asks first.
 */
export function SettingsPage() {
  const navigate = useNavigate();
  useActivityPing(); // time in the app, for the team's dashboard (issue #56)
  const [saved, setSaved] = React.useState<Form | null>(null);
  const [form, setForm] = React.useState<Form | null>(null);
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [attempt, setAttempt] = React.useState(0);
  const [errors, setErrors] = React.useState<Record<string, string>>({});
  const [problem, setProblem] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [blocks, setBlocks] = React.useState<Block[]>([]);
  const [instructionsDirty, setInstructionsDirty] = React.useState(false);
  const [template, setTemplate] = React.useState<string | null>(null);
  const problemRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const ctrl = new AbortController();
    getMe(ctrl.signal)
      .then((m) => setTemplate(m.business.template))
      .catch(() => {}); // only names the sample CSV; the settings load reports any real trouble
    getSettings(ctrl.signal)
      .then((r) => {
        const f = toForm(r.settings);
        setSaved(f);
        setForm(f);
        setBlocks(r.blocks ?? []);
        setLoadError(null);
      })
      .catch((err: unknown) => {
        if (isAbort(err)) return;
        if (err instanceof ApiError && err.status === 401) {
          navigate("/login?next=/settings", { replace: true });
          return;
        }
        setLoadError(err instanceof ApiError ? err.detail : "Your settings didn't load.");
      });
    return () => ctrl.abort();
  }, [attempt, navigate]);

  const dirty = form !== null && saved !== null && isDirty(form, saved);
  const anythingUnsaved = dirty || instructionsDirty;

  // Closing the tab or reloading with unsaved changes asks first.
  React.useEffect(() => {
    if (!anythingUnsaved) return;
    const onLeave = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", onLeave);
    return () => window.removeEventListener("beforeunload", onLeave);
  }, [anythingUnsaved]);

  // Leave days and instructions save on their own; a 401 there keeps the page and says so.
  const onAuthError = React.useCallback((err: unknown) => {
    if (!(err instanceof ApiError && err.status === 401)) return false;
    setProblem("You've been logged out. Log in again in another tab, then try again; nothing here is lost.");
    return true;
  }, []);

  function set<K extends keyof Form>(k: K, v: Form[K]) {
    setForm((f) => (f ? { ...f, [k]: v } : f));
  }

  function showProblem(message: string) {
    setProblem(message);
    requestAnimationFrame(() => problemRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }));
  }

  async function onSave() {
    if (!form || saving) return;
    const e = check(form);
    setErrors(e);
    if (Object.keys(e).length) {
      showProblem("Please fix the highlighted fields.");
      return;
    }
    setProblem(null);
    setSaving(true);
    try {
      const r = await saveSettings(toBody(form));
      const f = toForm(r.settings);
      setSaved(f);
      setForm(f);
      agentToast(r.agent);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        // Keep what was typed: the owner logs in again in a new tab and saves from here.
        showProblem("You've been logged out. Log in again in another tab, then save; nothing here is lost.");
      } else if (err instanceof ApiError) {
        setErrors(formErrors(err.fields));
        showProblem(err.detail);
      } else {
        showProblem("Couldn't save your settings. Please try again.");
      }
    } finally {
      setSaving(false);
    }
  }

  const header = (
    <AppHeader>
      <Button asChild variant="ghost" size="sm">
        <Link
          to="/home"
          onClick={(e) => {
            if (anythingUnsaved && !window.confirm("Leave without saving your changes?")) e.preventDefault();
          }}
        >
          <House aria-hidden /> Home
        </Link>
      </Button>
    </AppHeader>
  );

  if (loadError) {
    return (
      <>
        {header}
        <main className="mx-auto max-w-2xl px-4 py-12 sm:px-6">
          <EmptyState
            icon={AlertCircle}
            title="Your settings didn't load"
            description={loadError}
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
        </main>
      </>
    );
  }

  if (!form) {
    return (
      <>
        {header}
        <main className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-8 sm:px-6" role="status" aria-label="Loading your settings">
          <div className="h-8 w-1/2 animate-pulse rounded-md bg-muted" />
          <div className="h-48 animate-pulse rounded-lg bg-muted" />
          <div className="h-48 animate-pulse rounded-lg bg-muted" />
        </main>
      </>
    );
  }

  const bookings = form.kind === "bookings";
  const sections = [
    { id: "business", label: "Business" },
    { id: "hours", label: "Hours" },
    ...(bookings ? [{ id: "leave", label: "Leave" }] : []),
    bookings ? { id: "doctors", label: "Doctors" } : { id: "orders", label: "Orders" },
    ...(bookings ? [] : [{ id: "catalogue", label: "Catalogue" }]),
    ...(bookings ? [{ id: "safety", label: "Emergencies" }] : []),
    { id: "faqs", label: "Questions" },
    { id: "instructions", label: "Instructions" },
    { id: "whatsapp", label: "WhatsApp" },
  ];

  return (
    <>
      {header}
      <main className={cn("mx-auto flex max-w-3xl flex-col gap-5 px-4 pt-6 sm:px-6 sm:pt-8", dirty ? "pb-32" : "pb-12")}>
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold leading-tight tracking-tight">Settings</h1>
          <p className="text-sm text-muted-foreground">Your front desk says only what&apos;s here. Saving updates it straight away.</p>
        </div>

        <nav aria-label="Sections" className="sticky top-16 z-30 -mx-4 flex gap-1.5 overflow-x-auto border-b bg-background/95 px-4 py-2 backdrop-blur-sm [scrollbar-width:none] sm:mx-0 sm:rounded-lg sm:border sm:px-2 [&::-webkit-scrollbar]:hidden">
          {sections.map((s) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              className="flex min-h-9 shrink-0 items-center rounded-full px-3.5 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            >
              {s.label}
            </a>
          ))}
        </nav>

        {problem && (
          <div ref={problemRef} role="alert" className="rounded-lg bg-destructive-soft px-4 py-3 text-sm text-destructive-text">
            {problem}
          </div>
        )}

        <Section id="business" title="Business">
          <Field label="Business name" error={errors.name}>
            <Input value={form.name} onChange={(e) => set("name", e.target.value)} maxLength={80} autoComplete="organization" />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="City" optional error={errors.city}>
              <Input value={form.city} onChange={(e) => set("city", e.target.value)} maxLength={60} />
            </Field>
            <Field label="Landmark" optional error={errors.landmark} hint="Callers often ask how to find you.">
              <Input value={form.landmark} onChange={(e) => set("landmark", e.target.value)} maxLength={120} />
            </Field>
          </div>
          <Field label="Address" error={errors.address}>
            <Input value={form.address} onChange={(e) => set("address", e.target.value)} maxLength={200} autoComplete="street-address" />
          </Field>
        </Section>

        <Section id="hours" title="Hours" hint="Callers hear these, and bookings are only offered inside them.">
          <Fieldset legend="Open" error={errors.sessions}>
            <HoursEditor value={form.hours} onChange={(v) => set("hours", v)} errors={errors} />
          </Fieldset>
          <Fieldset legend="Closed on" error={errors.closed_weekdays}>
            <WeekdayPicker value={form.closed_weekdays} onChange={(v) => set("closed_weekdays", v)} />
          </Fieldset>
          {bookings && (
            <Field label="Length of one appointment" error={errors.slot_min} hint="Changing it moves the times on offer; existing bookings stay.">
              <select
                value={form.slot_min}
                onChange={(e) => set("slot_min", e.target.value)}
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm sm:w-48"
              >
                {SLOT_CHOICES.map((m) => (
                  <option key={m} value={m}>
                    {m} minutes
                  </option>
                ))}
              </select>
            </Field>
          )}
        </Section>

        {bookings && (
          <Section id="leave" title="Leave and holidays" hint="Days a doctor is away, or the whole clinic is closed. Callers aren't offered those days.">
            <LeaveSection
              blocks={blocks}
              onBlocks={setBlocks}
              doctors={(saved?.doctors ?? []).filter((d): d is { id: string; name: string } => Boolean(d.id))}
              onAuthError={onAuthError}
            />
          </Section>
        )}

        {bookings ? (
          <Section id="doctors" title="Doctors and services">
            <Fieldset legend="Doctors" error={errors.doctors} hint="A doctor with upcoming bookings can't be removed until they're moved or cancelled.">
              <TextRows
                values={form.doctors.map((d) => d.name)}
                onChange={(i, name) => set("doctors", form.doctors.map((d, j) => (j === i ? { ...d, name } : d)))}
                onRemove={(i) => set("doctors", form.doctors.filter((_, j) => j !== i))}
                onAdd={() => set("doctors", [...form.doctors, { name: "" }])}
                label={(i) => `Doctor ${i + 1}`}
                addLabel="Add a doctor"
                errors={errors}
                errorKey={(i) => `doctors.${i}.name`}
                max={MAX_DOCTORS}
              />
            </Fieldset>
            <Fieldset legend="Services and fees" hint="Callers hear these fees exactly as written." error={errors.services}>
              <PairRows
                values={form.services}
                onChange={(v) => set("services", v)}
                keys={["name", "fee"]}
                labels={(i) => [`Service ${i + 1}`, `Service ${i + 1} fee`]}
                addLabel="Add a service"
                errors={errors}
                errorPrefix="services"
                empty={{ name: "", fee: "" }}
              />
            </Fieldset>
          </Section>
        ) : (
          <Section id="orders" title="Orders" hint="Your products and rates are in the catalogue below.">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Minimum order" optional error={errors.min_order} hint="For example: ₹2,000">
                <Input value={form.min_order} onChange={(e) => set("min_order", e.target.value)} maxLength={60} />
              </Field>
              <Field label="Delivery area" optional error={errors.delivery_area}>
                <Input value={form.delivery_area} onChange={(e) => set("delivery_area", e.target.value)} maxLength={120} />
              </Field>
            </div>
          </Section>
        )}

        {!bookings && (
          <Section id="catalogue" title="Catalogue" hint="Your front desk quotes only these products and rates. Changes here save straight away.">
            <CatalogueSection template={template} onAuthError={onAuthError} />
          </Section>
        )}

        {bookings && (
          <Section id="safety" title="Emergencies" hint="Anything medical always goes to a person; these settings decide what callers hear first.">
            <Field
              label="Emergency instruction"
              error={errors.emergency_instruction}
              hint="Said word for word when a caller describes an emergency."
            >
              <Textarea value={form.emergency_instruction} onChange={(e) => set("emergency_instruction", e.target.value)} maxLength={600} />
            </Field>
            <Fieldset legend="Red-flag words" hint="Any of these: the caller hears the emergency instruction and you're alerted at once. Built-in safety rules always apply as well.">
              <TextRows
                values={form.red_flags}
                onChange={(i, v) => set("red_flags", form.red_flags.map((x, j) => (j === i ? v : x)))}
                onRemove={(i) => set("red_flags", form.red_flags.filter((_, j) => j !== i))}
                onAdd={() => set("red_flags", [...form.red_flags, ""])}
                label={(i) => `Red-flag word ${i + 1}`}
                addLabel="Add a word"
                errors={errors}
                errorKey={(i) => `red_flags.${i}`}
                max={40}
              />
            </Fieldset>
          </Section>
        )}

        <Section id="faqs" title="Questions and answers" hint="Your front desk answers only these, plus your hours, address, doctors and fees.">
          <PairRows
            values={form.faqs}
            onChange={(v) => set("faqs", v)}
            keys={["q", "a"]}
            labels={(i) => [`Question ${i + 1}`, `Answer ${i + 1}`]}
            addLabel="Add a question"
            errors={errors}
            errorPrefix="faqs"
            multiline
            empty={{ q: "", a: "" }}
          />
        </Section>

        <Section id="instructions" title="Your own instructions" hint="Anything else your front desk should know. It saves on its own and never overrides the safety rules.">
          <InstructionsSection onAuthError={onAuthError} onDirtyChange={setInstructionsDirty} />
        </Section>

        <Section id="whatsapp" title="WhatsApp and voice">
          <Fieldset legend="WhatsApp numbers" error={errors.whatsapp_numbers} hint="These numbers get alerts and the daily summary, and can change settings by message.">
            <TextRows
              values={form.whatsapp_numbers}
              onChange={(i, v) => set("whatsapp_numbers", form.whatsapp_numbers.map((x, j) => (j === i ? v : x)))}
              onRemove={(i) => set("whatsapp_numbers", form.whatsapp_numbers.filter((_, j) => j !== i))}
              onAdd={() => set("whatsapp_numbers", [...form.whatsapp_numbers, ""])}
              label={(i) => `WhatsApp number ${i + 1}`}
              addLabel="Add a number"
              errors={errors}
              errorKey={(i) => `whatsapp_numbers.${i}`}
              max={5}
              inputMode="tel"
              placeholder="10-digit mobile number"
            />
          </Fieldset>
          <Fieldset legend="Front desk's voice">
            <RadioGroup value={form.voice} onValueChange={(v) => set("voice", v as Form["voice"])} className="flex gap-6">
              <div className="flex items-center gap-2">
                <RadioGroupItem value="female" id="voice-female" />
                <Label htmlFor="voice-female">Female</Label>
              </div>
              <div className="flex items-center gap-2">
                <RadioGroupItem value="male" id="voice-male" />
                <Label htmlFor="voice-male">Male</Label>
              </div>
            </RadioGroup>
          </Fieldset>
        </Section>
      </main>

      {dirty && (
        <div className="fixed inset-x-0 bottom-0 z-40 border-t bg-background/95 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur-sm">
          <div className="mx-auto flex max-w-3xl items-center justify-between gap-3">
            <p className="text-sm font-medium" aria-live="polite">
              Unsaved changes
            </p>
            <div className="flex gap-2">
              <Button
                variant="ghost"
                onClick={() => {
                  setForm(saved);
                  setErrors({});
                  setProblem(null);
                }}
                disabled={saving}
              >
                Discard
              </Button>
              <Button onClick={() => void onSave()} disabled={saving}>
                {saving && <Loader2 aria-hidden className="animate-spin" />} Save changes
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

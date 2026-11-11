import { CalendarX2, CheckCircle2, PhoneCall } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { toast } from "sonner";

import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { Field } from "@/components/field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";

const SWATCHES = [
  ["background", "bg-background"],
  ["foreground", "bg-foreground"],
  ["muted", "bg-muted"],
  ["muted-foreground", "bg-muted-foreground"],
  ["border", "bg-border"],
  ["input", "bg-input"],
  ["destructive", "bg-destructive"],
  ["live", "bg-live"],
  ["success", "bg-success"],
] as const;

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

/** Every token and shared component on one page, for review at 360px and desktop (DESIGN.md). */
export function StyleguidePage() {
  return (
    <>
      <AppHeader>
        <Button asChild variant="ghost" size="sm">
          <Link to="/login">Log in</Link>
        </Button>
        <Button asChild size="sm">
          <Link to="/signup">Start free</Link>
        </Button>
      </AppHeader>

      <main className="mx-auto flex max-w-6xl flex-col gap-12 px-4 py-10 sm:px-6 sm:py-14">
        <div className="flex flex-col gap-2">
          <p className="text-[13px] font-medium text-muted-foreground">Design system · frontend/DESIGN.md</p>
          <h1 className="text-[28px] font-semibold leading-tight tracking-tight">Catalyst styleguide</h1>
          <p className="max-w-2xl text-body">
            Calls answered while you&apos;re with a patient. Every page is built from these pieces.
          </p>
        </div>

        <Section title="Colour">
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {SWATCHES.map(([name, cls]) => (
              <li key={name} className="flex items-center gap-3 rounded-lg border p-3">
                <span className={`size-9 shrink-0 rounded-md border ${cls}`} />
                <code className="break-all text-[13px]">{name}</code>
              </li>
            ))}
          </ul>
        </Section>

        <Section title="Type">
          <div className="flex flex-col gap-3">
            <p className="text-4xl font-semibold leading-tight tracking-tight">Never miss a patient call</p>
            <p className="text-[28px] font-semibold leading-tight tracking-tight">Today&apos;s schedule</p>
            <p className="text-lg font-semibold">Doctor A · 6 bookings</p>
            <p className="text-base text-body">
              The agent answers in Hindi, English or Hinglish, books into one shared schedule and sends anything
              medical to a human.
            </p>
            <p className="text-base text-body" lang="hi">
              मरीज़ों की कॉल कभी मिस नहीं होगी। कल सुबह 10:30 बजे का स्लॉट बुक हो गया है।
            </p>
            <p className="text-[13px] text-muted-foreground">Mon, 4 Nov · 10:30 am · ₹1,500</p>
          </div>
        </Section>

        <Section title="Buttons">
          <div className="flex flex-wrap items-center gap-3">
            <Button>Save changes</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive">Cancel booking</Button>
            <Button variant="link">Text link</Button>
            <Button disabled>Disabled</Button>
            <Button size="lg">Large (mobile main action)</Button>
            <Button size="icon" variant="outline" aria-label="Call">
              <PhoneCall />
            </Button>
          </div>
        </Section>

        <Section title="Badges">
          <div className="flex flex-wrap gap-2">
            <Badge>Walk-in</Badge>
            <Badge variant="live">
              <PhoneCall aria-hidden /> Live call
            </Badge>
            <Badge variant="success">
              <CheckCircle2 aria-hidden /> Booked
            </Badge>
            <Badge variant="destructive">Needs a human</Badge>
          </div>
        </Section>

        <Section title="Form fields">
          <Card className="max-w-2xl">
            <CardHeader>
              <CardTitle>Your business</CardTitle>
              <CardDescription>This is what the agent tells callers.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-5">
              <Field label="Business name" hint="As callers know it, e.g. the name on your board.">
                <Input placeholder="Example Dental Care" />
              </Field>
              <Field label="Email" error="Enter an email like name@example.com.">
                <Input type="email" defaultValue="not-an-email" />
              </Field>
              <Field label="Landmark" optional>
                <Input placeholder="Near the main bus stand" />
              </Field>
              <Field label="Anything else the agent should know?" optional hint="Up to 500 characters.">
                <Textarea placeholder="Pehle Hindi mein baat karo." />
              </Field>
            </CardContent>
            <CardFooter className="justify-end">
              <Button variant="ghost">Back</Button>
              <Button onClick={() => toast.success("Saved")}>Save</Button>
            </CardFooter>
          </Card>
        </Section>

        <Section title="Toast and empty state">
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={() => toast.success("Booking saved")}>
              Show success toast
            </Button>
            <Button variant="outline" onClick={() => toast.error("That slot was just taken. Pick another time.")}>
              Show error toast
            </Button>
          </div>
          <EmptyState
            icon={CalendarX2}
            title="No bookings today"
            description="When the agent books a call, it shows up here straight away."
            action={<Button variant="outline">Add a walk-in</Button>}
          />
        </Section>
      </main>
    </>
  );
}

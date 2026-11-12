import {
  BadgeCheck,
  ClipboardCheck,
  Lock,
  MessageCircle,
  Package,
  Phone,
  PhoneCall,
  ShieldCheck,
  Stethoscope,
} from "lucide-react";
import { Link } from "react-router";

import { AppHeader } from "@/components/app-header";
import { type Feature, FeatureGrid } from "@/components/feature-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const STEPS: Feature[] = [
  {
    title: "1. Set up in about two minutes",
    icon: ClipboardCheck,
    description: "Tell us your hours, doctors and fees. That's all your front desk needs to start.",
  },
  {
    title: "2. It answers every call",
    icon: PhoneCall,
    description: "In Hindi, English or Hinglish. It books, moves or cancels into one shared register.",
  },
  {
    title: "3. You stay in control on WhatsApp",
    icon: MessageCircle,
    description: "Get alerts, take a day off or change a fee with one message. Every change asks you first.",
  },
];

const TRUST: Feature[] = [
  {
    title: "Medical questions go to a person",
    icon: Stethoscope,
    description: "It never gives medical advice. Anything medical is passed to you or your team.",
  },
  {
    title: "Says only what you approved",
    icon: BadgeCheck,
    description: "Fees, hours and answers come from your settings, never made up.",
  },
  {
    title: "Asks for the minimum",
    icon: Lock,
    description: "A caller's name, phone number and time. No medical details are collected.",
  },
];

/** The product, shown directly (DESIGN.md): a register with a booking that just came in by phone. */
function RegisterPreview() {
  const slots = [
    { time: "10:00", who: "Ramesh G.", state: "booked" },
    { time: "10:15", who: null, state: "free" },
    { time: "10:30", who: "Sita K.", state: "new" },
    { time: "10:45", who: null, state: "free" },
  ] as const;
  return (
    <div aria-hidden className="rounded-xl border bg-card p-4 shadow-sm sm:p-5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold">Today · Doctor A</p>
        <Badge variant="live">
          <Phone /> On a call
        </Badge>
      </div>
      <div className="mt-3 rounded-lg bg-muted px-3 py-2.5 text-sm">
        <p className="text-muted-foreground">Caller</p>
        <p>&ldquo;Aaj saade das baje Doctor A ke saath appointment mil jayega?&rdquo;</p>
      </div>
      <div className="mt-2 rounded-lg bg-primary px-3 py-2.5 text-sm text-primary-foreground">
        <p className="opacity-75">Your front desk</p>
        <p>&ldquo;Ji, 10:30 baje book kar diya. Naam bata dijiye?&rdquo;</p>
      </div>
      <ul className="mt-4 grid grid-cols-2 gap-2">
        {slots.map((s) => (
          <li
            key={s.time}
            className={
              s.state === "new"
                ? "rounded-md border border-live bg-live-soft px-2.5 py-2 text-sm"
                : s.state === "booked"
                  ? "rounded-md border bg-muted px-2.5 py-2 text-sm"
                  : "rounded-md border px-2.5 py-2 text-sm"
            }
          >
            <span className="font-medium tabular-nums">{s.time}</span>
            <span className="block truncate text-[13px] text-muted-foreground">
              {s.state === "new" ? (
                <span className="font-semibold text-live-text">New · {s.who}</span>
              ) : (
                (s.who ?? "Free")
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * The public home page (phase2-plan §6 "landing /"). Mobile first: most owners will open this on a
 * phone, so the main action sits in a bar pinned to the bottom of small screens.
 */
export function LandingPage() {
  return (
    <>
      <AppHeader>
        <Button asChild variant="ghost" size="sm">
          <Link to="/login">Log in</Link>
        </Button>
        <Button asChild size="sm" className="hidden sm:inline-flex">
          <Link to="/signup">Get started</Link>
        </Button>
      </AppHeader>

      <main className="pb-24 sm:pb-0">
        {/* Hero: one promise, then the product itself */}
        <section className="mx-auto grid max-w-6xl items-center gap-10 px-4 pb-14 pt-10 sm:px-6 sm:pt-16 lg:grid-cols-[minmax(0,6fr)_minmax(0,5fr)] lg:gap-14 lg:pb-24">
          <div className="flex flex-col gap-5">
            <p className="text-sm font-medium text-muted-foreground">An AI front desk for clinics and shops</p>
            <h1 className="text-4xl font-semibold leading-[1.1] tracking-tight sm:text-5xl">
              Never miss a patient call.
            </h1>
            <p className="text-lg text-body">
              Catalyst answers your phone like a polite receptionist, books into one shared register, and sends anything
              medical to a person.
            </p>
            <p lang="hi" className="text-base text-body">
              मरीज़ों की कॉल कभी मिस नहीं होगी, चाहे आप मरीज़ देख रहे हों।
            </p>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Button asChild size="lg" className="w-full sm:w-auto">
                <Link to="/signup">Set up your front desk</Link>
              </Button>
              <Button asChild size="lg" variant="outline" className="w-full sm:w-auto">
                <Link to="/demo/clinic">
                  <PhoneCall aria-hidden /> Try a demo call
                </Link>
              </Button>
            </div>
          </div>
          <RegisterPreview />
        </section>

        {/* How it works */}
        <section aria-labelledby="how" className="border-t bg-surface-soft">
          <div className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-14 sm:px-6 sm:py-20">
            <div className="flex max-w-2xl flex-col gap-2">
              <h2 id="how" className="text-[28px] font-semibold leading-tight tracking-tight">
                How it works
              </h2>
              <p className="text-body">No new app to learn. You set it up once, and it runs from your phone.</p>
            </div>
            <FeatureGrid features={STEPS} className="bg-background" />
          </div>
        </section>

        {/* Who it's for */}
        <section aria-labelledby="who" className="border-t">
          <div className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-14 sm:px-6 sm:py-20">
            <h2 id="who" className="text-[28px] font-semibold leading-tight tracking-tight">
              Built for small businesses that live on the phone
            </h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-3 rounded-lg border p-6">
                <span className="flex size-10 items-center justify-center rounded-md bg-muted">
                  <Stethoscope aria-hidden className="size-5" />
                </span>
                <h3 className="text-lg font-semibold">Clinics</h3>
                <p className="text-body">
                  Calls answered while you&apos;re with a patient. Appointments land in one register your receptionist
                  sees too.
                </p>
              </div>
              <div className="flex flex-col gap-3 rounded-lg border p-6">
                <span className="flex size-10 items-center justify-center rounded-md bg-muted">
                  <Package aria-hidden className="size-5" />
                </span>
                <h3 className="text-lg font-semibold">Wholesale distributors</h3>
                <p className="text-body">
                  Shops place and check orders by phone, even at 9 pm. Only your catalogue rates are ever quoted.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Trust */}
        <section aria-labelledby="safe" className="border-t bg-surface-soft">
          <div className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-14 sm:px-6 sm:py-20">
            <div className="flex max-w-2xl flex-col gap-2">
              <h2 id="safe" className="flex items-center gap-2 text-[28px] font-semibold leading-tight tracking-tight">
                <ShieldCheck aria-hidden className="size-7" /> Safe by design
              </h2>
              <p className="text-body">The rules that keep your callers safe can&apos;t be switched off.</p>
            </div>
            <FeatureGrid features={TRUST} className="bg-background" />
          </div>
        </section>

        {/* Closing call to action */}
        <section className="border-t">
          <div className="mx-auto flex max-w-3xl flex-col items-center gap-5 px-4 py-16 text-center sm:px-6 sm:py-24">
            <h2 className="text-[28px] font-semibold leading-tight tracking-tight sm:text-4xl">
              Your front desk, ready in minutes
            </h2>
            <p className="text-body">Set it up now, then call it yourself to hear how it sounds.</p>
            <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
              <Button asChild size="lg" className="w-full sm:w-auto">
                <Link to="/signup">Set up your front desk</Link>
              </Button>
              <Button asChild size="lg" variant="outline" className="w-full sm:w-auto">
                <Link to="/login">I already have an account</Link>
              </Button>
            </div>
          </div>
        </section>

        <footer className="border-t">
          <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-8 text-sm text-muted-foreground sm:flex-row sm:justify-between sm:px-6">
            <p>Catalyst · an AI front desk for small businesses in India</p>
            <p>Calls in Hindi, English and Hinglish</p>
          </div>
        </footer>
      </main>

      {/* Phones: the main action stays in reach at the bottom of the screen. */}
      <div className="fixed inset-x-0 bottom-0 z-30 border-t bg-background/95 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur-sm sm:hidden">
        <Button asChild size="lg" className="w-full">
          <Link to="/signup">Set up your front desk</Link>
        </Button>
      </div>
    </>
  );
}

import { AlertCircle, CheckCircle2, Clock } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

import type { AgentState, Template } from "./model";

type SuccessProps = {
  businessName: string;
  template: Template;
  agent: AgentState;
};

const AGENT: Record<AgentState, { badge: "success" | "neutral" | "destructive"; label: string; text: string }> = {
  updated: {
    badge: "success",
    label: "Voice agent ready",
    text: "Your front desk already knows your hours, address and services, and answers in Hindi, English or Hinglish.",
  },
  not_configured: {
    badge: "neutral",
    label: "Voice agent not switched on yet",
    text: "Your details are saved. The voice agent will use them as soon as it's switched on for your business.",
  },
  failed: {
    badge: "destructive",
    label: "Voice agent not set up yet",
    text: "Your business is saved, but we couldn't set up the voice agent just now. You can try again later; nothing you entered is lost.",
  },
};

/**
 * Shown after a successful signup. The owner is already logged in (the session cookie is set).
 * When the test page exists (a later M8 task), signup sends the owner there instead.
 */
export function SignupSuccess({ businessName, template, agent }: SuccessProps) {
  const a = AGENT[agent];
  const Icon = agent === "updated" ? CheckCircle2 : agent === "failed" ? AlertCircle : Clock;
  return (
    <Card role="status" aria-live="polite">
      <CardHeader className="gap-3">
        <span className="flex size-11 items-center justify-center rounded-full bg-success-soft">
          <CheckCircle2 aria-hidden className="size-6 text-success" />
        </span>
        <CardTitle className="text-[28px] font-semibold leading-tight tracking-tight">
          {businessName} is set up
        </CardTitle>
        <CardDescription className="text-base">
          Your {template.label.toLowerCase()} account is ready and you&apos;re logged in.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Badge variant={a.badge}>
          <Icon aria-hidden /> {a.label}
        </Badge>
        <p className="text-body">{a.text}</p>
      </CardContent>
      <CardFooter>
        <Button asChild variant="outline">
          <a href="/">Back to the home page</a>
        </Button>
      </CardFooter>
    </Card>
  );
}

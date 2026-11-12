import type { ReactNode } from "react";
import { BrowserRouter, Route, Routes } from "react-router";

import { ConnectionBanner } from "@/components/connection-banner";
import { OfflineBanner } from "@/components/offline-banner";
import { Toaster } from "@/components/ui/sonner";
import { WakeGate } from "@/components/wake-gate";
import { AdminPage } from "@/pages/admin";
import { DeskPage } from "@/pages/desk";
import { HomePage } from "@/pages/home";
import { LandingPage } from "@/pages/landing";
import { LoginPage } from "@/pages/login";
import { NotFoundPage } from "@/pages/not-found";
import { SettingsPage } from "@/pages/settings";
import { SignupPage } from "@/pages/signup";
import { DemoRedirect, TryPage } from "@/pages/try";
import { StyleguidePage } from "@/pages/styleguide";

/** Pages that need the backend wait behind the "waking up" screen (phase2-plan §5 cold starts). */
const awake = (page: ReactNode) => <WakeGate>{page}</WakeGate>;

/**
 * Routes. During M8 each page moves here one PR at a time (ADR-0042 decision 4). A route only
 * reaches production once `frontend/vercel.json` rewrites its path to the app shell.
 */
export function App() {
  return (
    <BrowserRouter>
      <OfflineBanner />
      <ConnectionBanner />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/admin" element={awake(<AdminPage />)} />
        <Route path="/b/:publicId/try" element={awake(<TryPage />)} />
        <Route path="/demo/:template" element={<DemoRedirect />} />
        <Route path="/desk" element={awake(<DeskPage />)} />
        <Route path="/home" element={awake(<HomePage />)} />
        <Route path="/login" element={awake(<LoginPage />)} />
        <Route path="/settings" element={awake(<SettingsPage />)} />
        <Route path="/signup" element={awake(<SignupPage />)} />
        {/* The design reference page is for the team: local `npm run dev` only, never on the live site. */}
        {import.meta.env.DEV && <Route path="/styleguide" element={<StyleguidePage />} />}
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
      <Toaster />
    </BrowserRouter>
  );
}

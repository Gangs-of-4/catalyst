import { BrowserRouter, Navigate, Route, Routes } from "react-router";

import { OfflineBanner } from "@/components/offline-banner";
import { Toaster } from "@/components/ui/sonner";
import { HomePage } from "@/pages/home";
import { LoginPage } from "@/pages/login";
import { NotFoundPage } from "@/pages/not-found";
import { SignupPage } from "@/pages/signup";
import { DemoRedirect, TryPage } from "@/pages/try";
import { StyleguidePage } from "@/pages/styleguide";

/**
 * Routes. During M8 each page moves here one PR at a time (ADR-0042 decision 4). A route only
 * reaches production once `frontend/vercel.json` rewrites its path to the app shell.
 */
export function App() {
  return (
    <BrowserRouter>
      <OfflineBanner />
      <Routes>
        {/* Locally the dev server has no old pages, so "/" opens the styleguide for now. */}
        <Route path="/" element={<Navigate to="/styleguide" replace />} />
        <Route path="/b/:publicId/try" element={<TryPage />} />
        <Route path="/demo/:template" element={<DemoRedirect />} />
        <Route path="/home" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/styleguide" element={<StyleguidePage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
      <Toaster />
    </BrowserRouter>
  );
}

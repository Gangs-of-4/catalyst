/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Locally, FastAPI runs on :8000. The dev server forwards API calls to it so the session cookie
// stays same-origin (ADR-0042 decision 3). In production the Vercel rewrite does the same (ADR-0041).
const backend = process.env.CATALYST_BACKEND_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: { "/api": backend, "/vapi": backend, "/healthz": backend },
  },
  build: { outDir: "dist", sourcemap: false },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
    // Full-page tests (settings, desk) render a lot on first run; 5 s is too tight on a loaded machine or CI.
    testTimeout: 15_000,
  },
});

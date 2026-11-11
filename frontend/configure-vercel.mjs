// Adds the backend rewrites to vercel.json just before `vercel build` (ADR-0041).
//
// vercel.json can't read environment variables, and the backend URL lives in the Vercel project's
// NEXT_PUBLIC_API_URL. The deploy workflow runs `vercel pull` (which saves the production env vars to
// .vercel/.env.production.local), then this script, then `vercel build`.
//
// With a URL: /api/* and /healthz are rewritten to the backend, so the browser sees one origin and the
// HttpOnly session cookie is first-party. Webhooks (Vapi, Twilio) still call the backend directly.
// Without a URL: vercel.json is left as it is (the pages show the backend as unreachable).
//
// Usage: node frontend/configure-vercel.mjs   (from the repo root, as the workflow does)
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const vercelJson = join(here, "vercel.json");
const envFiles = [join(here, "..", ".vercel", ".env.production.local"), join(here, ".vercel", ".env.production.local")];

/** The value of `name` from a dotenv file (KEY=value or KEY="value"), or "". */
function fromEnvFile(path, name) {
  if (!existsSync(path)) return "";
  for (const line of readFileSync(path, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
    if (m && m[1] === name) return m[2].replace(/^(["'])(.*)\1$/, "$2").trim();
  }
  return "";
}

export function backendUrl(env = process.env, files = envFiles) {
  const raw = (env.NEXT_PUBLIC_API_URL || files.map((f) => fromEnvFile(f, "NEXT_PUBLIC_API_URL")).find(Boolean) || "")
    .trim()
    .replace(/\/+$/, "");
  if (raw && !/^https:\/\/[^\s/]+$/.test(raw)) {
    throw new Error("NEXT_PUBLIC_API_URL must be empty or an https:// origin with no path, e.g. https://api.example.com");
  }
  return raw;
}

/** vercel.json with the backend rewrites first, so they win over the app's page rewrites. */
export function withBackendRewrites(config, url) {
  const own = (config.rewrites ?? []).filter((r) => !r.source.startsWith("/api") && r.source !== "/healthz");
  if (!url) return { ...config, rewrites: own };
  return {
    ...config,
    rewrites: [
      { source: "/api/:path*", destination: `${url}/api/:path*` },
      { source: "/healthz", destination: `${url}/healthz` },
      ...own,
    ],
  };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const url = backendUrl();
  const config = JSON.parse(readFileSync(vercelJson, "utf8"));
  const updated = withBackendRewrites(config, url);
  if (JSON.stringify(updated) !== JSON.stringify(config)) {
    writeFileSync(vercelJson, JSON.stringify(updated, null, 2) + "\n");
  }
  console.log(
    url
      ? "Backend rewrites added: /api/* and /healthz go to the backend (ADR-0041)."
      : "NEXT_PUBLIC_API_URL is empty: no backend rewrites, so the pages can't reach an API.",
  );
}

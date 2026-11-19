// Cloudflare Worker for the React app (ADR-0043). The app's files are Workers static assets
// (wrangler.jsonc); every page route gets the app shell through the single-page-application fallback.
//
// This script runs only for /api/* and /healthz (`run_worker_first`). It forwards the request to the
// backend (BACKEND_URL, an https origin) and returns the response unchanged, Set-Cookie included, so the
// browser sees one origin and the HttpOnly session cookie stays first-party (ADR-0041). No other logic
// and no storage. Webhooks (Vapi, Twilio) call the backend directly, not through here.

const json = (status, detail, code) =>
  new Response(JSON.stringify({ detail, code }), { status, headers: { "Content-Type": "application/json" } });

export const isForwarded = (pathname) => pathname === "/healthz" || pathname.startsWith("/api/");

/** The backend origin from BACKEND_URL, or "" when it's missing or not a bare https origin. */
export function backendOrigin(value) {
  const raw = (value || "").trim().replace(/\/+$/, "");
  return /^https:\/\/[^\s/]+$/.test(raw) ? raw : "";
}

/** The same request, aimed at the backend: method, headers (but Host), body and query kept. */
export function toBackend(request, origin) {
  const url = new URL(request.url);
  const headers = new Headers(request.headers);
  headers.delete("host");
  const hasBody = !["GET", "HEAD"].includes(request.method);
  return new Request(origin + url.pathname + url.search, {
    method: request.method,
    headers,
    body: hasBody ? request.body : undefined,
    redirect: "manual", // a backend redirect goes back to the browser as it is
    ...(hasBody ? { duplex: "half" } : {}),
  });
}

export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);
    if (!isForwarded(pathname)) return env.ASSETS.fetch(request);
    const origin = backendOrigin(env.BACKEND_URL);
    if (!origin) return json(503, "The backend isn't configured for this site.", "BACKEND_NOT_CONFIGURED");
    try {
      return await fetch(toBackend(request, origin));
    } catch {
      return json(502, "We couldn't reach the server. Try again in a minute.", "BACKEND_UNREACHABLE");
    }
  },
};

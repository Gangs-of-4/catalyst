/**
 * The one way pages talk to the backend (contracts.md §6).
 *
 * - Paths are relative `/api/...`: the Vite dev proxy locally, the Vercel rewrite in production
 *   (ADR-0041, ADR-0042). Never a hard-coded backend URL.
 * - Every write carries `X-Requested-With: catalyst` (the backend's CSRF check).
 * - The session cookie is HttpOnly; the browser sends it, pages never read it.
 * - Errors become an `ApiError` whose `detail` is one plain sentence a page can show as-is.
 */

export type ApiErrorBody = {
  detail: string;
  code: string;
  fields?: Record<string, string>;
  alternatives?: unknown[];
};

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  /** One plain sentence to show the user as-is (same as `message`). */
  readonly detail: string;
  readonly fields: Record<string, string>;
  readonly alternatives: unknown[];

  constructor(status: number, body: ApiErrorBody) {
    super(body.detail);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.detail = body.detail;
    this.fields = body.fields ?? {};
    this.alternatives = body.alternatives ?? [];
  }
}

type Method = "GET" | "POST" | "PUT" | "DELETE";

export type ApiOptions = {
  method?: Method;
  /** JSON-serialisable body for writes. */
  body?: unknown;
  signal?: AbortSignal;
};

export const NETWORK_ERROR: ApiErrorBody = {
  code: "NETWORK",
  detail: "Can't reach Catalyst right now. Check your internet and try again.",
};

const GENERIC: Record<number, ApiErrorBody> = {
  401: { code: "UNAUTHENTICATED", detail: "Please log in to continue." },
  403: { code: "FORBIDDEN", detail: "That request wasn't allowed. Reload the page and try again." },
  404: { code: "NOT_FOUND", detail: "We couldn't find that." },
};
const INTERNAL: ApiErrorBody = {
  code: "INTERNAL",
  detail: "Something went wrong on our side. Please try again in a moment.",
};

type Listener = () => void;
const troubleListeners = new Set<Listener>();

/** Subscribe to connection trouble (network failure, or a 5xx not sent by the backend). Returns an unsubscribe function. */
export function onConnectionTrouble(listener: Listener): () => void {
  troubleListeners.add(listener);
  return () => troubleListeners.delete(listener);
}

function reportTrouble() {
  troubleListeners.forEach((l) => l());
}

function isErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as ApiErrorBody).detail === "string" &&
    typeof (value as ApiErrorBody).code === "string"
  );
}

export async function api<T>(path: string, { method = "GET", body, signal }: ApiOptions = {}): Promise<T> {
  if (!path.startsWith("/api/")) {
    throw new Error(`api() takes a relative /api/ path, got "${path}"`);
  }
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") headers["X-Requested-With"] = "catalyst";
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "same-origin",
      signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    reportTrouble();
    throw new ApiError(0, NETWORK_ERROR);
  }

  if (res.status === 204) return undefined as T;
  const data: unknown = await res.json().catch(() => undefined);

  if (!res.ok) {
    // A 5xx without our JSON error body came from the forwarding (Vercel's rewrite, Vite's dev proxy),
    // not from the backend, so the backend isn't reachable. The backend's own errors, like the
    // deliberate 503 VOICE_NOT_CONFIGURED or a 500 INTERNAL, always carry the body.
    if (res.status >= 500 && !isErrorBody(data)) reportTrouble();
    if (isErrorBody(data)) throw new ApiError(res.status, data);
    throw new ApiError(res.status, GENERIC[res.status] ?? INTERNAL);
  }
  return data as T;
}

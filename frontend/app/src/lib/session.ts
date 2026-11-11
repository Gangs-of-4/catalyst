/**
 * The logged-in owner (contracts.md §6). The session cookie is HttpOnly, so pages never see it; they
 * ask the backend who is logged in.
 */
import { api } from "@/lib/api";

export type Me = {
  user: { name: string; email: string };
  business: {
    name: string;
    template: string;
    public_id: string;
    labels: Partial<Record<"resource" | "resource_plural" | "contact" | "booking" | "tenant", string>>;
  };
};

export type LoginResponse = { public_id: string; template: string };

export const getMe = (signal?: AbortSignal) => api<Me>("/api/me", { signal });

export const login = (email: string, password: string) =>
  api<LoginResponse>("/api/login", { method: "POST", body: { email: email.trim(), password } });

export const logout = () => api<{ ok: boolean }>("/api/logout", { method: "POST" });

/**
 * Where to go after logging in. Only same-app paths are allowed, so a crafted `?next=` link can't
 * send the owner to another site.
 */
export function safeNext(next: string | null, fallback = "/home"): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return fallback;
  return next;
}

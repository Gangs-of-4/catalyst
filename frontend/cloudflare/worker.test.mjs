// Tests for the Worker (ADR-0043). Run from frontend/: node cloudflare/worker.test.mjs
import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import worker, { backendOrigin, isForwarded } from "./worker.js";

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

const assets = { fetch: async (req) => new Response(`asset ${new URL(req.url).pathname}`) };
const env = { ASSETS: assets, BACKEND_URL: "https://backend.example.com/" };

test("only /api/* and /healthz are forwarded", () => {
  assert.equal(isForwarded("/api/me"), true);
  assert.equal(isForwarded("/healthz"), true);
  assert.equal(isForwarded("/desk"), false);
  assert.equal(isForwarded("/apifoo"), false);
});

test("BACKEND_URL must be a bare https origin", () => {
  assert.equal(backendOrigin("https://backend.example.com/"), "https://backend.example.com");
  assert.equal(backendOrigin("http://backend.example.com"), "");
  assert.equal(backendOrigin("https://backend.example.com/api"), "");
  assert.equal(backendOrigin(undefined), "");
});

test("pages are served from the static assets", async () => {
  globalThis.fetch = async () => assert.fail("pages must not reach the backend");
  const res = await worker.fetch(new Request("https://site.example/settings"), env);
  assert.equal(await res.text(), "asset /settings");
});

test("an API call goes to the backend with its method, query, headers and body, and comes back unchanged", async () => {
  let seen;
  globalThis.fetch = async (req) => {
    seen = { url: req.url, method: req.method, csrf: req.headers.get("x-requested-with"), cookie: req.headers.get("cookie"), host: req.headers.get("host"), redirect: req.redirect, body: await req.text() };
    const headers = new Headers({ "Content-Type": "application/json" });
    headers.append("Set-Cookie", "catalyst_session=abc; HttpOnly; Secure; SameSite=Lax; Path=/");
    return new Response('{"ok":true}', { status: 201, headers });
  };
  const req = new Request("https://site.example/api/login?next=%2Fdesk", {
    method: "POST",
    headers: { "X-Requested-With": "catalyst", Cookie: "a=1", Host: "site.example", "Content-Type": "application/json" },
    body: '{"email":"owner@example.com"}',
  });
  const res = await worker.fetch(req, env);
  assert.equal(seen.url, "https://backend.example.com/api/login?next=%2Fdesk");
  assert.equal(seen.method, "POST");
  assert.equal(seen.csrf, "catalyst");
  assert.equal(seen.cookie, "a=1");
  assert.notEqual(seen.host, "site.example");
  assert.equal(seen.redirect, "manual");
  assert.equal(seen.body, '{"email":"owner@example.com"}');
  assert.equal(res.status, 201);
  assert.match(res.headers.get("set-cookie"), /catalyst_session=abc; HttpOnly/);
});

test("a missing backend URL or an unreachable backend gives a JSON error the app can show", async () => {
  let res = await worker.fetch(new Request("https://site.example/healthz"), { ASSETS: assets });
  assert.equal(res.status, 503);
  assert.equal((await res.json()).code, "BACKEND_NOT_CONFIGURED");
  globalThis.fetch = async () => {
    throw new TypeError("network down");
  };
  res = await worker.fetch(new Request("https://site.example/api/me"), env);
  assert.equal(res.status, 502);
  assert.equal((await res.json()).code, "BACKEND_UNREACHABLE");
});

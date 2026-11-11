import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { backendUrl, withBackendRewrites } from "../../configure-vercel.mjs";

const base = {
  cleanUrls: true,
  rewrites: [
    { source: "/signup", destination: "/app.html" },
    { source: "/styleguide", destination: "/app.html" },
  ],
};

describe("configure-vercel", () => {
  it("puts the backend rewrites first so they win over page rewrites", () => {
    const out = withBackendRewrites(base, "https://api.example.com");
    expect(out.rewrites.slice(0, 2)).toEqual([
      { source: "/api/:path*", destination: "https://api.example.com/api/:path*" },
      { source: "/healthz", destination: "https://api.example.com/healthz" },
    ]);
    expect(out.rewrites).toHaveLength(4);
    expect(out.cleanUrls).toBe(true);
  });

  it("is idempotent and leaves no backend rewrite without a URL", () => {
    const once = withBackendRewrites(base, "https://api.example.com");
    expect(withBackendRewrites(once, "https://api.example.com")).toEqual(once);
    expect(withBackendRewrites(once, "").rewrites).toEqual(base.rewrites);
  });

  it("reads the URL from the env, or from the file `vercel pull` writes", () => {
    expect(backendUrl({ NEXT_PUBLIC_API_URL: "https://api.example.com/" }, [])).toBe("https://api.example.com");
    const dir = mkdtempSync(join(tmpdir(), "vercel-env-"));
    const file = join(dir, ".env.production.local");
    writeFileSync(file, 'VERCEL="1"\nNEXT_PUBLIC_API_URL="https://api.example.com"\n');
    expect(backendUrl({}, [file])).toBe("https://api.example.com");
    expect(backendUrl({}, [join(dir, "missing")])).toBe("");
  });

  it("refuses anything but an https origin", () => {
    for (const bad of ["http://api.example.com", "https://api.example.com/v1", "api.example.com"]) {
      expect(() => backendUrl({ NEXT_PUBLIC_API_URL: bad }, [])).toThrow(/https/);
    }
  });
});

// WCAG 2.2 AA contrast check for the design tokens (frontend/DESIGN.md §1).
// Reads the hex values from src/index.css so the check can't drift from the real tokens.
// Usage: npm run check:contrast   (exits 1 if any pair fails)
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../src/index.css", import.meta.url), "utf8");
const root = css.match(/:root\s*{([\s\S]*?)}/)?.[1] ?? "";
const tokens = Object.fromEntries([...root.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})/g)].map((m) => [m[1], m[2]]));

// [foreground token, background token, minimum ratio]. 4.5 = body text, 3.0 = UI boundaries.
const PAIRS = [
  ["foreground", "background", 4.5],
  ["body", "background", 4.5],
  ["muted-foreground", "background", 4.5],
  ["muted-foreground", "muted", 4.5],
  ["muted-foreground", "surface-soft", 4.5],
  ["foreground", "muted", 4.5],
  ["primary-foreground", "primary", 4.5],
  ["destructive", "background", 4.5],
  ["destructive-foreground", "destructive", 4.5],
  ["destructive-text", "destructive-soft", 4.5],
  ["live", "background", 4.5],
  ["live-text", "live-soft", 4.5],
  ["success", "background", 4.5],
  ["success-text", "success-soft", 4.5],
  ["input", "background", 3.0],
  ["ring", "background", 3.0],
];

function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

let failed = 0;
for (const [fg, bg, min] of PAIRS) {
  if (!tokens[fg] || !tokens[bg]) {
    console.log(`MISSING  --${fg} or --${bg} in src/index.css`);
    failed++;
    continue;
  }
  const r = ratio(tokens[fg], tokens[bg]);
  const ok = r >= min;
  if (!ok) failed++;
  console.log(`${ok ? "ok  " : "FAIL"}  ${fg} on ${bg}: ${r.toFixed(2)} (needs ${min})`);
}
if (failed) {
  console.log(`\n${failed} pair(s) fail WCAG AA.`);
  process.exit(1);
}
console.log("\nAll pairs pass WCAG AA.");

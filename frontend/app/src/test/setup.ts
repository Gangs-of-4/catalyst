// Vitest setup (jsdom). Globals are off, so unmount rendered components after each test ourselves.
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// jsdom has no layout, so scrolling APIs are missing; pages call them after submit.
Element.prototype.scrollIntoView = () => {};
window.scrollTo = () => {};
// Radix measures its controls with ResizeObserver, which jsdom doesn't have.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

afterEach(() => cleanup());

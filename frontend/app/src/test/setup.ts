// Vitest setup (jsdom). Globals are off, so unmount rendered components after each test ourselves.
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());

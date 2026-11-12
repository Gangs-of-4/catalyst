import { describe, expect, it } from "vitest";

import { vapiClass } from "./voice";

class FakeVapi {}

describe("vapiClass", () => {
  it("takes the class from an ES module default", () => {
    expect(vapiClass({ default: FakeVapi })).toBe(FakeVapi);
  });

  it("takes it from a CommonJS default wrapped once more (the production build)", () => {
    expect(vapiClass({ default: { default: FakeVapi, __esModule: true } })).toBe(FakeVapi);
  });

  it("says so in plain words when there is no class", () => {
    expect(() => vapiClass({ default: {} })).toThrow("The voice library didn't load");
  });
});

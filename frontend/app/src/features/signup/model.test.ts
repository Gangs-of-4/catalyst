import { describe, expect, it } from "vitest";

import { CLINIC, filledClinic, WHOLESALE } from "@/test/fixtures";

import {
  errorsForStep,
  firstErrorStep,
  initialForm,
  normalizeMobile,
  remapErrors,
  stepOf,
  switchTemplate,
  toPayload,
  validate,
} from "./model";

describe("initialForm", () => {
  it("prefills hours, closed days and the template section from vertical.yaml defaults", () => {
    const f = initialForm(CLINIC);
    expect(f.business.template).toBe("clinic");
    expect(f.business.hours).toEqual([
      { start: "10:00", end: "14:00" },
      { start: "17:00", end: "20:00" },
    ]);
    expect(f.business.closed_weekdays).toEqual([6]);
    expect(f.bookings.services).toEqual([{ name: "Consultation", fee: "₹300" }]);
    expect(f.bookings.slot_min).toBe(15);
    expect(f.bookings.emergency_instruction).toContain("108");
  });
});

describe("switchTemplate", () => {
  it("keeps what both templates share and resets the template-specific parts", () => {
    const f = filledClinic();
    f.instructions = "Pehle Hindi mein baat karo.";
    const w = switchTemplate(f, WHOLESALE);
    expect(w.business.template).toBe("wholesale");
    expect(w.user.email).toBe("owner@example.com");
    expect(w.business.name).toBe("Example Dental");
    expect(w.business.hours).toEqual([{ start: "09:30", end: "19:30" }]);
    expect(w.bookings.doctors).toEqual([{ name: "" }]);
    expect(w.instructions).toBe("Pehle Hindi mein baat karo.");
  });
});

describe("normalizeMobile", () => {
  it.each([
    ["90000 00001", "+919000000001"],
    ["090000 00001", "+919000000001"],
    ["+91 90000-00001", "+919000000001"],
    ["919000000001", "+919000000001"],
  ])("%s → %s", (raw, want) => expect(normalizeMobile(raw)).toBe(want));

  it.each(["", "12345", "50000 00001", "900000000"])("rejects %j", (raw) => expect(normalizeMobile(raw)).toBeNull());
});

describe("validate", () => {
  it("passes a complete form", () => {
    expect(validate(filledClinic(), CLINIC)).toEqual({});
  });

  it("uses the API's field paths, so server errors land on the same inputs", () => {
    const f = initialForm(CLINIC);
    f.business.hours = [{ start: "14:00", end: "10:00" }];
    f.bookings.services = [{ name: "X-ray", fee: "" }];
    expect(Object.keys(validate(f, CLINIC)).sort()).toEqual(
      [
        "business.address",
        "business.consent",
        "business.hours.0",
        "business.name",
        "business.owner_whatsapp",
        "details.doctors",
        "details.services.0.fee",
        "user.email",
        "user.name",
        "user.password",
      ].sort(),
    );
  });

  it("skips the bookings section for an orders template", () => {
    const f = switchTemplate(filledClinic(), WHOLESALE);
    expect(validate(f, WHOLESALE)).toEqual({});
  });

  it("limits the instructions to 500 characters", () => {
    const f = filledClinic();
    f.instructions = "x".repeat(501);
    expect(validate(f, CLINIC)).toHaveProperty("instructions");
  });
});

describe("toPayload", () => {
  it("builds the contracts §6 body and drops blank optional rows", () => {
    const f = filledClinic();
    f.bookings.doctors = [{ name: "" }, { name: " Doctor A " }];
    f.bookings.services = [{ name: "", fee: "" }, { name: "Cleaning", fee: "₹800" }];
    f.faqs = [{ q: "Is there parking?", a: "Yes." }, { q: "", a: "" }];
    f.business.closed_weekdays = [6, 0];
    const { body, rowMaps } = toPayload(f, CLINIC);
    expect(body.business).toMatchObject({
      template: "clinic",
      hours: [
        ["10:00", "14:00"],
        ["17:00", "20:00"],
      ],
      closed_weekdays: [0, 6],
      owner_whatsapp: "+919000000001",
      consent: true,
    });
    expect(body.details).toEqual({
      doctors: [{ name: "Doctor A" }],
      services: [{ name: "Cleaning", fee: "₹800" }],
      slot_min: 15,
      emergency_instruction: "Go to the nearest hospital emergency or call 108.",
    });
    expect(body.faqs).toEqual([{ q: "Is there parking?", a: "Yes." }]);
    expect(rowMaps).toEqual({ "details.doctors": [1], "details.services": [1], faqs: [0] });
  });

  it("sends the orders section for an orders template", () => {
    const f = switchTemplate(filledClinic(), WHOLESALE);
    f.orders = { min_order: "₹2,000", delivery_area: "Within the city" };
    expect(toPayload(f, WHOLESALE).body.details).toEqual({ min_order: "₹2,000", delivery_area: "Within the city" });
  });
});

describe("remapErrors", () => {
  it("moves server row indexes back to the form rows behind them", () => {
    const fields = {
      "details.services.0.fee": "Please fill in fee.",
      "details.doctors.1.name": "Please fill in name.",
      "user.email": "That email already has an account.",
    };
    const maps = { "details.doctors": [0, 2], "details.services": [3], faqs: [] };
    expect(remapErrors(fields, maps)).toEqual({
      "details.services.3.fee": "Please fill in fee.",
      "details.doctors.2.name": "Please fill in name.",
      "user.email": "That email already has an account.",
    });
  });
});

describe("steps", () => {
  it("puts each error key on the screen that shows its input", () => {
    expect(stepOf("user.email")).toBe(1);
    expect(stepOf("business.hours.0")).toBe(2);
    expect(stepOf("business.owner_whatsapp")).toBe(2);
    expect(stepOf("business.consent")).toBe(3);
    expect(stepOf("details.doctors.0.name")).toBe(3);
    expect(stepOf("faqs.1.q")).toBe(3);
    expect(stepOf("instructions")).toBe(3);
  });

  it("finds the earliest step with an error and filters errors per step", () => {
    const errors = { "details.doctors": "Add one.", "business.name": "Fill it.", "user.email": "Bad." };
    expect(firstErrorStep(errors)).toBe(1);
    expect(firstErrorStep({})).toBeUndefined();
    expect(errorsForStep(errors, 2)).toEqual({ "business.name": "Fill it." });
  });
});

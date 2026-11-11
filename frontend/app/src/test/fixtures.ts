// Shared test data. Fictional only (CLAUDE.md rule 6): "Doctor A", example.com, a 90000 number.
import { initialForm, type SignupForm, type Template } from "@/features/signup/model";

export const CLINIC: Template = {
  template: "clinic",
  label: "Clinic",
  labels: { resource: "Doctor", resource_plural: "Doctors", booking: "Appointment", tenant: "Clinic" },
  modules: ["bookings"],
  defaults: {
    slot_min: 15,
    sessions: [
      ["10:00", "14:00"],
      ["17:00", "20:00"],
    ],
    closed_weekdays: [6],
    services: [{ name: "Consultation", fee: "₹300" }],
    emergency_instruction: "Go to the nearest hospital emergency or call 108.",
  },
  has_voice: true,
};

export const WHOLESALE: Template = {
  template: "wholesale",
  label: "Distributor",
  labels: { resource: "Salesperson", booking: "Order", tenant: "Distributor" },
  modules: ["orders"],
  defaults: { sessions: [["09:30", "19:30"]], closed_weekdays: [6], min_order: "", delivery_area: "" },
  has_voice: false,
};

/** A complete, valid clinic form with fictional data only. */
export function filledClinic(): SignupForm {
  const f = initialForm(CLINIC);
  f.user = { name: "Test Owner", email: "owner@example.com", password: "long enough" };
  f.business = { ...f.business, name: "Example Dental", address: "1 Test Road", owner_whatsapp: "90000 00001", consent: true };
  f.bookings.doctors = [{ name: "Doctor A" }];
  return f;
}


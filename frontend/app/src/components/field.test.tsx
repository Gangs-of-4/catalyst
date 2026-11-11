import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Field } from "./field";
import { Input } from "./ui/input";

describe("<Field>", () => {
  it("links the label, hint and error to the control", () => {
    render(
      <Field label="Email" hint="We'll never share it." error="Enter an email like name@example.com.">
        <Input />
      </Field>,
    );
    const input = screen.getByLabelText("Email");
    expect(input.getAttribute("aria-invalid")).toBe("true");
    const describedBy = input.getAttribute("aria-describedby")!.split(" ");
    const texts = describedBy.map((id) => document.getElementById(id)?.textContent);
    expect(texts).toEqual(["We'll never share it.", "Enter an email like name@example.com."]);
    expect(screen.getByRole("alert").textContent).toBe("Enter an email like name@example.com.");
  });

  it("is valid and quiet without an error", () => {
    render(
      <Field label="Landmark" optional>
        <Input />
      </Field>,
    );
    const input = screen.getByLabelText(/Landmark/);
    expect(input.hasAttribute("aria-invalid")).toBe(false);
    expect(input.hasAttribute("aria-describedby")).toBe(false);
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

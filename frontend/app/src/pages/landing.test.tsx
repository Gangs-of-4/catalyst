import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { LandingPage } from "./landing";

const renderLanding = () =>
  render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>,
  );

describe("<LandingPage>", () => {
  it("leads with one promise and the two main actions", () => {
    renderLanding();
    expect(screen.getByRole("heading", { level: 1, name: "Never miss a patient call." })).toBeTruthy();
    const signups = screen.getAllByRole("link", { name: "Set up your front desk" });
    expect(signups.length).toBeGreaterThan(0);
    signups.forEach((a) => expect(a.getAttribute("href")).toBe("/signup"));
    expect(screen.getByRole("link", { name: /Try a demo call/ }).getAttribute("href")).toBe("/demo/clinic");
  });

  it("lets existing owners log in from the header and the closing section", () => {
    renderLanding();
    const header = screen.getByRole("banner");
    expect(within(header).getByRole("link", { name: "Log in" }).getAttribute("href")).toBe("/login");
    expect(screen.getByRole("link", { name: "I already have an account" }).getAttribute("href")).toBe("/login");
  });

  it("explains how it works and the safety rules", () => {
    renderLanding();
    expect(screen.getByRole("heading", { name: "How it works" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "1. Set up in about two minutes" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Medical questions go to a person" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Clinics" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Wholesale distributors" })).toBeTruthy();
  });
});

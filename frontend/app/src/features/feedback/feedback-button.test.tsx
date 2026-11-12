import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FeedbackButton } from "./feedback-button";

// Fictional only (CLAUDE.md rule 6).
const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function mockApi(handler: (init?: RequestInit) => Response) {
  const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
    if (String(input) !== "/api/feedback") throw new Error(`unexpected fetch ${String(input)}`);
    return handler(init);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function openDialog() {
  fireEvent.click(screen.getByRole("button", { name: /Feedback/ }));
  return screen.findByRole("dialog", { name: "Send feedback" });
}

afterEach(() => vi.unstubAllGlobals());

describe("<FeedbackButton>", () => {
  it("sends the message with the type, name and role", async () => {
    const fetchMock = mockApi(() => json(200, { id: 1, saved: true }));
    render(<FeedbackButton defaultName="Test Owner" />);
    const dialog = await openDialog();
    expect((within(dialog).getByLabelText("Your name") as HTMLInputElement).value).toBe("Test Owner");
    expect((within(dialog).getByLabelText("You are") as HTMLInputElement).value).toBe("Owner");
    fireEvent.click(within(dialog).getByRole("radio", { name: "I wish it could…" }));
    fireEvent.change(within(dialog).getByLabelText("Your message"), { target: { value: "Show tomorrow's bookings on the home page." } });
    fireEvent.click(within(dialog).getByRole("button", { name: /Send/ }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    const [, init] = fetchMock.mock.calls[0]!;
    expect(init?.headers).toMatchObject({ "X-Requested-With": "catalyst" });
    expect(JSON.parse(String(init!.body))).toEqual({
      person_name: "Test Owner",
      person_role: "Owner",
      text: "Show tomorrow's bookings on the home page.",
      type: "feature",
    });
  });

  it("asks for what it's about and a message before sending", async () => {
    const fetchMock = mockApi(() => json(200, { id: 1, saved: true }));
    render(<FeedbackButton defaultName="Test Owner" />);
    const dialog = await openDialog();
    fireEvent.click(within(dialog).getByRole("button", { name: /Send/ }));
    expect(await within(dialog).findByText("Pick what it's about.")).toBeTruthy();
    expect(within(dialog).getByText("Tell us a little more.")).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps the message when the sheet is closed and opened again", async () => {
    mockApi(() => json(200, { id: 1, saved: true }));
    render(<FeedbackButton defaultName="Test Owner" />);
    let dialog = await openDialog();
    fireEvent.change(within(dialog).getByLabelText("Your message"), { target: { value: "Half written" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Back" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    dialog = await openDialog();
    expect((within(dialog).getByLabelText("Your message") as HTMLTextAreaElement).value).toBe("Half written");
  });

  it("keeps the message and says so when logged out", async () => {
    mockApi(() => json(401, { detail: "Please log in to continue.", code: "UNAUTHENTICATED" }));
    render(<FeedbackButton defaultName="Test Owner" />);
    const dialog = await openDialog();
    fireEvent.click(within(dialog).getByRole("radio", { name: "Something isn't working" }));
    fireEvent.change(within(dialog).getByLabelText("Your message"), { target: { value: "The desk froze." } });
    fireEvent.click(within(dialog).getByRole("button", { name: /Send/ }));
    expect(await within(dialog).findByText(/You've been logged out/)).toBeTruthy();
    expect((within(dialog).getByLabelText("Your message") as HTMLTextAreaElement).value).toBe("The desk froze.");
  });
});

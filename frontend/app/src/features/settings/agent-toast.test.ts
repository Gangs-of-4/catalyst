import { afterEach, describe, expect, it, vi } from "vitest";

const success = vi.fn();
const warning = vi.fn();
vi.mock("sonner", () => ({ toast: { success: (t: string) => success(t), warning: (t: string) => warning(t) } }));

const { agentToast } = await import("./agent-toast");

// The backend's own sentences (api/sync.py MESSAGES).
const UPDATED = "Saved. The agent has been updated.";
const FAILED = "Saved, but updating the agent failed. Try saving again in a minute.";

afterEach(() => {
  success.mockReset();
  warning.mockReset();
});

describe("agentToast", () => {
  it("shows a plain save as the backend words it, with no second 'Saved.'", () => {
    agentToast(UPDATED);
    expect(success).toHaveBeenCalledWith(UPDATED);
  });

  it("puts another lead-in in place of 'Saved.'", () => {
    agentToast(UPDATED, "Added.");
    expect(success).toHaveBeenCalledWith("Added. The agent has been updated.");
  });

  it("warns, not celebrates, when the agent update failed", () => {
    agentToast(FAILED);
    expect(warning).toHaveBeenCalledWith(FAILED);
    agentToast(FAILED, "Back to the earlier version.");
    expect(warning).toHaveBeenLastCalledWith("Back to the earlier version. Updating the agent failed. Try saving again in a minute.");
    expect(success).not.toHaveBeenCalled();
  });
});

import { describe, expect, it, vi } from "vitest";
import { RECEIPT_TIMEOUT_MS, intakeController, intakeErrorMessage } from "./intake";

describe("intakeErrorMessage", () => {
  it("falls back to a generic message with no response (network error / offline)", () => {
    expect(intakeErrorMessage()).toBe("Couldn't read that — try again");
  });

  it("maps 413 to a photo-size message", () => {
    expect(intakeErrorMessage(new Response(null, { status: 413 }))).toBe("Photo too large");
  });

  it("maps 415 to a file-type message", () => {
    expect(intakeErrorMessage(new Response(null, { status: 415 }))).toBe("Use a JPG or PNG");
  });

  it("maps 429 with a Retry-After header to a minutes estimate, rounded up", () => {
    const response = new Response(null, { status: 429, headers: { "Retry-After": "125" } });
    expect(intakeErrorMessage(response)).toBe("Too many scans — try again in 3 min");
  });

  it("maps 429 with no Retry-After to a generic retry-later message", () => {
    expect(intakeErrorMessage(new Response(null, { status: 429 }))).toBe("Too many scans — try again later");
  });

  it("maps 429 with a non-numeric Retry-After the same as no header", () => {
    const response = new Response(null, { status: 429, headers: { "Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT" } });
    expect(intakeErrorMessage(response)).toBe("Too many scans — try again later");
  });

  it("falls back to the generic message for any other status", () => {
    expect(intakeErrorMessage(new Response(null, { status: 500 }))).toBe("Couldn't read that — try again");
  });

  it("gives voice its own advice for silence (422) and a speech-service outage (502)", () => {
    expect(intakeErrorMessage(new Response(null, { status: 422 }), "voice")).toBe(
      "Didn't catch that — hold the button and speak",
    );
    expect(intakeErrorMessage(new Response(null, { status: 502 }), "voice")).toBe(
      "Voice isn't working right now — type it instead",
    );
  });

  it("keeps the generic message for 422/502 from photo and typed intake", () => {
    expect(intakeErrorMessage(new Response(null, { status: 422 }))).toBe("Couldn't read that — try again");
    expect(intakeErrorMessage(new Response(null, { status: 502 }))).toBe("Couldn't read that — try again");
  });

  it("uses the shared messages for other voice statuses and network errors", () => {
    expect(intakeErrorMessage(new Response(null, { status: 429 }), "voice")).toBe("Too many scans — try again later");
    expect(intakeErrorMessage(undefined, "voice")).toBe("Couldn't read that — try again");
  });
});

describe("intakeController", () => {
  it("starts with an unaborted signal and wasCancelled() false", () => {
    const ctl = intakeController();
    expect(ctl.signal.aborted).toBe(false);
    expect(ctl.wasCancelled()).toBe(false);
    ctl.done();
  });

  it("cancel() aborts the signal and marks wasCancelled() true", () => {
    const ctl = intakeController();
    ctl.cancel();
    expect(ctl.signal.aborted).toBe(true);
    expect(ctl.wasCancelled()).toBe(true);
    ctl.done();
  });

  it("aborts on its own after the timeout, without wasCancelled() being true", () => {
    vi.useFakeTimers();
    const ctl = intakeController();
    expect(ctl.signal.aborted).toBe(false);
    vi.advanceTimersByTime(30_000);
    expect(ctl.signal.aborted).toBe(true);
    expect(ctl.wasCancelled()).toBe(false); // a timeout isn't a user cancel
    vi.useRealTimers();
  });

  it("takes a longer timeout for slow calls: a receipt outlives the usual 30 s but not its own limit", () => {
    vi.useFakeTimers();
    const ctl = intakeController(RECEIPT_TIMEOUT_MS);
    vi.advanceTimersByTime(30_000);
    expect(ctl.signal.aborted).toBe(false); // still waiting: the model may just be busy
    vi.advanceTimersByTime(RECEIPT_TIMEOUT_MS - 30_000);
    expect(ctl.signal.aborted).toBe(true);
    expect(ctl.wasCancelled()).toBe(false);
    vi.useRealTimers();
  });

  it("done() prevents the timeout from firing", () => {
    vi.useFakeTimers();
    const ctl = intakeController();
    ctl.done();
    vi.advanceTimersByTime(30_000);
    expect(ctl.signal.aborted).toBe(false);
    vi.useRealTimers();
  });
});

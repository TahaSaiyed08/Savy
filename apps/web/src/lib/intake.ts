// Shared by every /intake/* caller (list/page.tsx, TypeOrSaySheet): a message per HTTP status, and an
// AbortController wrapper so a stalled call can be cancelled from the UI and times out after 30s instead
// of hanging forever. Pass "voice" from /intake/voice: its 422 means silence and its 502 means the speech
// service is down, which need different advice than the same statuses from photo or typed intake.
export function intakeErrorMessage(response?: Response, source?: "voice"): string {
  if (source === "voice") {
    if (response?.status === 422) return "Didn't catch that — hold the button and speak";
    if (response?.status === 502) return "Voice isn't working right now — type it instead";
  }
  switch (response?.status) {
    case 413:
      return "Photo too large";
    case 415:
      return "Use a JPG or PNG";
    case 429: {
      const retryAfter = Number(response.headers.get("Retry-After"));
      const minutes = Number.isFinite(retryAfter) && retryAfter > 0 ? Math.ceil(retryAfter / 60) : null;
      return minutes ? `Too many scans — try again in ${minutes} min` : "Too many scans — try again later";
    }
    default:
      return "Couldn't read that — try again";
  }
}

const TIMEOUT_MS = 30_000;
/** A receipt is a whole page read by a model: usually 10 to 20 s, longer when the model is busy and a fallback steps in. */
export const RECEIPT_TIMEOUT_MS = 120_000;

/** One per intake call. `cancel()` is for the user (Cancel button); the 30s timer fires on its own. */
export function intakeController(timeoutMs = TIMEOUT_MS) {
  const controller = new AbortController();
  let userCancelled = false;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return {
    signal: controller.signal,
    cancel: () => {
      userCancelled = true;
      controller.abort();
    },
    /** True only for an explicit cancel(), not the timeout — lets callers stay silent on a real cancel. */
    wasCancelled: () => userCancelled,
    done: () => clearTimeout(timer),
  };
}

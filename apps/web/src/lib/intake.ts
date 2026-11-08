// Shared by every /intake/* caller (list/page.tsx, TypeOrSaySheet): a message per HTTP status, and an
// AbortController wrapper so a stalled call can be cancelled from the UI and times out after 30s instead
// of hanging forever.
export function intakeErrorMessage(response?: Response): string {
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

/** One per intake call. `cancel()` is for the user (Cancel button); the 30s timer fires on its own. */
export function intakeController() {
  const controller = new AbortController();
  let userCancelled = false;
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
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

import { beforeEach, describe, expect, it } from "vitest";
import {
  cookieValue,
  matchesPasscode,
  PASSCODE_HEADER,
  passcodeProblem,
  recordFailure,
  resetFailuresForTests,
  tooManyFailures,
  unlocked,
  visitorIp,
} from "./demo-gate";

const PASS = "correct horse battery";

describe("visitorIp", () => {
  it("trusts cf-connecting-ip from the tunnel over any client-supplied x-forwarded-for", () => {
    const h = new Headers({ "cf-connecting-ip": "203.0.113.7", "x-forwarded-for": "1.2.3.4, 198.51.100.2" });
    expect(visitorIp(h)).toBe("203.0.113.7");
  });

  it("otherwise uses the hop Next.js recorded (the right-most x-forwarded-for entry)", () => {
    expect(visitorIp(new Headers({ "x-forwarded-for": "10.0.0.5" }))).toBe("10.0.0.5");
    expect(visitorIp(new Headers({ "x-forwarded-for": "1.2.3.4, 10.0.0.5" }))).toBe("10.0.0.5");
  });

  it("never returns an empty key", () => {
    expect(visitorIp(new Headers())).toBe("unknown");
    expect(visitorIp(new Headers({ "cf-connecting-ip": "  " }))).toBe("unknown");
  });
});

describe("passcode gate", () => {
  it("fails closed when DEMO_PASSCODE is unset or too short", () => {
    expect(passcodeProblem(undefined)).toMatch(/Set DEMO_PASSCODE/);
    expect(passcodeProblem("short")).toMatch(/at least 8/);
    expect(passcodeProblem(PASS)).toBeNull();
  });

  it("accepts the unlock cookie, which is a hash and not the passcode", () => {
    const cookie = cookieValue(PASS);
    expect(cookie).toMatch(/^[0-9a-f]{64}$/);
    expect(cookie).not.toContain(PASS);
    expect(unlocked(new Headers(), cookie, PASS)).toBe(true);
    expect(unlocked(new Headers(), cookieValue("another passcode"), PASS)).toBe(false);
    expect(unlocked(new Headers(), "not-hex", PASS)).toBe(false);
    expect(unlocked(new Headers(), undefined, PASS)).toBe(false);
  });

  it("accepts the passcode header for scripts", () => {
    expect(unlocked(new Headers({ [PASSCODE_HEADER]: PASS }), undefined, PASS)).toBe(true);
    expect(unlocked(new Headers({ [PASSCODE_HEADER]: "wrong guess" }), undefined, PASS)).toBe(false);
  });

  it("compares any length without throwing", () => {
    expect(matchesPasscode("", PASS)).toBe(false);
    expect(matchesPasscode(PASS + PASS, PASS)).toBe(false);
    expect(matchesPasscode(PASS, PASS)).toBe(true);
  });
});

describe("wrong-passcode limiter", () => {
  beforeEach(() => resetFailuresForTests());

  it("blocks an IP after 10 failures in 15 minutes, per IP, then forgets", () => {
    const t = 1_000_000;
    for (let n = 0; n < 10; n++) recordFailure("203.0.113.7", t);
    expect(tooManyFailures("203.0.113.7", t)).toBe(true);
    expect(tooManyFailures("198.51.100.2", t)).toBe(false);
    expect(tooManyFailures("203.0.113.7", t + 15 * 60_000)).toBe(false);
  });
});

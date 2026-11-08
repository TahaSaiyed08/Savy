// Server-only helpers for the Databricks App proxy (src/app/api/[...path]/route.ts) and /unlock: who the visitor
// is, and whether they've entered the demo passcode. The proxy adds the laptop's Databricks token to every call,
// so behind a public tunnel it must not serve strangers.
import { createHash, timingSafeEqual } from "node:crypto";

export const PASSCODE_COOKIE = "rd_demo";
export const PASSCODE_HEADER = "x-demo-passcode";
export const MIN_PASSCODE_LENGTH = 8;

/**
 * The visitor's IP, for the API's per-IP upload limit. Cloudflare sets cf-connecting-ip on every tunnelled request
 * and overwrites any value the client sent, so it's trusted when present. Otherwise this is the address Next.js
 * recorded: it fills x-forwarded-for from the socket only when the client sent none, so a direct (non-tunnel)
 * client can still spoof it. The passcode gate limits who can reach the proxy at all.
 */
export function visitorIp(headers: Headers): string {
  const cf = headers.get("cf-connecting-ip")?.trim();
  if (cf) return cf;
  const hops = (headers.get("x-forwarded-for") ?? "").split(",").map((h) => h.trim()).filter(Boolean);
  return hops.at(-1) ?? "unknown";
}

function digest(value: string): Buffer {
  return createHash("sha256").update(`realdeal-demo:${value}`).digest();
}

/** The unlock cookie holds a hash of the passcode, never the passcode itself. */
export function cookieValue(passcode: string): string {
  return digest(passcode).toString("hex");
}

/** Constant-time: equal-length digests, so timing doesn't reveal how much of a guess was right. */
export function matchesPasscode(given: string, passcode: string): boolean {
  return timingSafeEqual(digest(given), digest(passcode));
}

export function unlocked(headers: Headers, cookie: string | undefined, passcode: string): boolean {
  const header = headers.get(PASSCODE_HEADER);
  if (header !== null && matchesPasscode(header, passcode)) return true;
  if (!cookie || !/^[0-9a-f]{64}$/.test(cookie)) return false;
  return timingSafeEqual(Buffer.from(cookie, "hex"), digest(passcode));
}

// Wrong-passcode attempts per visitor IP, so the passcode can't be brute-forced through the tunnel.
const WINDOW_MS = 15 * 60_000;
const MAX_FAILURES = 10;
const MAX_TRACKED = 10_000; // bound memory if many IPs guess
const failures = new Map<string, number[]>();

function recent(ip: string, now: number): number[] {
  const kept = (failures.get(ip) ?? []).filter((t) => now - t < WINDOW_MS);
  if (kept.length) failures.set(ip, kept);
  else failures.delete(ip);
  return kept;
}

export function tooManyFailures(ip: string, now = Date.now()): boolean {
  return recent(ip, now).length >= MAX_FAILURES;
}

export function recordFailure(ip: string, now = Date.now()): void {
  if (failures.size >= MAX_TRACKED && !failures.has(ip)) failures.delete(failures.keys().next().value!);
  failures.set(ip, [...recent(ip, now), now]);
}

/** Why the proxy can't serve anyone yet, or null if DEMO_PASSCODE is usable. Fails closed when unset. */
export function passcodeProblem(passcode: string | undefined): string | null {
  if (!passcode) return "Set DEMO_PASSCODE in apps/web/.env.local to use the Databricks App proxy";
  if (passcode.length < MIN_PASSCODE_LENGTH) return `DEMO_PASSCODE must be at least ${MIN_PASSCODE_LENGTH} characters`;
  return null;
}

export function resetFailuresForTests(): void {
  failures.clear();
}

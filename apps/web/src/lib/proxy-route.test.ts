// The Databricks App proxy (src/app/api/[...path]/route.ts) with the CLI and the app faked: the passcode gate,
// the token, and which headers reach the app.
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { cookieValue, PASSCODE_HEADER, resetFailuresForTests } from "./demo-gate";

const PASS = "correct horse battery";

vi.mock("node:child_process", () => ({
  execFile: (_cmd: string, _args: string[], _opts: unknown, cb: (e: Error | null, out: string, err: string) => void) =>
    cb(null, JSON.stringify({ access_token: "oauth-from-cli", expiry: new Date(Date.now() + 3_600_000).toISOString() }), ""),
}));

let upstream: { url: string; headers: Headers }[];

async function loadProxy(passcode: string | undefined) {
  vi.resetModules();
  vi.stubEnv("DATABRICKS_APP_URL", "https://realdeal-api.example.databricksapps.com");
  vi.stubEnv("DEMO_PASSCODE", passcode ?? "");
  return (await import("../app/api/[...path]/route")).GET;
}

function call(get: Awaited<ReturnType<typeof loadProxy>>, headers: Record<string, string>) {
  const req = new NextRequest("http://localhost:3000/api/items?x=1", { headers });
  return get(req, { params: Promise.resolve({ path: ["items"] }) });
}

beforeEach(() => {
  upstream = [];
  resetFailuresForTests();
  vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => {
    upstream.push({ url, headers: new Headers(init.headers) });
    return new Response("[]", { status: 200, headers: { "content-type": "application/json" } });
  }));
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("Databricks App proxy", () => {
  it("refuses everyone while DEMO_PASSCODE is unset", async () => {
    const r = await call(await loadProxy(undefined), {});
    expect(r.status).toBe(503);
    expect(upstream).toEqual([]);
  });

  it("refuses a device that hasn't unlocked, without calling the app", async () => {
    const r = await call(await loadProxy(PASS), { "cf-connecting-ip": "203.0.113.7" });
    expect(r.status).toBe(401);
    expect(upstream).toEqual([]);
  });

  it("forwards an unlocked request with the token and the real visitor IP, dropping spoofable headers", async () => {
    const r = await call(await loadProxy(PASS), {
      cookie: `rd_demo=${cookieValue(PASS)}`,
      "cf-connecting-ip": "203.0.113.7",
      "x-forwarded-for": "1.2.3.4",
      "x-real-ip": "1.2.3.4",
      forwarded: "for=1.2.3.4",
      "x-user-id": "00000000-0000-0000-0000-000000000001",
    });
    expect(r.status).toBe(200);
    const [{ url, headers }] = upstream;
    expect(url).toBe("https://realdeal-api.example.databricksapps.com/items?x=1");
    expect(headers.get("authorization")).toBe("Bearer oauth-from-cli");
    expect(headers.get("x-forwarded-for")).toBe("203.0.113.7");
    for (const dropped of ["x-real-ip", "forwarded", "cf-connecting-ip", "cookie", PASSCODE_HEADER]) {
      expect(headers.has(dropped)).toBe(false);
    }
    expect(headers.get("x-user-id")).toBe("00000000-0000-0000-0000-000000000001");
  });

  it("accepts the passcode header but doesn't forward it", async () => {
    const r = await call(await loadProxy(PASS), { [PASSCODE_HEADER]: PASS, "x-forwarded-for": "10.0.0.5" });
    expect(r.status).toBe(200);
    expect(upstream[0].headers.has(PASSCODE_HEADER)).toBe(false);
    expect(upstream[0].headers.get("x-forwarded-for")).toBe("10.0.0.5");
  });

  it("rate-limits wrong passcode headers per visitor", async () => {
    const get = await loadProxy(PASS);
    const wrong = { [PASSCODE_HEADER]: "wrong guess", "cf-connecting-ip": "203.0.113.9" };
    for (let n = 0; n < 10; n++) expect((await call(get, wrong)).status).toBe(401);
    expect((await call(get, wrong)).status).toBe(429);
    expect(upstream).toEqual([]);
  });
});

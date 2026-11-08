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

describe("Databricks App proxy upload cap", () => {
  const MB = 1024 * 1024;
  const unlockedHeaders = { [PASSCODE_HEADER]: PASS };

  async function post(body: BodyInit, headers: Record<string, string>) {
    vi.resetModules();
    vi.stubEnv("DATABRICKS_APP_URL", "https://realdeal-api.example.databricksapps.com");
    vi.stubEnv("DEMO_PASSCODE", PASS);
    const { POST } = await import("../app/api/[...path]/route");
    const init = { method: "POST", body, headers: { ...unlockedHeaders, ...headers }, duplex: "half" };
    const req = new NextRequest("http://localhost:3000/api/intake/receipt",
                                init as ConstructorParameters<typeof NextRequest>[1]);
    return POST(req, { params: Promise.resolve({ path: ["intake", "receipt"] }) });
  }

  function stream(totalBytes: number, chunk = MB): ReadableStream<Uint8Array> {
    let sent = 0;
    return new ReadableStream({
      pull(c) {
        if (sent >= totalBytes) return c.close();
        const n = Math.min(chunk, totalBytes - sent);
        sent += n;
        c.enqueue(new Uint8Array(n));
      },
    });
  }

  it("refuses a declared oversized body before reading it", async () => {
    const r = await post(stream(1), { "content-length": String(12 * MB) });
    expect(r.status).toBe(413);
    expect(upstream).toEqual([]);
  });

  it("stops reading an undeclared stream once it passes the cap", async () => {
    let pulled = 0;
    const big = stream(50 * MB);
    const counted = big.pipeThrough(new TransformStream({ transform(c, ctl) { pulled += c.byteLength; ctl.enqueue(c); } }));
    const r = await post(counted, {});
    expect(r.status).toBe(413);
    expect(upstream).toEqual([]);
    expect(pulled).toBeLessThan(15 * MB); // gave up near 11 MB, never read all 50 MB
  });

  it("forwards a normal upload unchanged", async () => {
    const photo = new Uint8Array(2 * MB).map((_, i) => i % 251);
    vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => {
      upstream.push({ url, headers: new Headers(init.headers) });
      expect(Buffer.from(init.body as ArrayBuffer).equals(Buffer.from(photo))).toBe(true);
      return new Response("{}", { status: 200, headers: { "content-type": "application/json" } });
    }));
    const r = await post(photo, { "content-type": "application/octet-stream" });
    expect(r.status).toBe(200);
    expect(upstream).toHaveLength(1);
  });
});

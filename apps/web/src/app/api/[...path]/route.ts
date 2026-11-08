// Proxy for /api/* when the API is hosted as a Databricks App (DATABRICKS_APP_URL is set; next.config.ts then
// drops its plain rewrite). Databricks Apps only accept OAuth tokens, so this asks the Databricks CLI for one
// (`databricks auth login --host <workspace>` once on this machine; the CLI refreshes it) and adds it server-side.
// The token never reaches the browser. Because every call carries that token, the proxy only serves devices that
// unlocked the demo with DEMO_PASSCODE (/unlock), and refuses everyone while DEMO_PASSCODE is unset.
import { execFile } from "node:child_process";
import type { NextRequest } from "next/server";

import {
  PASSCODE_COOKIE,
  PASSCODE_HEADER,
  passcodeProblem,
  recordFailure,
  tooManyFailures,
  unlocked,
  visitorIp,
} from "@/lib/demo-gate";

const APP_URL = process.env.DATABRICKS_APP_URL?.replace(/\/+$/, "");
const HOST = process.env.DATABRICKS_HOST;
// Hop-by-hop and recomputed headers aren't forwarded; Authorization is ours to set. Client-supplied forwarding
// headers are dropped too and x-forwarded-for is rebuilt from the real visitor IP, or a caller could pick the
// "IP" the API's per-IP upload limit counts against. The passcode header stays on this side.
const DROP = new Set([
  "host", "connection", "content-length", "authorization", "cookie", "accept-encoding",
  "x-forwarded-for", "x-real-ip", "forwarded", "cf-connecting-ip", PASSCODE_HEADER,
]);
const REFRESH_EARLY_MS = 5 * 60_000;

let cached: { token: string; expires: number } | null = null;
let pending: Promise<string> | null = null;

function cliToken(): Promise<string> {
  return new Promise((resolve, reject) => {
    const args = ["auth", "token", ...(HOST ? ["--host", HOST] : [])];
    execFile("databricks", args, { timeout: 20_000 }, (err, stdout, stderr) => {
      if (err) return reject(new Error(`databricks auth token failed: ${stderr || err.message}`));
      try {
        const out = JSON.parse(stdout) as { access_token: string; expiry?: string };
        const expiry = out.expiry ? Date.parse(out.expiry) : NaN;
        cached = { token: out.access_token, expires: Number.isFinite(expiry) ? expiry : Date.now() + 30 * 60_000 };
        resolve(out.access_token);
      } catch {
        reject(new Error("databricks auth token returned unexpected output"));
      }
    });
  });
}

async function token(): Promise<string> {
  if (cached && cached.expires - REFRESH_EARLY_MS > Date.now()) return cached.token;
  pending ??= cliToken().finally(() => (pending = null)); // one CLI call however many requests are waiting
  return pending;
}

// The API rejects uploads over 10 MB; allow 1 MB more for multipart framing. Checked while reading, so an
// oversized body (declared or not) is refused without the laptop ever holding all of it in memory.
const MAX_BODY_BYTES = 11 * 1024 * 1024;

/** The request body, or null once it's known to exceed MAX_BODY_BYTES. */
async function readCapped(req: NextRequest): Promise<ArrayBuffer | null> {
  const declared = Number(req.headers.get("content-length"));
  if (Number.isFinite(declared) && declared > MAX_BODY_BYTES) return null;
  if (!req.body) return new ArrayBuffer(0);
  const reader = req.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > MAX_BODY_BYTES) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  const out = new Uint8Array(total);
  let at = 0;
  for (const c of chunks) {
    out.set(c, at);
    at += c.byteLength;
  }
  return out.buffer;
}

async function proxy(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  if (!APP_URL) return Response.json({ detail: "DATABRICKS_APP_URL is not set" }, { status: 500 });
  const passcode = process.env.DEMO_PASSCODE;
  const problem = passcodeProblem(passcode);
  if (problem) return Response.json({ detail: problem }, { status: 503 });
  const ip = visitorIp(req.headers);
  // Before the passcode is checked: a locked-out guesser must get 429 even for the right one.
  if (req.headers.has(PASSCODE_HEADER) && tooManyFailures(ip)) {
    return Response.json({ detail: "Too many wrong passcodes" }, { status: 429 });
  }
  if (!unlocked(req.headers, req.cookies.get(PASSCODE_COOKIE)?.value, passcode!)) {
    if (req.headers.has(PASSCODE_HEADER)) recordFailure(ip);
    return Response.json({ detail: "Locked: open /unlock on this device and enter the demo passcode" },
                         { status: 401 });
  }
  // Read the body before anything else costs work, and never past the cap (see readCapped).
  const body = req.method === "GET" || req.method === "HEAD" ? undefined : await readCapped(req);
  if (body === null) return Response.json({ detail: "upload over 10 MB" }, { status: 413 });
  const { path } = await params;
  let auth: string;
  try {
    auth = await token();
  } catch (e) {
    console.error(e);
    return Response.json({ detail: "Couldn't get a Databricks token; run `databricks auth login`" }, { status: 502 });
  }
  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!DROP.has(key.toLowerCase())) headers.set(key, value);
  });
  headers.set("x-forwarded-for", ip); // the API's per-IP limit counts the real visitor, not the laptop
  headers.set("authorization", `Bearer ${auth}`);
  const upstream = await fetch(`${APP_URL}/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`, {
    method: req.method,
    headers,
    body,
    redirect: "manual",
  });
  if (upstream.status === 401 || upstream.status === 403) cached = null; // re-ask the CLI next time
  const out = new Headers();
  for (const key of ["content-type", "retry-after", "cache-control"]) {
    const value = upstream.headers.get(key);
    if (value) out.set(key, value);
  }
  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export { proxy as DELETE, proxy as GET, proxy as PATCH, proxy as POST, proxy as PUT };

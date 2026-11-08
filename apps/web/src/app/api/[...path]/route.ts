// Proxy for /api/* when the API is hosted as a Databricks App (DATABRICKS_APP_URL is set; next.config.ts then
// drops its plain rewrite). Databricks Apps only accept OAuth tokens, so this asks the Databricks CLI for one
// (`databricks auth login --host <workspace>` once on this machine; the CLI refreshes it) and adds it server-side.
// The token never reaches the browser.
import { execFile } from "node:child_process";
import type { NextRequest } from "next/server";

const APP_URL = process.env.DATABRICKS_APP_URL?.replace(/\/+$/, "");
const HOST = process.env.DATABRICKS_HOST;
// Hop-by-hop and recomputed headers aren't forwarded; Authorization is ours to set.
const DROP = new Set(["host", "connection", "content-length", "authorization", "cookie", "accept-encoding"]);
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

async function proxy(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  if (!APP_URL) return Response.json({ detail: "DATABRICKS_APP_URL is not set" }, { status: 500 });
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
  headers.set("authorization", `Bearer ${auth}`);
  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const upstream = await fetch(`${APP_URL}/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`, {
    method: req.method,
    headers,
    body: hasBody ? await req.arrayBuffer() : undefined, // uploads are capped at 10 MB by the API
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

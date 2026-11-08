// /unlock: enter DEMO_PASSCODE once per device to use the Databricks App proxy (src/app/api/[...path]/route.ts).
// Sets an HttpOnly cookie holding a hash of the passcode. Only exists in proxy mode (DATABRICKS_APP_URL set).
import type { NextRequest } from "next/server";

import {
  cookieValue,
  matchesPasscode,
  PASSCODE_COOKIE,
  passcodeProblem,
  recordFailure,
  tooManyFailures,
  visitorIp,
} from "@/lib/demo-gate";

const COOKIE_MAX_AGE_S = 7 * 24 * 3600;

function page(message = "", status = 200): Response {
  // message is always one of the fixed strings below, never user input
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Unlock Savy</title>
<style>body{font:17px -apple-system,system-ui,sans-serif;max-width:22rem;margin:20vh auto;padding:0 1rem}
input,button{font:inherit;width:100%;box-sizing:border-box;min-height:44px;margin-top:.75rem;padding:.5rem}
p{color:#c00}</style></head><body><h1>Savy demo</h1>
<form method="post"><label for="p">Demo passcode</label>
<input id="p" name="passcode" type="password" autocomplete="current-password" required autofocus>
<button type="submit">Unlock</button></form>${message ? `<p role="alert">${message}</p>` : ""}</body></html>`;
  return new Response(html, { status, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } });
}

function notFound(): Response {
  return new Response("Not found", { status: 404 });
}

export function GET() {
  return process.env.DATABRICKS_APP_URL ? page() : notFound();
}

export async function POST(req: NextRequest) {
  if (!process.env.DATABRICKS_APP_URL) return notFound();
  const passcode = process.env.DEMO_PASSCODE;
  const problem = passcodeProblem(passcode);
  if (problem) return page(problem, 503);
  const ip = visitorIp(req.headers);
  if (tooManyFailures(ip)) return page("Too many wrong passcodes. Try again in 15 minutes.", 429);
  const given = String((await req.formData()).get("passcode") ?? "");
  if (!matchesPasscode(given, passcode!)) {
    recordFailure(ip);
    return page("Wrong passcode.", 401);
  }
  // Secure whenever the page came over https (the tunnel); plain http://localhost still works for the laptop.
  const https = req.headers.has("cf-connecting-ip") || req.headers.get("x-forwarded-proto") === "https"
    || req.nextUrl.protocol === "https:";
  const cookie = `${PASSCODE_COOKIE}=${cookieValue(passcode!)}; Path=/; Max-Age=${COOKIE_MAX_AGE_S}; HttpOnly; `
    + `SameSite=Lax${https ? "; Secure" : ""}`;
  return new Response(null, { status: 303, headers: { location: "/", "set-cookie": cookie } });
}

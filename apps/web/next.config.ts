import type { NextConfig } from "next";

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";
// Set when the API runs as a Databricks App: src/app/api/[...path]/route.ts proxies instead, adding a token.
const DATABRICKS_APP_URL = process.env.DATABRICKS_APP_URL;

const nextConfig: NextConfig = {
  // The proxy below gives up on a slow API after 30 s by default, which cuts off the calls that are slow by nature: a
  // Genie answer (15 to 30 s, minutes when the warehouse is waking up) and a receipt scan. The API has its own limits
  // (Genie 150 s, Gemini under 100 s), so this only has to be longer than those.
  experimental: { proxyTimeout: 180_000 },
  devIndicators: false, // the floating badge covers the tab bar on phones
  // `make tunnel` serves dev over https://*.trycloudflare.com (campus Wi-Fi blocks phone-to-laptop traffic).
  allowedDevOrigins: ["*.trycloudflare.com"],
  // Same-origin proxy: the browser calls /api/*, so phones on the LAN or a tunnel need no CORS setup.
  async rewrites() {
    return DATABRICKS_APP_URL ? [] : [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;

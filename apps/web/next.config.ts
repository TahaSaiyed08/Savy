import type { NextConfig } from "next";

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";
// Set when the API runs as a Databricks App: src/app/api/[...path]/route.ts proxies instead, adding a token.
const DATABRICKS_APP_URL = process.env.DATABRICKS_APP_URL;

const nextConfig: NextConfig = {
  devIndicators: false, // the floating badge covers the tab bar on phones
  // `make tunnel` serves dev over https://*.trycloudflare.com (campus Wi-Fi blocks phone-to-laptop traffic).
  allowedDevOrigins: ["*.trycloudflare.com"],
  // Same-origin proxy: the browser calls /api/*, so phones on the LAN or a tunnel need no CORS setup.
  async rewrites() {
    return DATABRICKS_APP_URL ? [] : [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;

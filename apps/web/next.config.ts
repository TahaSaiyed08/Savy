import type { NextConfig } from "next";

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  devIndicators: false, // the floating badge covers the tab bar on phones
  // Same-origin proxy: the browser calls /api/*, so phones on the LAN or a tunnel need no CORS setup.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;

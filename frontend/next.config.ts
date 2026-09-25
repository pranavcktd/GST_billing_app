import type { NextConfig } from "next";

// The browser always calls /api on the same address it opened the app on (localhost, LAN IP or domain);
// Next.js forwards those calls to the FastAPI backend. Other PCs then only need port 3000, and the
// backend can stay private. Set API_PROXY_TARGET to the backend URL when it runs elsewhere.
const API_TARGET = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_TARGET}/api/:path*` }];
  },
};

export default nextConfig;

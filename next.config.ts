import type { NextConfig } from "next";
import { networkInterfaces } from "node:os";

// The browser always calls /api on the same address it opened the app on (localhost, LAN IP or domain);
// Next.js forwards those calls to the FastAPI backend. Other PCs then only need port 3000, and the
// backend can stay private. Set API_PROXY_TARGET to the backend URL when it runs elsewhere.
const API_TARGET = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000";

// Development server only: let phones / other PCs on the same network load the app's scripts when they open
// http://<this-PC-IP>:3000 (Next.js blocks other origins in dev by default). Uses this PC's own LAN addresses.
const lanAddresses = Object.values(networkInterfaces())
  .flat()
  .filter((a) => a && a.family === "IPv4" && !a.internal)
  .map((a) => a!.address);

const nextConfig: NextConfig = {
  allowedDevOrigins: [...lanAddresses, "192.168.*.*", "10.*.*.*"],
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_TARGET}/api/:path*` }];
  },
};

export default nextConfig;

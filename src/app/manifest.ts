import type { MetadataRoute } from "next";
import { APP_NAME, BY_LINE, DESCRIPTION } from "@/lib/brand";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: `${APP_NAME} ${BY_LINE}`,
    short_name: APP_NAME,
    description: DESCRIPTION,
    start_url: "/dashboard",
    display: "standalone",
    background_color: "#fbf8f4",
    theme_color: "#b8532a",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
    ],
    shortcuts: [
      { name: "New sale invoice", url: "/v/sales/new", icons: [{ src: "/icon-192.png", sizes: "192x192" }] },
      { name: "POS billing", url: "/pos", icons: [{ src: "/icon-192.png", sizes: "192x192" }] },
    ],
  };
}

import type { MetadataRoute } from "next";
import { APP_NAME, BY_LINE, DESCRIPTION } from "@/lib/brand";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: `${APP_NAME} ${BY_LINE}`,
    short_name: APP_NAME,
    description: DESCRIPTION,
    start_url: "/dashboard",
    display: "standalone",
    background_color: "#f6f7f9",
    theme_color: "#1f65bb",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
  };
}

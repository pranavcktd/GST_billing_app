import { SiteContentPage } from "@/components/SiteContent";

export const metadata = { title: "Disclaimer" };

/** Text edited in Admin → Website (built-in text: backend/app/content/disclaimer.md). */
export default function Page() {
  return <SiteContentPage slug="disclaimer" />;
}

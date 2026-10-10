import { SiteContentPage } from "@/components/SiteContent";

export const metadata = { title: "Security & Data Retention" };

/** Text edited in Admin → Website (built-in text: backend/app/content/security.md). */
export default function Page() {
  return <SiteContentPage slug="security" />;
}

import { SiteContentPage } from "@/components/SiteContent";

export const metadata = { title: "Privacy Policy" };

/** Text edited in Admin → Website (built-in text: backend/app/content/privacy.md). */
export default function Page() {
  return <SiteContentPage slug="privacy" />;
}

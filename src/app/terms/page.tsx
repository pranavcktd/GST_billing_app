import { SiteContentPage } from "@/components/SiteContent";

export const metadata = { title: "Terms of Service" };

/** Text edited in Admin → Website (built-in text: backend/app/content/terms.md). */
export default function Page() {
  return <SiteContentPage slug="terms" />;
}

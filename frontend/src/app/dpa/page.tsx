import { SiteContentPage } from "@/components/SiteContent";

export const metadata = { title: "Data Processing Addendum" };

/** Text edited in Admin → Website (built-in text: backend/app/content/dpa.md). */
export default function Page() {
  return <SiteContentPage slug="dpa" />;
}

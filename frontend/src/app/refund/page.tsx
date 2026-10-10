import { SiteContentPage } from "@/components/SiteContent";

export const metadata = { title: "Refund & Cancellation Policy" };

/** Text edited in Admin → Website (built-in text: backend/app/content/refund.md). */
export default function Page() {
  return <SiteContentPage slug="refund" />;
}

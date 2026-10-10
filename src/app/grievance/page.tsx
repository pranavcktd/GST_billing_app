import { SiteContentPage } from "@/components/SiteContent";

export const metadata = { title: "Grievance Redressal" };

/** Text edited in Admin → Website (built-in text: backend/app/content/grievance.md). */
export default function Page() {
  return <SiteContentPage slug="grievance" />;
}

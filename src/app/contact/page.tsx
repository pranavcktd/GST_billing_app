import { SiteContentPage } from "@/components/SiteContent";

export const metadata = { title: "Contact" };

/** Text edited in Admin → Website (built-in text: backend/app/content/contact.md). */
export default function Page() {
  return <SiteContentPage slug="contact" />;
}

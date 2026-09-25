import { COMPANY, LegalPage } from "@/components/LegalPage";

export const metadata = { title: "Contact — GST Billing" };

export default function Contact() {
  return (
    <LegalPage title="Contact us" updated="September 2026">
      <p>We are happy to help with setup, billing questions or anything else.</p>
      <div className="rounded-xl border border-gray-200 p-5">
        <div className="font-semibold text-gray-900">{COMPANY.name}</div>
        <div>E-mail: <a className="text-brand-600 hover:underline" href={`mailto:${COMPANY.email}`}>{COMPANY.email}</a></div>
        <div>{COMPANY.phone}</div>
        <div>{COMPANY.address}</div>
      </div>
      <p>Support hours: Monday–Saturday, 10:00–19:00 IST.</p>
    </LegalPage>
  );
}

import { LegalPage } from "@/components/LegalPage";
import Link from "next/link";
import { Company, IfLegal, Legal } from "@/lib/config";

export const metadata = { title: "Contact" };

export default function Contact() {
  return (
    <LegalPage title="Contact us" updated="10 October 2026">
      <p>We are happy to help with setup, billing questions or anything else.</p>
      <div className="rounded-xl border border-gray-200 p-5">
        <div className="font-semibold text-gray-900"><Company field="name" /></div>
        <div>E-mail: <Company field="email" link /></div>
        <div><Company field="phone" /></div>
        <div><Company field="address" /></div>
      </div>
      <p>Support hours: Monday–Saturday, 10:00–19:00 IST.</p>
      <h2>Grievance Officer</h2>
      <p>
        <Legal field="grievance_officer" fallback="Grievance Officer" /> · <Legal field="grievance_email" />
        <IfLegal field="grievance_phone"> · <Legal field="grievance_phone" /></IfLegal> —{" "}
        <Link href="/grievance" className="text-brand-600 underline">how complaints and privacy requests are handled</Link>.
      </p>
    </LegalPage>
  );
}

import Link from "next/link";
import { LegalPage } from "@/components/LegalPage";
import { BrandName, Company, IfLegal, Legal } from "@/lib/config";

export const metadata = { title: "Data Processing Addendum" };

const L = ({ href, children }: { href: string; children: React.ReactNode }) => <Link href={href} className="text-brand-600 underline">{children}</Link>;

export default function Dpa() {
  return (
    <LegalPage title="Data Processing Addendum" updated="10 October 2026" intro={<>
      This addendum forms part of the <L href="/terms">Terms of Service</L>. It applies to personal data inside your Business Data,
      for which <b>you are the data fiduciary</b> and <Company field="name" /> is <b>your data processor</b> under section 8 of the
      Digital Personal Data Protection Act, 2023.
    </>}>
      <h2>1. Instructions and purpose</h2>
      <p>
        We process that personal data only on your documented instructions — which are given by your use and configuration of
        <BrandName /> and by these terms — and only to provide the Service: creating invoices and documents, keeping accounting,
        inventory and payroll records, generating e-invoices and e-way bills, preparing return data, sending messages you ask us to
        send, backups and support.
      </p>

      <h2>2. No other use</h2>
      <p>We will not sell, rent or disclose your Business Data, or use it for our own marketing, profiling or to train AI models. We may use aggregated statistics from which no person or business can be identified.</p>

      <h2>3. Your responsibilities as data fiduciary</h2>
      <ul>
        <li>Having a lawful basis (consent or a legitimate use) and giving any notice required before you enter personal data of others;</li>
        <li>Responding to requests of your data principals (we will help, clause 6);</li>
        <li>Informing the Data Protection Board of India and affected individuals of a personal data breach, where the law requires (we will give you the information you need, clause 5).</li>
      </ul>

      <h2>4. Security safeguards</h2>
      <p>We maintain the technical and organisational measures on the <L href="/security">Security &amp; Data Retention</L> page, including encryption in transit, encryption of keys and certificates, role-based access, two-factor sign-in, an unalterable audit trail and daily backups. Our personnel with access to data are bound by confidentiality and access is limited to what their role needs.</p>

      <h2>5. Personal data breaches</h2>
      <p>
        If we become aware of a personal data breach affecting your data on our systems, we will inform the business owner by e-mail
        without undue delay — aiming for within 48 hours of confirming it — with what we know about its nature, the data affected, the
        likely consequences and the steps taken. We keep a register of security incidents.
      </p>

      <h2>6. Assistance</h2>
      <p>We will provide reasonable help, through the features of the Service (export, correction, audit trail) and on request, so that you can answer data-principal requests, carry out audits and meet your obligations.</p>

      <h2>7. Sub-processors</h2>
      <p>You authorise us to use the service providers listed in section 4 of the <L href="/privacy">Privacy Policy</L>. We impose data-protection obligations on them and remain responsible for their performance. We will announce a new category of sub-processor in the app or by e-mail before it starts processing your data; you may object and, if we cannot address the objection, stop using the affected feature or close your account.</p>

      <h2>8. Location and transfers</h2>
      <p>
        <IfLegal field="data_location">Core databases and daily backups are hosted in <b><Legal field="data_location" /></b>. </IfLegal>
        Any processing outside India is done only as permitted under section 16 of the DPDP Act. If you are a company that must keep
        books of account and their backups on servers in India (Companies (Accounts) Rules 3(5)), check the hosting location on the
        Security page and keep your own backups as well.
      </p>

      <h2>9. Retention, return and deletion</h2>
      <p>
        On closure of your account you can download your data for 30 days. After that we delete your Business Data, except Statutory
        Records and audit trails that the law requires to be kept (CGST Act s.36 — 72 months; Companies Act s.128 — 8 years); these are
        retained securely and deleted when the period ends. Section 8(7)(b) of the DPDP Act permits this retention.
      </p>

      <h2>10. Information and audits</h2>
      <p>On reasonable written request we will provide information needed to demonstrate compliance with this addendum. On-site audits are by prior agreement, at your cost, no more than once a year, and subject to confidentiality and the security of other customers.</p>

      <h2>11. Liability</h2>
      <p>Each party’s liability under this addendum is subject to the limits in the Terms of Service.</p>
    </LegalPage>
  );
}

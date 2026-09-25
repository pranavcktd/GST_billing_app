import { LegalPage } from "@/components/LegalPage";
import { Company } from "@/lib/config";

export const metadata = { title: "Privacy Policy" };

export default function Privacy() {
  return (
    <LegalPage title="Privacy Policy" updated="September 2026">
      <p className="rounded-lg bg-amber-50 px-3 py-2 text-amber-900">Template — review against the Digital Personal Data Protection Act, 2023 with your legal advisor.</p>
      <h2>What we collect</h2>
      <ul>
        <li>Account details: name, e-mail, phone, business name, GSTIN and address.</li>
        <li>Business data you enter: invoices, parties, items, payments and related records.</li>
        <li>Technical data: sign-in times, IP addresses and device information for security and audit.</li>
        <li>Payment details are processed by our payment partner (Razorpay); we do not store card numbers.</li>
      </ul>
      <h2>How we use it</h2>
      <ul>
        <li>To provide and secure the Service, including audit trails and backups.</li>
        <li>To send service e-mails such as password resets and billing notices.</li>
        <li>We do not sell your data. Resellers who manage your subscription see your account details and usage counts, never your invoices or books.</li>
      </ul>
      <h2>Storage and security</h2>
      <p>Data is stored on secured cloud servers with encrypted connections, hashed passwords, optional two-factor sign-in and regular backups.</p>
      <h2>Your rights</h2>
      <p>You can access, correct, export or delete your data. Some records may be retained where the law requires (for example, GST record keeping for 72 months).</p>
      <h2>Contact / grievance officer</h2>
      <p><Company field="name" /> · <Company field="email" /></p>
    </LegalPage>
  );
}

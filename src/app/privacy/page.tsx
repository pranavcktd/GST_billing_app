import Link from "next/link";
import { LegalPage } from "@/components/LegalPage";
import { BrandName, Company, IfLegal, Legal } from "@/lib/config";

export const metadata = { title: "Privacy Policy" };

const L = ({ href, children }: { href: string; children: React.ReactNode }) => <Link href={href} className="text-brand-600 underline">{children}</Link>;

export default function Privacy() {
  return (
    <LegalPage title="Privacy Policy" updated="10 October 2026" intro={<>
      This policy explains how <Company field="name" /> handles personal data in <BrandName />, under the Digital Personal Data
      Protection Act, 2023 (“DPDP Act”) and the Information Technology Act, 2000 and its rules. <b>We do not sell personal data and
      do not use your business data for advertising or profiling.</b>
    </>}>
      <h2>1. Two roles</h2>
      <ul>
        <li><b>Your account data</b> (your name, e-mail, mobile, sign-in and subscription details): we decide how it is used, so for this we are the <b>data fiduciary</b>.</li>
        <li><b>Business Data you enter</b> (your customers’, suppliers’ and employees’ details inside invoices, ledgers, payroll and documents): the business using <BrandName /> is the data fiduciary and we are its <b>data processor</b>. We handle it only to provide the Service, under our <L href="/dpa">Data Processing Addendum</L>. Requests about that data should go to the business concerned; we will help them answer.</li>
      </ul>

      <h2>2. What we collect</h2>
      <table>
        <thead><tr><th>Data</th><th>Examples</th><th>Source</th></tr></thead>
        <tbody>
          <tr><td>Account</td><td>Name, e-mail, mobile, password (stored only as a hash), WhatsApp number if linked, Google account e-mail and name if you sign in with Google</td><td>You</td></tr>
          <tr><td>Business profile</td><td>Business name, GSTIN, PAN, address, bank and UPI details, logo, signature, digital signature certificate</td><td>You; public GST records when you verify a GSTIN</td></tr>
          <tr><td>Business Data</td><td>Invoices, parties, items, payments, payroll, attendance, uploaded documents</td><td>You and your staff</td></tr>
          <tr><td>Security and usage</td><td>Sign-in times, IP address, device and browser, audit trail of changes, consents given</td><td>Automatically</td></tr>
          <tr><td>Payments</td><td>Plan, amount, payment reference — card / bank details are handled by our payment gateway and not stored by us</td><td>Razorpay</td></tr>
          <tr><td>Messages</td><td>One-time codes, e-mails and WhatsApp messages you ask us to send, and their delivery status</td><td>Our e-mail / WhatsApp providers</td></tr>
        </tbody>
      </table>

      <h2>3. Why we use it (purposes)</h2>
      <ul>
        <li>To create and secure your account, verify you (one-time codes, two-factor sign-in) and prevent fraud and misuse.</li>
        <li>To provide the Service: billing, tax computation, e-invoice / e-way bill generation, reports, reminders, backups and support.</li>
        <li>To meet our legal duties (tax, company and IT law, responding to lawful requests of authorities).</li>
        <li>To send service messages (security alerts, billing, changes to these policies). Marketing messages are sent only with your consent and you can opt out at any time.</li>
        <li>To improve the Service using aggregated, de-identified statistics only.</li>
      </ul>
      <p>We process personal data on the basis of your consent (given when you sign up and recorded with its version and time) and for the legitimate uses the DPDP Act allows, such as complying with law.</p>

      <h2>4. Who we share it with</h2>
      <p>Only with service providers who help us run the Service, under contracts that restrict their use of the data, and only as much as each needs:</p>
      <table>
        <thead><tr><th>Provider (category)</th><th>Why</th></tr></thead>
        <tbody>
          <tr><td>Cloud hosting and database</td><td>Running the Service and storing data and backups</td></tr>
          <tr><td>Image / document storage (Cloudinary, if your platform admin chooses it)</td><td>Storing logos, signatures, item photos and vault documents</td></tr>
          <tr><td>GST data / GSP providers (gstinapi.in and the licensed GSP it uses)</td><td>GSTIN verification, e-invoice (IRN), e-way bills, filing status</td></tr>
          <tr><td>Razorpay</td><td>Subscription payments; also the public IFSC lookup (only the IFSC code is sent)</td></tr>
          <tr><td>WhatsApp Business API provider (e.g. Spring Edge)</td><td>Sign-in codes, invoices and reminders you choose to send</td></tr>
          <tr><td>E-mail service</td><td>Sign-in codes, invoices, reminders, backups and notices</td></tr>
          <tr><td>Google</td><td>“Continue with Google”, if you use it</td></tr>
        </tbody>
      </table>
      <p>We may also disclose data when required by law or a valid order of a court or authority, or to protect the rights and safety of users and the Service. Resellers who manage a subscription see account and usage details, never invoices or books.</p>

      <h2>5. Where data is stored</h2>
      <p>
        <IfLegal field="data_location">Our database and backups are stored in <b><Legal field="data_location" /></b>. </IfLegal>
        Some providers listed above may process data outside India; transfers are made only as permitted under section 16 of the DPDP
        Act. See the <L href="/security">Security &amp; Data Retention</L> page for current details.
      </p>

      <h2>6. How long we keep it</h2>
      <table>
        <thead><tr><th>Data</th><th>Kept for</th></tr></thead>
        <tbody>
          <tr><td>Account data</td><td>While the account is open, then deleted within 90 days of closure, except where needed for the items below</td></tr>
          <tr><td>Tax invoices, books of account and their audit trail</td><td>At least 72 months from the due date of the annual GST return (CGST Act s.36) and 8 financial years (Companies Act s.128), as applicable — even if erasure is requested (DPDP Act s.8(7))</td></tr>
          <tr><td>Subscription invoices and payment records</td><td>8 financial years (tax and accounting law)</td></tr>
          <tr><td>Security logs and consent records</td><td>At least 1 year, and longer while needed to protect against or investigate misuse</td></tr>
          <tr><td>Backups</td><td>As described on the Security &amp; Data Retention page; they expire on a rolling basis</td></tr>
        </tbody>
      </table>

      <h2>7. Security</h2>
      <p>We use encrypted connections, hashed passwords, encrypted storage of keys and certificates, role-based access, two-factor sign-in, an audit trail that cannot be altered, and daily backups. Details are on the <L href="/security">Security &amp; Data Retention</L> page. No system is perfectly secure; if a breach affects your data we will inform you without undue delay.</p>

      <h2>8. Your rights</h2>
      <p>Under the DPDP Act you can:</p>
      <ul>
        <li><b>Access</b> a summary of your personal data and how it is used;</li>
        <li><b>Correct, complete or update</b> it;</li>
        <li><b>Erase</b> it, subject to the retention required by law (section 6 above);</li>
        <li><b>Withdraw consent</b> — this stops further processing based on consent but does not affect processing already done or required by law;</li>
        <li><b>Nominate</b> another person to exercise these rights in case of death or incapacity;</li>
        <li><b>Have a grievance redressed</b> by us, and then complain to the Data Protection Board of India.</li>
      </ul>
      <p>
        Use <b>Settings → Security → Your data &amp; privacy</b> in the app to download your data or raise a request, or write to the
        Grievance Officer below. We acknowledge requests within 24 hours and respond within 30 days (grievances within 15 days). We may
        need to verify your identity first.
      </p>

      <h2>9. Children</h2>
      <p>The Service is for businesses and is not meant for anyone under 18. We do not knowingly collect children’s personal data; businesses must not enter it without verifiable parental consent where the law requires.</p>

      <h2>10. Cookies and local storage</h2>
      <p>We use only what is needed to run the Service: your sign-in session and preferences are kept in your browser’s storage, and offline billing keeps a temporary copy of data on your device. We do not use advertising or third-party tracking cookies.</p>

      <h2>11. Changes</h2>
      <p>When we change this policy we update the date above and ask you to accept the new version in the app.</p>

      <h2>12. Grievance Officer / contact</h2>
      <p>
        <b><Legal field="grievance_officer" fallback="Grievance Officer" /></b>, <Company field="name" /><br />
        E-mail: <Legal field="grievance_email" /><IfLegal field="grievance_phone"> · Phone: <Legal field="grievance_phone" /></IfLegal><br />
        Address: <Company field="address" /><br />
        See <L href="/grievance">Grievance Redressal</L> for the process and timelines.
      </p>
    </LegalPage>
  );
}

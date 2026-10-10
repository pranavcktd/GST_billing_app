import Link from "next/link";
import { LegalPage } from "@/components/LegalPage";
import { BrandName, IfLegal, Legal } from "@/lib/config";

export const metadata = { title: "Security & Data Retention" };

export default function Security() {
  return (
    <LegalPage title="Security & Data Retention" updated="10 October 2026" intro={<>
      How <BrandName /> protects your data, how long data is kept, and what the platform does for the record-keeping rules of the
      GST law and the Companies Act. This page describes measures that are in place today.
    </>}>
      <h2>1. Protecting access</h2>
      <ul>
        <li>All traffic to the Service uses encrypted HTTPS (TLS) connections.</li>
        <li>Passwords are stored only as one-way hashes (bcrypt). Accounts lock for 15 minutes after repeated wrong passwords.</li>
        <li>Optional two-factor sign-in with an authenticator app; sign-in with a one-time code on WhatsApp or e-mail; “sign out everywhere”.</li>
        <li>Role-based permissions for staff, staff sign-in controls (devices, places and hours chosen by the owner), and a manager approval PIN for changes to older entries.</li>
        <li>API keys, portal passwords and digital signature certificates are encrypted in the database with an application key and are never sent back to browsers.</li>
      </ul>

      <h2>2. Records the law requires</h2>
      <ul>
        <li><b>No deletion of issued documents</b> — tax invoices and notes can only be cancelled or corrected by a credit / debit note; cancelled numbers stay in the series (CGST Rules 46, 53).</li>
        <li><b>Audit trail (edit log)</b> — every change to books of account is recorded with the values before and after, the user, the time and the IP address. It cannot be switched off, and the database itself refuses any change or deletion of it (Companies (Accounts) Rules 3(1)).</li>
        <li><b>HSN/SAC on invoices</b> — required on B2B invoices and notes (4 digits up to ₹5 crore turnover, 6 above, and also on B2C above ₹5 crore).</li>
        <li><b>“Clear data”</b> — only for test entries; blocked once documents are reported to the government or returns are filed; a backup is kept before anything is cleared.</li>
      </ul>

      <h2>3. Backups and hosting</h2>
      <ul>
        <li>Automatic daily backups of each business (the latest 7 are kept), manual backups whenever you want, and a full platform backup every day.</li>
        <li>You can download any backup, or an Excel copy of your data, at any time — and restore it.</li>
        <li><IfLegal field="data_location"><>Database and backups are hosted in <b><Legal field="data_location" /></b>.</></IfLegal>{" "}
          Companies must keep a backup of their books on servers in India (Companies (Accounts) Rules 3(5)); please also keep your own copies.</li>
      </ul>

      <h2>4. Retention schedule</h2>
      <table>
        <thead><tr><th>Data</th><th>Retention</th></tr></thead>
        <tbody>
          <tr><td>Invoices, notes, books of account, audit trail</td><td>At least 72 months from the annual-return due date (CGST s.36) / 8 financial years (Companies Act s.128)</td></tr>
          <tr><td>Backups taken before data was cleared</td><td>Kept; cannot be deleted by users</td></tr>
          <tr><td>Daily automatic backups</td><td>Rolling — latest 7</td></tr>
          <tr><td>One-time codes</td><td>Expire in 5–10 minutes; only a keyed hash is stored</td></tr>
          <tr><td>Account data after closure</td><td>Deleted within 90 days, except records required by law</td></tr>
        </tbody>
      </table>

      <h2>5. Incidents</h2>
      <p>We keep a register of security incidents. If an incident affects your data we notify the account owner by e-mail without undue delay so that you can meet your own duties under the DPDP Act. To report a vulnerability, write to <Legal field="grievance_email" /> — please do not test the Service without our written permission.</p>

      <h2>6. More</h2>
      <p>See the <Link href="/privacy" className="text-brand-600 underline">Privacy Policy</Link> and the <Link href="/dpa" className="text-brand-600 underline">Data Processing Addendum</Link>.</p>
    </LegalPage>
  );
}

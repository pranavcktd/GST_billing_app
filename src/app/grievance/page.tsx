import Link from "next/link";
import { LegalPage } from "@/components/LegalPage";
import { Company, IfLegal, Legal } from "@/lib/config";

export const metadata = { title: "Grievance Redressal" };

export default function Grievance() {
  return (
    <LegalPage title="Grievance Redressal" updated="10 October 2026" intro={<>
      How to raise a complaint, a privacy request or a concern about content or data on the platform, as required by the
      Information Technology (Intermediary Guidelines and Digital Media Ethics Code) Rules, 2021 and the Digital Personal Data
      Protection Act, 2023.
    </>}>
      <h2>Grievance Officer</h2>
      <p>
        <b><Legal field="grievance_officer" fallback="Grievance Officer" /></b>, <Company field="name" /><br />
        E-mail: <Legal field="grievance_email" /><IfLegal field="grievance_phone"><br />Phone: <Legal field="grievance_phone" /></IfLegal><br />
        Address: <Company field="address" />
      </p>

      <h2>How to raise it</h2>
      <ul>
        <li>In the app: <b>Settings → Security → Your data &amp; privacy</b> — choose access, correction, erasure, withdrawal of consent or a grievance. You get a reference number and can follow its status.</li>
        <li>Or e-mail the Grievance Officer with your registered e-mail, the business name and the details.</li>
      </ul>

      <h2>Timelines</h2>
      <ul>
        <li>Acknowledgement within 24 hours.</li>
        <li>Grievances resolved within 15 days; data-access, correction and erasure requests answered within 30 days.</li>
        <li>Where the request concerns data a business entered about you (for example as its customer or employee), we pass it to that business (the data fiduciary) and help it respond.</li>
      </ul>

      <h2>If you are not satisfied</h2>
      <p>You may complain to the Data Protection Board of India once the Board’s processes are available, after using this procedure. See also our <Link href="/privacy" className="text-brand-600 underline">Privacy Policy</Link>.</p>
    </LegalPage>
  );
}

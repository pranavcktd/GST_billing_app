import Link from "next/link";
import { LegalPage } from "@/components/LegalPage";
import { Company } from "@/lib/config";

export const metadata = { title: "Terms of Service" };

export default function Terms() {
  return (
    <LegalPage title="Terms of Service" updated="September 2026">
      <p className="rounded-lg bg-amber-50 px-3 py-2 text-amber-900">Template — have it reviewed by your legal advisor before going live.</p>
      <p>
        These terms govern your use of SmartHisab (the &quot;Service&quot;), provided by <Company field="name" /> (&quot;we&quot;, &quot;us&quot;).
        By creating an account or using the Service you agree to these terms and to our <Link href="/privacy" className="underline">Privacy Policy</Link> and{" "}
        <Link href="/disclaimer" className="underline">Disclaimer</Link>.
      </p>

      <h2>1. The Service</h2>
      <p>
        SmartHisab is online software for invoicing, inventory, accounting and preparing GST-related documents and reports from the data
        you enter. It is a tool to assist you; it does not provide tax, legal or accounting advice and does not file returns or make
        payments on your behalf.
      </p>

      <h2>2. Your responsibilities</h2>
      <ul>
        <li>You are responsible for the accuracy and completeness of the data you enter, including GST rates, HSN/SAC codes, party details and tax treatment.</li>
        <li>You are responsible for reviewing invoices, e-invoice / e-way bill data, reports and return files before issuing, uploading or filing them, and for meeting all statutory deadlines.</li>
        <li>You must use the Service lawfully and must not use it to create false or misleading documents.</li>
        <li>You are responsible for everything done through your account, including by staff you add, and for keeping passwords and two-factor devices secure.</li>
      </ul>

      <h2>3. Third-party services and data</h2>
      <p>
        Some features rely on third parties — for example GSTIN verification providers, GST Suvidha Providers (GSPs), payment gateways,
        e-mail and cloud hosting. Their availability and the accuracy of the data they return are outside our control. Information such
        as GSTIN details and the HSN/SAC directory is provided for convenience and should be checked by you.
      </p>

      <h2>4. Changes in law</h2>
      <p>
        Tax laws, rates, forms and file formats change. We make reasonable efforts to update the Service, but updates may not be
        immediate. You should always refer to official notifications and the GST portal.
      </p>

      <h2>5. Plans, trial and payment</h2>
      <ul>
        <li>Paid plans are billed in advance, monthly or yearly; applicable GST is added to the price.</li>
        <li>When a paid plan ends the account moves to the Free plan; your data is kept.</li>
        <li>Prices and plan features may change with 30 days&apos; notice; changes apply from your next renewal.</li>
        <li>Refunds follow our <Link href="/refund" className="underline">Refund &amp; Cancellation Policy</Link>.</li>
      </ul>

      <h2>6. Your data</h2>
      <p>
        You own your business data. We process it only to provide the Service, as described in the Privacy Policy. You can export or
        back up your data at any time. We recommend keeping your own copies of important records.
      </p>

      <h2>7. Availability</h2>
      <p>We aim for high availability but do not guarantee that the Service will be uninterrupted or error-free. Planned maintenance may occasionally be required.</p>

      <h2>8. Disclaimer of warranties</h2>
      <p>
        The Service is provided &quot;as is&quot; and &quot;as available&quot;. To the maximum extent permitted by law, we disclaim all warranties,
        express or implied, including that the Service or its output will be accurate, complete, or suitable for any particular
        statutory or regulatory purpose.
      </p>

      <h2>9. Limitation of liability</h2>
      <p>
        To the maximum extent permitted by law, we are not liable for any indirect, incidental, special or consequential loss, or for
        any tax, interest, penalty, late fee or loss of input tax credit arising from the use of the Service or reliance on its output.
        Our total liability for any claim relating to the Service is limited to the fees you paid to us for the Service in the 12 months
        before the event giving rise to the claim.
      </p>

      <h2>10. Indemnity</h2>
      <p>You agree to indemnify us against claims arising from your data, your documents and filings, or your breach of these terms or of applicable law.</p>

      <h2>11. Suspension and termination</h2>
      <p>We may suspend or close accounts used unlawfully or in a way that harms the Service or other users. You may stop using the Service at any time.</p>

      <h2>12. Changes to these terms</h2>
      <p>We may update these terms; material changes will be notified in the app or by e-mail. Continued use after the change means you accept the updated terms.</p>

      <h2>13. Governing law and disputes</h2>
      <p>
        These terms are governed by the laws of India. Disputes will first be attempted to be resolved amicably; failing that, courts at
        the location of our registered office will have exclusive jurisdiction.
      </p>

      <h2>14. Contact</h2>
      <p><Company field="name" /> · <Company field="email" link /></p>
    </LegalPage>
  );
}

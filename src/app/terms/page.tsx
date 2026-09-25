import { LegalPage } from "@/components/LegalPage";
import { Company } from "@/lib/config";

export const metadata = { title: "Terms of Service — GST Billing" };

export default function Terms() {
  return (
    <LegalPage title="Terms of Service" updated="September 2026">
      <p className="rounded-lg bg-amber-50 px-3 py-2 text-amber-900">Template — have it reviewed by your legal advisor before going live.</p>
      <p>These terms govern the use of GST Billing (the &quot;Service&quot;), provided by <Company field="name" /> (&quot;we&quot;). By creating an account you agree to them.</p>
      <h2>1. The Service</h2>
      <p>GST Billing is online software for invoicing, inventory, accounting and GST compliance. You are responsible for the accuracy of the data you enter and for the returns you file; reports produced by the Service should be reviewed by you or your tax professional before filing.</p>
      <h2>2. Accounts</h2>
      <ul>
        <li>You must give accurate information and keep your password and two-factor device safe.</li>
        <li>You are responsible for everything done through your account and by staff you add.</li>
        <li>We may suspend accounts that are used unlawfully or that harm the Service.</li>
      </ul>
      <h2>3. Plans, trial and payment</h2>
      <ul>
        <li>Paid plans are billed in advance, monthly or yearly, and include applicable GST.</li>
        <li>When a paid plan expires the account moves to the Free plan; your data is kept.</li>
        <li>Prices may change with 30 days notice; the change applies from your next renewal.</li>
      </ul>
      <h2>4. Your data</h2>
      <p>You own your business data. We process it only to provide the Service, as described in our Privacy Policy. You can export or back up your data at any time.</p>
      <h2>5. Availability</h2>
      <p>We aim for high availability but do not guarantee uninterrupted service. Keep your own backups of important data.</p>
      <h2>6. Liability</h2>
      <p>To the extent permitted by law, our total liability is limited to the fees you paid in the 12 months before the claim.</p>
      <h2>7. Governing law</h2>
      <p>These terms are governed by the laws of India. Courts at the location of our registered office have jurisdiction.</p>
      <h2>8. Contact</h2>
      <p><Company field="name" /> · <Company field="email" /></p>
    </LegalPage>
  );
}

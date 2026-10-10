import { LegalPage } from "@/components/LegalPage";
import { Company } from "@/lib/config";

export const metadata = { title: "Refund & Cancellation Policy" };

export default function Refund() {
  return (
    <LegalPage title="Refund & Cancellation Policy" updated="10 October 2026">
      <h2>Free plan and free trial</h2>
      <p>The Free plan costs nothing. New accounts get a free trial of a paid plan; no payment is taken during the trial and nothing renews automatically.</p>
      <h2>Cancellation</h2>
      <p>You can stop renewing at any time. Your paid plan stays active until the end of the period already paid for; then the account moves to the Free plan with your data intact. You can download your data at any time.</p>
      <h2>Refunds</h2>
      <ul>
        <li><b>Monthly plans</b> are not refundable once the month has started.</li>
        <li><b>Yearly and multi-year plans</b> can be refunded in full within 7 days of the first payment for that plan if you are not satisfied. After 7 days there is no refund for the remaining period; multi-year plans are discounted because they are paid for the whole term.</li>
        <li><b>API credit packs</b> are not refundable once any credit from the pack has been used; an unused pack can be refunded within 7 days of purchase.</li>
        <li><b>Duplicate payments, or payments debited but not applied</b>, are refunded in full within 5–7 working days to the original payment method.</li>
        <li>GST charged is refunded together with the amount it relates to.</li>
      </ul>
      <h2>How to request</h2>
      <p>E-mail <Company field="email" link /> from your registered e-mail with the payment reference. We reply within 2 working days.</p>
    </LegalPage>
  );
}

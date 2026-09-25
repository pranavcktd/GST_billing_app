import { COMPANY, LegalPage } from "@/components/LegalPage";

export const metadata = { title: "Refund & Cancellation Policy — GST Billing" };

export default function Refund() {
  return (
    <LegalPage title="Refund & Cancellation Policy" updated="September 2026">
      <p className="rounded-lg bg-amber-50 px-3 py-2 text-amber-900">Template — adjust to your business policy.</p>
      <h2>Free trial</h2>
      <p>New accounts get a free trial. No payment is taken during the trial.</p>
      <h2>Cancellation</h2>
      <p>You can stop renewing at any time. Your paid plan stays active until the end of the period already paid for, after which the account moves to the Free plan with your data intact.</p>
      <h2>Refunds</h2>
      <ul>
        <li>Monthly plans are non-refundable once the billing period has started.</li>
        <li>Yearly plans can be refunded within 7 days of the first payment if you are not satisfied.</li>
        <li>Duplicate or failed-but-debited payments are refunded in full within 5–7 working days to the original payment method.</li>
      </ul>
      <h2>How to request</h2>
      <p>E-mail {COMPANY.email} with your registered e-mail and the payment reference.</p>
    </LegalPage>
  );
}

import { LegalPage } from "@/components/LegalPage";
import { Company } from "@/lib/config";

export const metadata = { title: "Disclaimer" };

export default function Disclaimer() {
  return (
    <LegalPage title="Disclaimer" updated="September 2026">
      <p className="rounded-lg bg-amber-50 px-3 py-2 text-amber-900">Template — have it reviewed by your legal advisor before going live.</p>
      <h2>A software tool, not professional advice</h2>
      <p>
        SmartHisab, provided by <Company field="name" />, is software that helps businesses record transactions and prepare invoices,
        reports and data files from the information they enter. It does not provide tax, legal, accounting or financial advice, and
        nothing in the software, its help text or our communications should be treated as such.
      </p>
      <h2>Your responsibility for filings and documents</h2>
      <ul>
        <li>You decide the GST rates, HSN/SAC codes, place of supply, tax treatment and all other details of your transactions.</li>
        <li>Invoices, e-invoice / e-way bill data, GSTR reports and JSON files are prepared from your entries. Review them — ideally with a qualified professional — before you issue, upload or file them.</li>
        <li>SmartHisab does not file returns or make tax payments on your behalf. Filing, payment and compliance with deadlines remain your responsibility.</li>
      </ul>
      <h2>Rules change</h2>
      <p>
        GST law, rates, forms and file formats change from time to time. We work to update the software promptly, but there may be a
        delay between a change in law and its reflection in the software. Always refer to the official notifications and the GST portal.
      </p>
      <h2>Third-party and public data</h2>
      <p>
        GSTIN details (name, address, status) are obtained from third-party data providers, and the HSN/SAC directory is based on
        publicly available lists. This information is provided for convenience, may be incomplete or out of date, and should be
        checked before you rely on it. Suggested GST rates are indicative only.
      </p>
      <h2>No affiliation</h2>
      <p>
        SmartHisab is independent software. It is not affiliated with, endorsed, approved or certified by the Goods and Services Tax
        Network (GSTN), the Central Board of Indirect Taxes and Customs (CBIC), the NIC e-invoice / e-way bill systems or any Government
        authority. Names of forms and systems are used only to describe compatibility.
      </p>
      <h2>No warranty</h2>
      <p>
        The software is provided on an &quot;as is&quot; and &quot;as available&quot; basis. To the extent permitted by law, we do not warrant that it
        will be error-free or uninterrupted, or that its output will meet any particular legal or regulatory requirement. Our liability
        is limited as set out in the Terms of Service.
      </p>
      <h2>Questions</h2>
      <p><Company field="name" /> · <Company field="email" link /></p>
    </LegalPage>
  );
}

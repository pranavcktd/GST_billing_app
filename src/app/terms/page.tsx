import Link from "next/link";
import { LegalPage } from "@/components/LegalPage";
import { BrandName, Company, IfLegal, Legal } from "@/lib/config";

export const metadata = { title: "Terms of Service" };

const L = ({ href, children }: { href: string; children: React.ReactNode }) => <Link href={href} className="text-brand-600 underline">{children}</Link>;

export default function Terms() {
  return (
    <LegalPage title="Terms of Service" updated="10 October 2026" intro={<>
      These terms are a contract between you (the business or person using the Service) and <Company field="name" />. Please read
      them with our <L href="/privacy">Privacy Policy</L>, <L href="/dpa">Data Processing Addendum</L> and{" "}
      <L href="/security">Security &amp; Data Retention</L> page, which form part of them. In short: <BrandName /> is a
      record-keeping and computing tool; <b>you remain responsible for your tax and statutory compliance</b>.
    </>}>
      <h2>1. Acceptance and versions</h2>
      <p>
        By creating an account, signing in, or using the Service you accept these terms on behalf of yourself and the business you
        represent, and you confirm that you are at least 18 years old and authorised to bind that business. We record the version you
        accept and when. When we change these terms we will show the new version in the app and ask you to accept it before you
        continue; if you do not accept it you may stop using the Service and export your data (clause 17).
      </p>

      <h2>2. Definitions</h2>
      <ul>
        <li><b>“Company”, “we”, “us”</b> — <Company field="name" /><IfLegal field="cin">, CIN <Legal field="cin" /></IfLegal>, the provider of the Service.</li>
        <li><b>“Service”</b> — the <BrandName /> web and mobile application, its APIs and related support.</li>
        <li><b>“You”, “User”</b> — the account holder and the business(es) in the account, including staff they invite.</li>
        <li><b>“Business Data”</b> — invoices, books of account, parties, items, payroll, documents and other data entered or uploaded by you.</li>
        <li><b>“Statutory Records”</b> — Business Data you must keep under law, such as tax invoices, credit / debit notes, books of account and their audit trail.</li>
      </ul>

      <h2>3. Nature of the Service — a tool, not advice</h2>
      <ol>
        <li>
          The Service is a cloud-based record-keeping, computing and electronic-invoicing tool. It works out taxes, prepares documents,
          return data and files from the data you enter, using rules and rate tables kept by us.
        </li>
        <li>
          We, our directors, officers, employees and agents are <b>not</b> chartered accountants, tax practitioners, lawyers or auditors
          for you, and we do not give legal, tax, accounting or audit advice. We are not a GST Suvidha Provider (GSP): direct
          e-invoice and e-way bill generation is done through a licensed GSP chosen by us.
        </li>
        <li>
          Tax law, rates, notifications and portal formats change often. We make reasonable efforts to keep the Service up to date but
          cannot promise that every change is reflected immediately. You must check tax rates, HSN/SAC codes, place of supply, input tax
          credit treatment and every document or return with a qualified professional before issuing or filing it.
        </li>
        <li>The Service does not file returns or pay taxes on your behalf. Return data and JSON files are prepared for you to review and upload.</li>
      </ol>

      <h2>4. Accounts, staff and security</h2>
      <ul>
        <li>You must give true and complete registration details and keep them up to date.</li>
        <li>You are responsible for everything done through your account, including by staff, accountants or other users you invite, and for the access rights you give them.</li>
        <li>Keep passwords, one-time codes, authenticator devices and digital signature certificates secure. Tell us at once if you suspect misuse. We strongly recommend two-factor sign-in for owners and administrators.</li>
        <li>You must not share one login between several people.</li>
      </ul>

      <h2>5. Your statutory responsibilities</h2>
      <p>The duty to comply with the CGST Act, IGST Act, State GST Acts, the Income-tax Act, the Companies Act, 2013, labour laws and the rules under them rests entirely with you. In particular you are responsible for:</p>
      <ul>
        <li>the accuracy and completeness of all data you enter, including party GSTINs, HSN/SAC codes, tax rates, place of supply and values;</li>
        <li>invoice numbering under Rule 46 of the CGST Rules — unique and consecutive in each financial year, at most 16 characters (the Service numbers documents this way; numbers you type yourself are your responsibility);</li>
        <li>where e-invoicing applies to you (Rule 48(4)), generating a valid IRN and QR code before the goods move or the service is supplied, and checking it;</li>
        <li>checking transporter, vehicle and distance details before generating an e-way bill and before dispatch;</li>
        <li>reconciling GSTR-2B with your purchases and filing GSTR-1, GSTR-3B, GSTR-9 and other returns, and paying tax, on time;</li>
        <li>keeping your books of account and records for the periods required by law (CGST Act s.36 — 72 months from the due date of the annual return; Companies Act s.128 — 8 financial years), including your own copies (clause 11);</li>
        <li>if you are a company, meeting the audit-trail and electronic-records duties of the Companies (Accounts) Rules, 2014 — the Service provides the audit trail; compliance and audit remain yours.</li>
      </ul>

      <h2>6. Records cannot be deleted</h2>
      <ol>
        <li>Issued tax invoices, bills of supply and credit / debit notes cannot be deleted from the Service. Wrong documents must be <b>cancelled</b> (the number stays used, as the law requires) or corrected by a <b>credit or debit note</b> under Section 34 of the CGST Act. Reporting cancellations and notes in your returns is your responsibility.</li>
        <li>Every change to your books of account is recorded in an audit trail with the values before and after, who made it and when. The audit trail cannot be switched off, edited or deleted by any user.</li>
        <li>“Clear data” is meant only for test or practice entries before you go live. It cannot clear bills once any of them has an IRN or e-way bill, or once GST returns are recorded as filed, and a full backup is kept before anything is cleared.</li>
        <li>We will not act on requests to erase cancelled numbers, to remove entries from the audit trail, or to delete Statutory Records before the end of the period the law requires.</li>
      </ol>

      <h2>7. Government systems and third parties</h2>
      <p>
        Some features depend on systems we do not control: the GST Network (GSTN), the Invoice Registration Portals (IRP), the National
        Informatics Centre (NIC) e-way bill system, GSPs and other API providers, payment gateways, WhatsApp and e-mail providers, and
        cloud hosting. Their availability, speed and the data they return (for example GSTIN details) are outside our control.
        We are not liable for missed deadlines, rejected or delayed documents, goods held in transit, interest, late fees or penalties
        caused by the downtime, errors or rejections of these systems.
      </p>

      <h2>8. Plans, credits, payment and taxes</h2>
      <ul>
        <li>Paid plans are billed in advance for the period chosen (monthly, yearly or a multi-year term paid upfront). GST is added to the price.</li>
        <li>Direct e-invoice, e-way bill, cancellation, filing-status and WhatsApp messages beyond your plan’s allowance use API credits. Monthly allowances do not carry forward; prepaid credit packs do not expire while your account is active. Failed calls and test-mode calls are not charged.</li>
        <li>When a paid plan ends the account moves to the Free plan and your data is kept.</li>
        <li>We may change prices and plan features with at least 30 days’ notice; changes apply from your next renewal and never to a period you have already paid for.</li>
        <li>Refunds follow our <L href="/refund">Refund &amp; Cancellation Policy</L>.</li>
      </ul>

      <h2>9. Acceptable use</h2>
      <p>You must not use the Service to:</p>
      <ul>
        <li>create fake, back-dated or misleading invoices, circular or accommodation entries, or otherwise evade tax or claim input tax credit you are not entitled to;</li>
        <li>break any law, or upload content that is unlawful, infringing or harmful;</li>
        <li>access another person’s account or data without permission, probe or test the security of the Service without our written consent, or interfere with its operation;</li>
        <li>copy, resell, reverse engineer or scrape the Service, or use it to build a competing product.</li>
      </ul>
      <p>We may suspend accounts that breach this clause and report unlawful activity to the authorities where the law requires.</p>

      <h2>10. Your data and privacy</h2>
      <p>
        You own your Business Data. For personal data in your Business Data (for example your customers’ and employees’ details) you
        are the <b>data fiduciary</b> under the Digital Personal Data Protection Act, 2023 and we act as your <b>data processor</b>,
        on the terms of our <L href="/dpa">Data Processing Addendum</L>. For your own account details we are the data fiduciary, as set
        out in the <L href="/privacy">Privacy Policy</L>. You must have a lawful basis, and give any notices, needed to enter personal data
        of others into the Service.
      </p>

      <h2>11. Backups and your own copies</h2>
      <p>
        We back up the Service daily and keep backups as described on the <L href="/security">Security &amp; Data Retention</L> page. You
        can download a backup or an Excel export of your data at any time. Because the duty to keep records is yours, you should keep
        your own copies of important records as well.
      </p>

      <h2>12. Intellectual property</h2>
      <p>The Service, its software, design and content belong to the Company or its licensors. You receive a limited, non-exclusive, non-transferable right to use it for your business during your subscription. Feedback you give may be used to improve the Service.</p>

      <h2>13. Disclaimer</h2>
      <p>
        The Service is provided “as is” and “as available”. To the maximum extent permitted by law we exclude all warranties, express or
        implied, including that the Service or its output will be uninterrupted, error-free, complete, or suitable for any particular
        statutory, regulatory or audit purpose. See also our <L href="/disclaimer">Disclaimer</L>.
      </p>

      <h2>14. Limitation of liability</h2>
      <ol>
        <li>
          To the maximum extent permitted by law, the Company and its directors, officers, employees, shareholders, developers and
          agents are not liable for: (a) any tax, demand, interest, late fee or penalty under the CGST, IGST, Customs, Income-tax or
          Companies Acts; (b) any loss, blocking, disallowance or reversal of input tax credit; (c) detention, seizure or delay of goods
          or conveyances; or (d) any indirect, special, punitive or consequential loss, or loss of profit, business, goodwill or data
          that could have been avoided by keeping your own copies.
        </li>
        <li>
          Our total liability for all claims relating to the Service, under any legal theory, is limited to the subscription fees you
          actually paid us in the three (3) months before the event giving rise to the claim.
        </li>
        <li>Nothing in these terms limits liability that cannot be limited by law, including for fraud.</li>
      </ol>

      <h2>15. Indemnity</h2>
      <p>
        You will indemnify and hold harmless the Company and its directors, officers, employees and contractors against claims,
        notices, demands, liabilities and reasonable legal costs arising from: inaccurate, incomplete or fraudulent data or documents
        you enter or issue; your failure to pay tax or file returns on time; your non-compliance with the Companies Act or its rules;
        your breach of anyone’s data-protection rights; or your breach of these terms.
      </p>

      <h2>16. Contracting entity</h2>
      <p>
        This contract is with the Company only. To the extent permitted by law, claims relating to the Service, its data processing or
        infrastructure must be brought against the Company and not against its directors, founders, shareholders or employees in
        their personal capacity, and are subject to clause 14.
      </p>

      <h2>17. Suspension, termination and your data afterwards</h2>
      <ul>
        <li>You may stop using the Service at any time. We may suspend or close accounts that breach these terms or the law, or that put the Service or other users at risk; where reasonable we will give notice first.</li>
        <li>After closure you have 30 days to download your data. After that we delete it, except Statutory Records and audit trails that the law requires to be kept, which are retained securely for the statutory period and then deleted.</li>
      </ul>

      <h2>18. Changes to these terms</h2>
      <p>We may update these terms. Material changes take effect when you accept them in the app (clause 1); we will also tell account owners by e-mail.</p>

      <h2>19. Governing law and disputes</h2>
      <ol>
        <li>These terms are governed by the laws of India.</li>
        <li>The parties will first try to settle any dispute in good faith within 30 days of written notice.</li>
        <li>
          Unresolved disputes will be referred to arbitration by a sole arbitrator under the Arbitration and Conciliation Act, 1996.
          The seat of arbitration is <Legal field="jurisdiction" fallback="the city of the Company's registered office" />, and the
          language is English. Subject to this, the courts at <Legal field="jurisdiction" fallback="the city of the Company's registered office" />{" "}
          have exclusive jurisdiction, including for urgent interim relief.
        </li>
        <li>Nothing in this clause removes any right that cannot be excluded by law.</li>
      </ol>

      <h2>20. Grievance officer and contact</h2>
      <p>
        <Legal field="grievance_officer" fallback="Grievance Officer" /> · <Legal field="grievance_email" />{" "}
        <Legal field="grievance_phone" /> — see the <L href="/grievance">Grievance Redressal</L> page for how complaints are handled.
        General contact: <Company field="email" link />.
      </p>

      <h2>21. General</h2>
      <ul>
        <li>These terms and the documents they refer to are the whole agreement about the Service.</li>
        <li>If a provision is found unenforceable, the rest stays in force and that provision applies to the extent it is enforceable.</li>
        <li>Neither party is liable for delay caused by events beyond its reasonable control (force majeure), including failures of government systems, networks or utilities.</li>
        <li>You may not transfer this contract without our consent; we may transfer it to a successor of our business with notice to you.</li>
        <li>Notices to you are sent to your registered e-mail or shown in the app; notices to us go to the contact e-mail above.</li>
      </ul>
    </LegalPage>
  );
}

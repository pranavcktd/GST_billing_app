import Link from "next/link";
import { BrandLogo } from "@/components/BrandLogo";
import { BrandName, Company } from "@/lib/config";

export const LEGAL_LINKS: [string, string][] = [
  ["/terms", "Terms"], ["/privacy", "Privacy"], ["/dpa", "Data Processing"], ["/security", "Security & Retention"],
  ["/refund", "Refunds"], ["/disclaimer", "Disclaimer"], ["/grievance", "Grievance"], ["/contact", "Contact"],
];

/** Frame for the public policy pages (also required by payment gateways such as Razorpay). */
export function LegalPage({ title, updated, intro, children }: { title: string; updated: string; intro?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-white">
      <header className="border-b border-gray-100">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-2 px-4 py-3">
          <Link href="/"><BrandLogo size="sm" /></Link>
          <nav className="flex flex-wrap justify-end gap-x-4 gap-y-1 text-sm text-gray-600">
            {LEGAL_LINKS.map(([href, label]) => <Link key={href} href={href} className="hover:text-gray-900">{label}</Link>)}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
        <p className="mt-1 text-sm text-gray-500">Last updated {updated}</p>
        {intro && <div className="mt-4 rounded-lg bg-gray-50 px-4 py-3 text-sm text-gray-700">{intro}</div>}
        <div className="mt-6 space-y-4 text-sm leading-relaxed text-gray-700 [&_h2]:mt-8 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:text-gray-900 [&_h3]:mt-4 [&_h3]:font-semibold [&_h3]:text-gray-900 [&_li]:ml-5 [&_li]:list-disc [&_ol>li]:list-decimal [&_table]:w-full [&_table]:text-left [&_td]:border-t [&_td]:border-gray-100 [&_td]:py-2 [&_td]:pr-3 [&_td]:align-top [&_th]:pb-2 [&_th]:pr-3 [&_th]:text-xs [&_th]:font-semibold [&_th]:uppercase [&_th]:text-gray-500">
          {children}
        </div>
        <p className="mt-10 border-t border-gray-100 pt-4 text-xs text-gray-400">
          <BrandName /> is a product of <Company field="name" />. <BrandName /> is independent software and is not affiliated with,
          endorsed or certified by GSTN, CBIC, the Ministry of Corporate Affairs or any Government authority.
        </p>
      </main>
    </div>
  );
}

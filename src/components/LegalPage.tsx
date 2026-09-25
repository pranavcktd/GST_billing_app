import Link from "next/link";

/** Frame for the public policy pages (required by payment gateways such as Razorpay). */
export function LegalPage({ title, updated, children }: { title: string; updated: string; children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-white">
      <header className="border-b border-gray-100">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4">
          <Link href="/" className="font-semibold text-gray-900">GST Billing</Link>
          <nav className="flex gap-4 text-sm text-gray-600">
            <Link href="/terms">Terms</Link><Link href="/privacy">Privacy</Link><Link href="/refund">Refunds</Link><Link href="/contact">Contact</Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
        <p className="mt-1 text-sm text-gray-500">Last updated {updated}</p>
        <div className="mt-6 space-y-4 text-sm leading-relaxed text-gray-700 [&_h2]:mt-6 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:text-gray-900 [&_li]:ml-5 [&_li]:list-disc">
          {children}
        </div>
      </main>
    </div>
  );
}

export const COMPANY = {
  name: "Core NexGen AI Pvt Ltd",
  email: "corenexgenaipvtltd@gmail.com",
  address: "Registered office address — to be filled in",
  phone: "Phone — to be filled in",
};

"use client";

import {
  BarChart3,
  Boxes,
  ClipboardList,
  FileCheck2,
  FileText,
  HandCoins,
  Landmark,
  LayoutDashboard,
  LogOut,
  Menu,
  Plus,
  ReceiptIndianRupee,
  ReceiptText,
  Settings,
  ShoppingCart,
  Tags,
  Truck,
  Undo2,
  Users,
  Wallet,
  Wrench,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LinkButton, Loading } from "@/components/ui";
import { useAuth } from "@/lib/auth";

const NAV: { section?: string; items: { href: string; label: string; icon: React.ElementType }[] }[] = [
  { items: [{ href: "/dashboard", label: "Dashboard", icon: LayoutDashboard }] },
  {
    section: "Sales",
    items: [
      { href: "/v/sales", label: "Sale Invoices", icon: ReceiptIndianRupee },
      { href: "/v/estimates", label: "Estimates", icon: FileText },
      { href: "/v/sale-orders", label: "Sale Orders", icon: ClipboardList },
      { href: "/v/delivery-challans", label: "Delivery Challans", icon: Truck },
      { href: "/payments/in", label: "Payment In", icon: Wallet },
      { href: "/v/credit-notes", label: "Credit Notes", icon: Undo2 },
    ],
  },
  {
    section: "Purchases",
    items: [
      { href: "/v/purchases", label: "Purchase Bills", icon: ShoppingCart },
      { href: "/v/purchase-orders", label: "Purchase Orders", icon: FileCheck2 },
      { href: "/payments/out", label: "Payment Out", icon: Wallet },
      { href: "/v/debit-notes", label: "Debit Notes", icon: Undo2 },
    ],
  },
  {
    section: "Expenses",
    items: [
      { href: "/v/expenses", label: "Expenses", icon: ReceiptText },
      { href: "/expenses/categories", label: "Categories & Items", icon: Tags },
    ],
  },
  {
    section: "Cash & Bank",
    items: [
      { href: "/cash-bank", label: "Bank & Cash", icon: Landmark },
      { href: "/cash-bank/cheques", label: "Cheques", icon: FileCheck2 },
      { href: "/loans", label: "Loan Accounts", icon: HandCoins },
      { href: "/cash-bank/capital", label: "Capital", icon: Wallet },
      { href: "/cash-bank/tax-payments", label: "Tax Payments", icon: ReceiptText },
    ],
  },
  {
    section: "Masters",
    items: [
      { href: "/parties", label: "Parties", icon: Users },
      { href: "/items", label: "Items & Stock", icon: Boxes },
    ],
  },
  {
    section: "Insights",
    items: [
      { href: "/reports", label: "Reports", icon: BarChart3 },
      { href: "/utilities", label: "Utilities", icon: Wrench },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { me, loading, business, logout, switchBusiness } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!me) router.replace("/login");
    else if (!business) router.replace("/onboarding");
  }, [loading, me, business, router]);

  if (loading || !me || !business) return <Loading />;

  return (
    <div className="flex min-h-screen">
      {open && <div className="fixed inset-0 z-30 bg-black/30 lg:hidden" onClick={() => setOpen(false)} />}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-gray-200 bg-white transition-transform lg:static lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="flex h-14 items-center justify-between border-b border-gray-100 px-4">
          <Link href="/dashboard" className="flex items-center gap-2">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/icon.svg" alt="" className="h-7 w-7" />
            <span className="font-semibold text-gray-900">GST Billing</span>
          </Link>
          <button className="lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu">
            <X size={20} />
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto px-3 py-3">
          {NAV.map((group, gi) => (
            <div key={gi} className="mb-3">
              {group.section && (
                <div className="px-2 pb-1 text-[11px] font-semibold tracking-wider text-gray-400 uppercase">{group.section}</div>
              )}
              {group.items.map(({ href, label, icon: Icon }) => {
                const active = pathname === href || (pathname.startsWith(href + "/") && !NAV.some((g) =>
                  g.items.some((i) => i.href !== href && i.href.startsWith(href + "/") && pathname.startsWith(i.href))));
                return (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setOpen(false)}
                    className={`flex items-center gap-2.5 rounded-lg px-2 py-2 text-sm ${active ? "bg-brand-50 font-medium text-brand-700" : "text-gray-700 hover:bg-gray-50"}`}
                  >
                    <Icon size={17} />
                    {label}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="border-t border-gray-100 p-3">
          <div className="truncate px-2 text-sm font-medium text-gray-900">{me.user.name}</div>
          <div className="truncate px-2 text-xs text-gray-500">{me.user.email}</div>
          <button onClick={logout} className="mt-2 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-sm text-gray-700 hover:bg-gray-50">
            <LogOut size={16} /> Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-gray-200 bg-white/90 px-4 backdrop-blur">
          <button className="lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu size={22} />
          </button>
          <div className="min-w-0 flex-1">
            {me.businesses.length > 1 ? (
              <select
                className="max-w-full truncate rounded-md border-0 bg-transparent py-1 text-sm font-semibold text-gray-900 focus:ring-0"
                value={business.id}
                onChange={(e) => switchBusiness(e.target.value)}
              >
                {me.businesses.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            ) : (
              <div className="truncate text-sm font-semibold text-gray-900">{business.name}</div>
            )}
            <div className="truncate text-xs text-gray-500">
              {business.gstin ? `GSTIN ${business.gstin}` : "Not GST registered"}
            </div>
          </div>
          <LinkButton href="/v/purchases/new" variant="secondary" className="hidden sm:inline-flex">
            <Plus size={16} /> Purchase
          </LinkButton>
          <LinkButton href="/v/sales/new">
            <Plus size={16} /> Sale
          </LinkButton>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">{children}</main>
      </div>
    </div>
  );
}

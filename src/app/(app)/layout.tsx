"use client";

import {
  Barcode,
  BarChart3,
  Boxes,
  ClipboardList,
  Crown,
  FileCheck2,
  FileText,
  HandCoins,
  History,
  Landmark,
  LayoutDashboard,
  LogOut,
  Menu,
  Plus,
  ReceiptIndianRupee,
  ReceiptText,
  ScanLine,
  Settings,
  Shield,
  ShoppingCart,
  Store,
  Tags,
  Truck,
  Undo2,
  Users,
  Wallet,
  Warehouse,
  Wrench,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LinkButton, Loading } from "@/components/ui";
import { useAuth, usePerms } from "@/lib/auth";
import type { Action, Module } from "@/lib/types";
import { BrandLogo } from "@/components/BrandLogo";
import { UserBar } from "@/components/UserBar";

type NavItem = { href: string; label: string; icon: React.ElementType; perm?: [Module, Action] | [Module, Action][] };

const NAV: { section?: string; items: NavItem[] }[] = [
  {
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/pos", label: "POS Billing", icon: ScanLine, perm: ["sales", "create"] },
    ],
  },
  {
    section: "Sales",
    items: [
      { href: "/v/sales", label: "Sale Invoices", icon: ReceiptIndianRupee, perm: ["sales", "view"] },
      { href: "/v/estimates", label: "Estimates", icon: FileText, perm: ["sales", "view"] },
      { href: "/v/sale-orders", label: "Sale Orders", icon: ClipboardList, perm: ["sales", "view"] },
      { href: "/v/delivery-challans", label: "Delivery Challans", icon: Truck, perm: ["sales", "view"] },
      { href: "/payments/in", label: "Payment In", icon: Wallet, perm: ["payments_in", "view"] },
      { href: "/v/credit-notes", label: "Credit Notes", icon: Undo2, perm: ["sales", "view"] },
    ],
  },
  {
    section: "Purchases",
    items: [
      { href: "/v/purchases", label: "Purchase Bills", icon: ShoppingCart, perm: ["purchases", "view"] },
      { href: "/v/purchase-orders", label: "Purchase Orders", icon: FileCheck2, perm: ["purchases", "view"] },
      { href: "/payments/out", label: "Payment Out", icon: Wallet, perm: ["payments_out", "view"] },
      { href: "/v/debit-notes", label: "Debit Notes", icon: Undo2, perm: ["purchases", "view"] },
    ],
  },
  {
    section: "Expenses",
    items: [
      { href: "/v/expenses", label: "Expenses", icon: ReceiptText, perm: ["expenses", "view"] },
      { href: "/expenses/categories", label: "Categories & Items", icon: Tags, perm: ["expenses", "view"] },
    ],
  },
  {
    section: "Cash & Bank",
    items: [
      { href: "/cash-bank", label: "Bank & Cash", icon: Landmark, perm: ["cashbank", "view"] },
      { href: "/cash-bank/cheques", label: "Cheques", icon: FileCheck2, perm: ["cashbank", "view"] },
      { href: "/loans", label: "Loan Accounts", icon: HandCoins, perm: ["cashbank", "view"] },
      { href: "/cash-bank/capital", label: "Capital", icon: Wallet, perm: ["cashbank", "view"] },
      { href: "/cash-bank/tax-payments", label: "Tax Payments", icon: ReceiptText, perm: ["cashbank", "view"] },
    ],
  },
  {
    section: "Masters",
    items: [
      { href: "/parties", label: "Parties", icon: Users, perm: ["parties", "view"] },
      { href: "/items", label: "Items & Stock", icon: Boxes, perm: ["items", "view"] },
      { href: "/godowns", label: "Godowns & Transfers", icon: Warehouse, perm: ["items", "view"] },
      { href: "/items/labels", label: "Barcode Labels", icon: Barcode, perm: ["items", "view"] },
    ],
  },
  {
    section: "Insights",
    items: [
      { href: "/reports", label: "Reports", icon: BarChart3,
        perm: [["reports_sales", "view"], ["reports_stock", "view"], ["reports_financial", "view"], ["reports_gst", "view"]] },
      { href: "/utilities/audit", label: "Audit Trail", icon: History, perm: ["audit", "view"] },
      { href: "/utilities", label: "Utilities", icon: Wrench },
      { href: "/billing", label: "Subscription", icon: Crown },
      { href: "/settings", label: "Settings", icon: Settings, perm: ["settings", "view"] },
    ],
  },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { me, loading, business, logout, switchBusiness } = useAuth();
  const { can } = usePerms();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (loading) return;
    if (!me) router.replace("/login");
    else if (me.must_change_password) router.replace("/change-password");
    else if (!business) router.replace(me.platform_role === "SUPERADMIN" ? "/admin" : me.platform_role === "RESELLER" ? "/reseller" : "/onboarding");
  }, [loading, me, business, router]);

  if (loading || !me || !business) return <Loading />;

  const allowed = (i: NavItem) =>
    !i.perm || (Array.isArray(i.perm[0]) ? (i.perm as [Module, Action][]).some(([m, a]) => can(m, a)) : can(...(i.perm as [Module, Action])));
  const nav = NAV.map((g) => ({ ...g, items: g.items.filter(allowed) })).filter((g) => g.items.length);
  if (me.platform_role) {
    nav.push({ section: "Platform", items: [
      me.platform_role === "SUPERADMIN"
        ? { href: "/admin", label: "Super Admin", icon: Shield }
        : { href: "/reseller", label: "Reseller Portal", icon: Store },
    ] });
  }
  const allHrefs = nav.flatMap((g) => g.items.map((i) => i.href));

  return (
    <div className="flex min-h-screen">
      {open && <div className="fixed inset-0 z-30 bg-black/30 lg:hidden" onClick={() => setOpen(false)} />}
      <aside
        className={`no-print fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-gray-200 bg-white transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="flex h-14 items-center justify-between border-b border-gray-100 px-4">
          <Link href="/dashboard"><BrandLogo size="sm" /></Link>
          <button className="lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu">
            <X size={20} />
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto px-3 py-3">
          {nav.map((group, gi) => (
            <div key={gi} className="mb-3">
              {group.section && (
                <div className="px-2 pb-1 text-[11px] font-semibold tracking-wider text-gray-400 uppercase">{group.section}</div>
              )}
              {group.items.map(({ href, label, icon: Icon }) => {
                const active = pathname === href || (pathname.startsWith(href + "/") &&
                  !allHrefs.some((h) => h !== href && h.startsWith(href + "/") && pathname.startsWith(h)));
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
        <header className="no-print sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-gray-200 bg-white/90 px-4 backdrop-blur">
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
          {can("purchases", "create") && (
            <LinkButton href="/v/purchases/new" variant="secondary" className="hidden sm:inline-flex">
              <Plus size={16} /> Purchase
            </LinkButton>
          )}
          {can("sales", "create") && (
            <LinkButton href="/v/sales/new">
              <Plus size={16} /> Sale
            </LinkButton>
          )}
          <div className="ml-1 border-l border-gray-200 pl-3"><UserBar /></div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">{children}</main>
      </div>
    </div>
  );
}

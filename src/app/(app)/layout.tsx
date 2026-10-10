"use client";

import {
  BellRing,
  CalendarCheck,
  CalendarDays,
  UserRound,
  BadgeIndianRupee,
  FolderLock,
  Factory,
  Route,
  Repeat,
  Briefcase,
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
  LifeBuoy,
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
import { Suspense, useEffect, useState } from "react";
import { LinkButton, Loading } from "@/components/ui";
import { useAuth, usePerms } from "@/lib/auth";
import type { Action, Module } from "@/lib/types";
import { BrandLogo } from "@/components/BrandLogo";
import { GlobalSearch } from "@/components/GlobalSearch";
import { OfflineSync } from "@/components/OfflineSync";
import { MobileNav } from "@/components/MobileNav";
import { PlanBadge } from "@/components/PlanBadge";
import { NotificationBell } from "@/components/NotificationBell";
import { UserBar } from "@/components/UserBar";
import { businessMode, hiddenHrefs, isHiddenHref } from "@/lib/modules";
import { InvitationsBanner, PendingSignIns } from "@/components/StaffComponents";
import { CheckInButton } from "@/components/CheckInButton";
import { HelpButton } from "@/components/Support";
import { trackUsage } from "@/lib/track";

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
      { href: "/ewaybills", label: "E-way Bills", icon: Route, perm: ["sales", "view"] },
      { href: "/payments/in", label: "Payment In", icon: Wallet, perm: ["payments_in", "view"] },
      { href: "/reminders", label: "Collect payments", icon: BellRing, perm: ["sales", "view"] },
      { href: "/recurring", label: "Recurring invoices", icon: Repeat, perm: ["sales", "view"] },
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
    section: "Staff",
    items: [
      { href: "/staff", label: "Employees", icon: UserRound, perm: ["attendance", "view"] },
      { href: "/staff/attendance", label: "Attendance", icon: CalendarDays, perm: ["attendance", "view"] },
      { href: "/staff/payroll", label: "Payroll", icon: BadgeIndianRupee, perm: ["payroll", "view"] },
    ],
  },
  {
    section: "Masters",
    items: [
      { href: "/parties", label: "Parties", icon: Users, perm: ["parties", "view"] },
      { href: "/items", label: "Items & Stock", icon: Boxes, perm: ["items", "view"] },
      { href: "/godowns", label: "Godowns & Transfers", icon: Warehouse, perm: ["items", "view"] },
      { href: "/manufacturing", label: "Manufacturing", icon: Factory, perm: ["items", "view"] },
      { href: "/price-lists", label: "Price Lists", icon: Tags, perm: ["items", "view"] },
      { href: "/items/labels", label: "Barcode Labels", icon: Barcode, perm: ["items", "view"] },
    ],
  },
  {
    section: "Insights",
    items: [
      { href: "/reports", label: "Reports", icon: BarChart3,
        perm: [["reports_sales", "view"], ["reports_stock", "view"], ["reports_financial", "view"], ["reports_gst", "view"]] },
      { href: "/compliance", label: "Compliance calendar", icon: CalendarCheck, perm: ["reports_gst", "view"] },
      { href: "/documents", label: "Documents", icon: FolderLock, perm: ["documents", "view"] },
      { href: "/utilities/audit", label: "Audit Trail", icon: History, perm: ["audit", "view"] },
      { href: "/utilities", label: "Utilities", icon: Wrench },
      { href: "/billing", label: "Subscription", icon: Crown },
      { href: "/support", label: "Help & support", icon: LifeBuoy },
      { href: "/settings", label: "Settings", icon: Settings, perm: ["settings", "view"] },
    ],
  },
];

/** The module a screen belongs to (longest menu link that matches) — for usage analytics and help tickets. */
const ALL_ITEMS = NAV.flatMap((g) => g.items);
function moduleOf(pathname: string): string | undefined {
  if (pathname === "/dashboard") return "Dashboard";
  return ALL_ITEMS.filter((i) => pathname === i.href || pathname.startsWith(i.href + "/"))
    .sort((a, b) => b.href.length - a.href.length)[0]?.label;
}

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
    else if (!business) router.replace(me.platform_role === "SUPERADMIN" || me.platform_role === "TEAM" ? "/admin" : me.platform_role === "RESELLER" ? "/reseller" : me.practice_clients > 0 ? "/practice" : "/onboarding");
  }, [loading, me, business, router]);

  const signedIn = Boolean(me && business);
  useEffect(() => { if (signedIn) trackUsage(moduleOf(pathname)); }, [pathname, signedIn]);

  if (loading || !me || !business) return <Loading />;

  const allowed = (i: NavItem) =>
    !i.perm || (Array.isArray(i.perm[0]) ? (i.perm as [Module, Action][]).some(([m, a]) => can(m, a)) : can(...(i.perm as [Module, Action])));
  const hidden = hiddenHrefs(business);
  const services = businessMode(business) === "SERVICES";
  const nav = NAV.map((g) => ({ ...g, items: g.items.filter((i) => allowed(i) && !isHiddenHref(i.href, hidden))
    .map((i) => (services && i.href === "/items" ? { ...i, label: "Services & Items" } : i)) })).filter((g) => g.items.length);
  const platformItems: NavItem[] = [];
  if (me.practice_clients > 0) platformItems.push({ href: "/practice", label: "Practitioner workspace", icon: Briefcase });
  if (me.platform_role === "SUPERADMIN") platformItems.push({ href: "/admin", label: "Super Admin", icon: Shield });
  else if (me.platform_role === "TEAM") platformItems.push({ href: "/admin", label: "Admin panel (team)", icon: Shield });
  else if (me.platform_role === "RESELLER") platformItems.push({ href: "/reseller", label: "Reseller Portal", icon: Store });
  if (platformItems.length) nav.push({ section: "More", items: platformItems });
  const allHrefs = nav.flatMap((g) => g.items.map((i) => i.href));

  return (
    <div className="flex min-h-screen">
      {open && <div className="fixed inset-0 z-30 bg-black/30 lg:hidden" onClick={() => setOpen(false)} />}
      <aside
        className={`no-print fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-gradient-to-b from-slate-950 via-slate-900 to-indigo-950 text-slate-300 transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="flex h-14 items-center justify-between border-b border-white/10 px-4">
          <Link href="/dashboard" className="rounded-lg bg-white px-2 py-1"><BrandLogo size="sm" /></Link>
          <button className="text-slate-300 lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu">
            <X size={20} />
          </button>
        </div>
        <nav className="sidebar-scroll flex-1 overflow-y-auto px-3 py-3">
          {nav.map((group, gi) => (
            <div key={gi} className="mb-3">
              {group.section && (
                <div className="px-2 pt-1 pb-1 text-[10.5px] font-semibold tracking-wider text-slate-500 uppercase">{group.section}</div>
              )}
              {group.items.map(({ href, label, icon: Icon }) => {
                const active = pathname === href || (pathname.startsWith(href + "/") &&
                  !allHrefs.some((h) => h !== href && h.startsWith(href + "/") && pathname.startsWith(h)));
                return (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setOpen(false)}
                    className={`group flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors ${active
                      ? "bg-gradient-to-r from-brand-600 to-brand-500 font-medium text-white shadow-md shadow-black/30"
                      : "text-slate-300 hover:bg-white/5 hover:text-white"}`}
                  >
                    <Icon size={17} className={active ? "text-white" : "text-slate-400 group-hover:text-white"} />
                    {label}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="border-t border-white/10 p-3">
          <div className="flex items-center gap-2.5 px-2">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-amber-300 to-orange-400 text-xs font-bold text-slate-900">
              {me.user.name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase()}
            </span>
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-white">{me.user.name}</div>
              <div className="truncate text-xs text-slate-400">{me.user.email}</div>
            </div>
          </div>
          <button onClick={logout} className="mt-2 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-sm text-slate-300 hover:bg-white/5 hover:text-white">
            <LogOut size={16} /> Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="no-print sticky top-0 z-20 flex h-14 items-center gap-2 border-b border-gray-200/70 bg-white/80 px-4 shadow-[0_1px_12px_rgba(15,23,42,0.04)] backdrop-blur-lg">
          <button className="lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu size={22} />
          </button>
          <div className="max-w-[38%] min-w-0 shrink sm:max-w-none lg:w-56">
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
            <div className="hidden truncate text-xs text-gray-500 sm:block">
              {business.gstin ? `GSTIN ${business.gstin}` : "Not GST registered"}
            </div>
          </div>
          <div className="flex min-w-0 flex-1 justify-center"><GlobalSearch /></div>
          <OfflineSync />
          <PendingSignIns />
          <CheckInButton />
          {can("purchases", "create") && (
            <span className="hidden xl:inline-flex">
              <LinkButton href="/v/purchases/new" variant="secondary"><Plus size={16} /> Purchase</LinkButton>
            </span>
          )}
          {can("sales", "create") && (
            <span className="hidden md:inline-flex">
              <LinkButton href="/v/sales/new"><Plus size={16} /> Sale</LinkButton>
            </span>
          )}
          <div className="flex items-center gap-2 sm:ml-1 sm:border-l sm:border-gray-200 sm:pl-3"><PlanBadge /><NotificationBell /><UserBar /></div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 pt-4 pb-24 sm:px-6 md:py-6"><InvitationsBanner />{children}</main>
        <Suspense fallback={null}><MobileNav onMenu={() => setOpen(true)} /></Suspense>
        {!pathname.startsWith("/support") && <HelpButton module={moduleOf(pathname)} />}
      </div>
    </div>
  );
}

"use client";

import { Boxes, LayoutDashboard, Menu, Plus, Users } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { usePerms } from "@/lib/auth";

/** Phone-only bottom bar: the few places a shop owner uses all day, within thumb reach. Hidden from md width up. */
export function MobileNav({ onMenu }: { onMenu: () => void }) {
  const path = usePathname();
  const editing = useSearchParams().has("edit");
  const { can } = usePerms();
  // like phone apps, hide the tabs while filling a form, so its Save bar (pinned to the bottom) stays visible
  if (editing || /\/(new|edit)$/.test(path) || path.startsWith("/pos")) return null;
  const item = (href: string, label: string, Icon: React.ElementType) => {
    const active = path === href || path.startsWith(href + "/");
    return (
      <Link key={href} href={href} className={`flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] ${active ? "text-brand-700" : "text-gray-600"}`}>
        <Icon size={20} /> {label}
      </Link>
    );
  };
  return (
    <nav className="no-print fixed inset-x-0 bottom-0 z-30 flex items-end border-t border-gray-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
      {item("/dashboard", "Home", LayoutDashboard)}
      {can("parties") && item("/parties", "Parties", Users)}
      {can("sales", "create") && (
        <Link href="/v/sales/new" className="flex flex-1 flex-col items-center gap-0.5 pb-2 text-[11px] font-medium text-brand-700">
          <span className="-mt-5 flex h-12 w-12 items-center justify-center rounded-full bg-brand-600 text-white shadow-lg"><Plus size={24} /></span>
          New sale
        </Link>
      )}
      {can("items") && item("/items", "Items", Boxes)}
      <button type="button" onClick={onMenu} className="flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] text-gray-600">
        <Menu size={20} /> Menu
      </button>
    </nav>
  );
}

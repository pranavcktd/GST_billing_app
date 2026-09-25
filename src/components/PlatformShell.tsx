"use client";

import { LayoutDashboard, LogOut, Shield, Store } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Loading } from "@/components/ui";
import { useAuth } from "@/lib/auth";

/** Frame for the platform-level portals (super admin, reseller) — separate from business data. */
export function PlatformShell({ need, children }: { need: "SUPERADMIN" | "RESELLER"; children: React.ReactNode }) {
  const { me, loading, business, logout } = useAuth();
  const router = useRouter();
  const allowed = me?.platform_role === need || (need === "RESELLER" && me?.platform_role === "SUPERADMIN");

  useEffect(() => {
    if (!loading && !me) router.replace("/login");
  }, [loading, me, router]);

  if (loading || !me) return <Loading />;
  if (!allowed) return <div className="p-10 text-center text-sm text-gray-600">This area is for {need === "SUPERADMIN" ? "platform administrators" : "resellers"} only.</div>;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-gray-200 bg-white">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4">
          <div className="flex items-center gap-2 font-semibold text-gray-900">
            {need === "SUPERADMIN" ? <Shield size={18} className="text-brand-600" /> : <Store size={18} className="text-brand-600" />}
            {need === "SUPERADMIN" ? "Super Admin" : "Reseller Portal"}
          </div>
          <div className="flex-1" />
          {me.platform_role === "SUPERADMIN" && need === "SUPERADMIN" && <Link href="/reseller" className="text-sm text-gray-600 hover:underline">Reseller view</Link>}
          {business && <Link href="/dashboard" className="inline-flex items-center gap-1 text-sm text-gray-600 hover:underline"><LayoutDashboard size={15} /> My business</Link>}
          <span className="hidden text-sm text-gray-500 sm:inline">{me.user.email}</span>
          <button onClick={logout} className="inline-flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900"><LogOut size={15} /> Sign out</button>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
    </div>
  );
}

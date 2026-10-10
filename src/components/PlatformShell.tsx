"use client";

import { Briefcase, LayoutDashboard, Shield, Store } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { NotificationBell } from "@/components/NotificationBell";
import { UserBar } from "@/components/UserBar";
import { Loading } from "@/components/ui";
import { useAuth } from "@/lib/auth";

/** Frame for the platform-level portals (super admin, reseller) — separate from business data. */
export function PlatformShell({ need, children }: { need: "SUPERADMIN" | "RESELLER"; children: React.ReactNode }) {
  const { me, loading, business } = useAuth();
  const router = useRouter();
  // the admin panel also opens for company team members (they see only their areas)
  const allowed = me?.platform_role === need || (need === "RESELLER" && me?.platform_role === "SUPERADMIN")
    || (need === "SUPERADMIN" && me?.platform_role === "TEAM" && (me.platform_areas?.length ?? 0) > 0);

  useEffect(() => {
    if (!loading && !me) router.replace("/login");
  }, [loading, me, router]);

  if (loading || !me) return <Loading />;
  if (!allowed) return <div className="p-10 text-center text-sm text-gray-600">This area is for {need === "SUPERADMIN" ? "platform administrators" : "resellers"} only.</div>;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-gray-200 bg-white">
        <div className="mx-auto flex h-14 max-w-[90rem] items-center gap-4 px-4">
          <div className="flex items-center gap-2 font-semibold text-gray-900">
            {need === "SUPERADMIN" ? <Shield size={18} className="text-brand-600" /> : <Store size={18} className="text-brand-600" />}
            {need === "SUPERADMIN" ? (me.platform_role === "TEAM" ? "Admin panel" : "Super Admin") : "Reseller Portal"}
          </div>
          <div className="flex-1" />
          {me.platform_role === "SUPERADMIN" && need === "SUPERADMIN" && <Link href="/reseller" className="text-sm text-gray-600 hover:underline">Reseller view</Link>}
          {me.practice_clients > 0 && <Link href="/practice" className="inline-flex items-center gap-1 text-sm text-gray-600 hover:underline"><Briefcase size={15} /> Practice</Link>}
          {business && <Link href="/dashboard" className="inline-flex items-center gap-1 text-sm text-gray-600 hover:underline"><LayoutDashboard size={15} /> My business</Link>}
          <NotificationBell />
          <UserBar />
        </div>
      </header>
      <main className="mx-auto max-w-[90rem] px-4 py-6">{children}</main>
    </div>
  );
}

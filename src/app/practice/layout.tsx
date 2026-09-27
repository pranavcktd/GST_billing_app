"use client";

import { Briefcase, LayoutDashboard } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { BrandLogo } from "@/components/BrandLogo";
import { UserBar } from "@/components/UserBar";
import { Loading } from "@/components/ui";
import { useAuth } from "@/lib/auth";

/** Practitioner workspace frame — independent of any one business. */
export default function PracticeLayout({ children }: { children: React.ReactNode }) {
  const { me, loading, business } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !me) router.replace("/login");
    else if (!loading && me?.must_change_password) router.replace("/change-password");
  }, [loading, me, router]);

  if (loading || !me) return <Loading />;

  return (
    <div className="min-h-screen">
      <header className="no-print sticky top-0 z-20 border-b border-gray-200 bg-white">
        <div className="mx-auto flex h-14 max-w-[90rem] items-center gap-4 px-4">
          <Link href="/practice"><BrandLogo size="sm" /></Link>
          <Link href="/practice" className="hidden items-center gap-1.5 rounded-md bg-brand-50 px-2.5 py-1 text-sm font-medium text-brand-700 sm:inline-flex">
            <Briefcase size={15} /> Practitioner workspace
          </Link>
          <div className="flex-1" />
          {business && <Link href="/dashboard" className="hidden items-center gap-1 text-sm text-gray-600 hover:underline md:inline-flex"><LayoutDashboard size={15} /> My business</Link>}
          <UserBar />
        </div>
      </header>
      <main className="mx-auto max-w-[90rem] px-4 py-6">{children}</main>
    </div>
  );
}

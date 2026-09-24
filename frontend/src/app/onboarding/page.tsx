"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { BusinessForm, emptyBusiness } from "@/components/BusinessForm";
import { Loading } from "@/components/ui";
import { api, session } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { MyBusiness } from "@/lib/types";

export default function OnboardingPage() {
  const { me, loading, refresh } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !me) router.replace("/login");
  }, [loading, me, router]);

  if (loading || !me) return <Loading />;

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-2xl font-semibold text-gray-900">Set up your business</h1>
      <p className="mt-1 mb-6 text-sm text-gray-500">
        These details appear on your invoices. You can change them any time in Settings.
      </p>
      <BusinessForm
        initial={emptyBusiness}
        submitLabel="Create business"
        onSubmit={async (b) => {
          const created = await api<MyBusiness>("/businesses", { body: b });
          session.setBusinessId(created.id);
          await refresh();
          router.replace("/dashboard");
        }}
      />
    </div>
  );
}

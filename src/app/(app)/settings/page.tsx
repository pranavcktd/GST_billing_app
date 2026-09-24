"use client";

import { useState } from "react";
import { BusinessForm } from "@/components/BusinessForm";
import { ErrorBox, LinkButton, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFetch } from "@/lib/useFetch";
import type { Business } from "@/lib/types";

export default function SettingsPage() {
  const { refresh, business: mine } = useAuth();
  const { data, error, loading } = useFetch<Business>("/businesses/current");
  const [saved, setSaved] = useState(false);

  if (loading) return <Loading />;
  if (!data) return <ErrorBox message={error} />;
  const canEdit = mine?.role === "OWNER" || mine?.role === "ADMIN";

  return (
    <div className="max-w-4xl">
      <PageHeader
        title="Settings"
        sub="Business profile, GST details, bank details and invoice numbering"
        actions={<LinkButton href="/onboarding" variant="secondary">Add another business</LinkButton>}
      />
      {saved && <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">Settings saved.</div>}
      {!canEdit && <ErrorBox message="Only the owner or an admin can change business settings." />}
      <BusinessForm
        initial={data}
        showUploads
        submitLabel="Save settings"
        onSubmit={async (b) => {
          await api(`/businesses/current`, { method: "PUT", body: b });
          await refresh();
          setSaved(true);
          window.scrollTo({ top: 0, behavior: "smooth" });
        }}
      />
    </div>
  );
}

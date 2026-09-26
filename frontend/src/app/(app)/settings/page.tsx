"use client";

import { useState } from "react";
import { BusinessForm } from "@/components/BusinessForm";
import { PrintSettingsForm } from "@/components/PrintSettingsForm";
import { SecuritySettings } from "@/components/SecuritySettings";
import { SmtpForm } from "@/components/SmtpForm";
import { Button, Card, ErrorBox, Field, Input, LinkButton, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth, usePerms } from "@/lib/auth";
import { useFetch } from "@/lib/useFetch";
import type { Business, PrintSettings } from "@/lib/types";

const TABS = [
  { key: "business", label: "Business" },
  { key: "print", label: "Invoice & print" },
  { key: "einvoice", label: "e-Invoice" },
  { key: "email", label: "Email" },
  { key: "security", label: "Security" },
] as const;

export default function SettingsPage() {
  const { refresh, business: mine } = useAuth();
  const { can } = usePerms();
  const { data, error, loading, setData } = useFetch<Business>("/businesses/current");
  const [tab, setTab] = useState<(typeof TABS)[number]["key"]>(() => {
    const t = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("tab") : null;
    return TABS.find((x) => x.key === t)?.key ?? "business";
  });
  const [saved, setSaved] = useState<string | null>(null);

  if (loading) return <Loading />;
  if (!data) return <ErrorBox message={error} />;
  const canEdit = can("settings", "edit");

  async function saveBusiness(patch: Partial<Business> & Record<string, unknown>) {
    const updated = await api<Business>("/businesses/current", { method: "PUT", body: { ...data, ...patch } });
    setData(updated);
    await refresh();
    setSaved("Settings saved.");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <div className="max-w-7xl">
      <PageHeader title="Settings" sub="Business profile, invoice design, e-invoicing and security"
        actions={<LinkButton href="/utilities/companies" variant="secondary">Companies & staff</LinkButton>} />
      <div className="mb-5 flex flex-wrap gap-1 rounded-lg border border-gray-200 bg-white p-1 text-sm w-fit">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => { setTab(t.key); setSaved(null); }} className={`rounded-md px-4 py-1.5 ${tab === t.key ? "bg-brand-600 text-white" : "text-gray-700"}`}>{t.label}</button>
        ))}
      </div>
      {saved && <div className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{saved}</div>}
      {!canEdit && tab !== "security" && tab !== "email" && <ErrorBox message="Your role can view settings but not change them." />}

      {tab === "business" && (
        <div className="max-w-4xl">
          <BusinessForm initial={data} showUploads submitLabel="Save settings" onSubmit={(b) => saveBusiness(b as Partial<Business>)} />
        </div>
      )}
      {tab === "print" && <PrintSettingsForm business={data} onSave={(ps: PrintSettings) => saveBusiness({ print_settings: ps })} />}
      {tab === "einvoice" && <EInvoiceSettings business={data} onSave={saveBusiness} />}
      {tab === "email" && (
        <SmtpForm base="/smtp" canEdit={canEdit} title="E-mail for this business"
          help="Invoices, payment reminders and backups you e-mail go out from this address. Leave empty to use your reseller's or the platform's mail server." />
      )}
      {tab === "security" && <SecuritySettings canApprove={["OWNER", "ADMIN", "MANAGER"].includes(mine?.role ?? "")} />}
    </div>
  );
}

function EInvoiceSettings({ business, onSave }: { business: Business; onSave: (p: Record<string, unknown>) => Promise<void> }) {
  const [user, setUser] = useState(business.einvoice_username ?? "");
  const [pass, setPass] = useState("");
  const [err, setErr] = useState<string | null>(null);
  return (
    <Card className="max-w-2xl space-y-4 p-5">
      <h2 className="font-semibold text-gray-900">e-Invoice / e-Way bill API user</h2>
      <p className="text-sm text-gray-600">
        Create an API user on the e-invoice portal (einvoice1.gst.gov.in → API Registration → “Through GSP”, select our GSP) and enter it here.
        Without it you can still download the JSON and upload it on the portal yourself.
      </p>
      <p className="text-xs text-gray-500">Plan: {business.plan?.einvoice === "API" ? "direct generation included" : business.plan?.einvoice === "JSON" ? "JSON download (upgrade to Professional for direct generation)" : "not included — upgrade to Starter"}</p>
      <ErrorBox message={err} />
      <Field label="API username"><Input value={user} onChange={(e) => setUser(e.target.value)} /></Field>
      <Field label="API password" hint={business.einvoice_password_set ? "A password is saved — leave blank to keep it" : "Stored encrypted"}>
        <Input type="password" value={pass} onChange={(e) => setPass(e.target.value)} autoComplete="new-password" />
      </Field>
      <div className="flex justify-end">
        <Button onClick={() => onSave({ einvoice_username: user || null, einvoice_password: pass || null }).catch((e) => setErr(e.message))}>Save</Button>
      </div>
    </Card>
  );
}

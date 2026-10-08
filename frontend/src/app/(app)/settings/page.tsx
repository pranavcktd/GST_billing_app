"use client";

import { useState } from "react";
import { BusinessForm } from "@/components/BusinessForm";
import { PrintSettingsForm } from "@/components/PrintSettingsForm";
import { SecuritySettings } from "@/components/SecuritySettings";
import { SmtpForm } from "@/components/SmtpForm";
import { Button, Card, ErrorBox, Field, Input, LinkButton, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth, usePerms } from "@/lib/auth";
import { BrandName } from "@/lib/config";
import { useFetch } from "@/lib/useFetch";
import type { Business, PrintSettings } from "@/lib/types";
import { ReminderSettings } from "@/components/ReminderSettings";
import { PortalLink } from "@/components/PortalLink";
import { ModuleSettings } from "@/components/ModuleSettings";

const TABS = [
  { key: "business", label: "Business" },
  { key: "print", label: "Invoice & print" },
  { key: "einvoice", label: "e-Invoice" },
  { key: "email", label: "Email" },
  { key: "reminders", label: "Reminders" },
  { key: "modules", label: "Modules" },
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
      {!canEdit && tab !== "security" && tab !== "email" && tab !== "reminders" && tab !== "modules" && <ErrorBox message="Your role can view settings but not change them." />}

      {tab === "business" && (
        <div className="max-w-4xl">
          <BusinessForm initial={data} portal={data.gst_portal} showUploads submitLabel="Save settings" onSubmit={(b) => saveBusiness(b as Partial<Business>)} />
        </div>
      )}
      {tab === "print" && <PrintSettingsForm business={data} onSave={(ps: PrintSettings) => saveBusiness({ print_settings: ps })} />}
      {tab === "einvoice" && <EInvoiceSettings business={data} onSave={saveBusiness} />}
      {tab === "email" && (
        <SmtpForm base="/smtp" canEdit={canEdit} title="E-mail for this business"
          help="Invoices, payment reminders and backups you e-mail go out from this address. Leave empty to use your reseller's or the platform's mail server." />
      )}
      {tab === "reminders" && <ReminderSettings canEdit={canEdit} />}
      {tab === "modules" && <ModuleSettings canEdit={canEdit} />}
      {tab === "security" && <SecuritySettings canApprove={["OWNER", "ADMIN", "MANAGER"].includes(mine?.role ?? "")} />}
    </div>
  );
}

function EInvoiceSettings({ business, onSave }: { business: Business; onSave: (p: Record<string, unknown>) => Promise<void> }) {
  const { data: setup } = useFetch<{ live: boolean; test_mode: boolean | null; sandbox: boolean; gsp_name: string | null; plan: string | null }>("/einvoice/setup");
  const [f, setF] = useState({ einvoice_applicable: !!business.einvoice_applicable, einvoice_username: business.einvoice_username ?? "", einvoice_password: "",
    ewb_username: business.ewb_username ?? "", ewb_password: "" });
  const [err, setErr] = useState<string | null>(null);
  const gsp = setup?.gsp_name || "the GSP named by SmartHisab";
  const plan = business.plan?.einvoice;
  return (
    <div className="max-w-3xl space-y-4">
      <Card className="space-y-2 p-5">
        <h2 className="font-semibold text-gray-900">e-Invoice & e-Way bill</h2>
        <p className="text-sm text-gray-600">
          {setup?.live
            ? <>Direct generation from <BrandName /> is <b className="text-emerald-700">on</b>{setup.test_mode ? <> — <b className="text-amber-700">test mode</b>: numbers start with TEST and nothing is filed yet</> : ""}.</>
            : <>Direct generation is not switched on yet. You can still download the JSON, upload it on the portal and record the IRN / e-way bill number on the bill.</>}
        </p>
        <p className="text-xs text-gray-500">Your plan: {plan === "API" ? "JSON + direct generation" : plan === "JSON" ? "JSON download (direct generation on paid plans)" : "not included — upgrade to Starter"}</p>
        <label className="flex items-start gap-2.5 pt-2 text-sm">
          <input type="checkbox" className="mt-0.5" checked={f.einvoice_applicable} onChange={(e) => setF({ ...f, einvoice_applicable: e.target.checked })} />
          <span><b>e-Invoicing applies to us</b><span className="block text-xs text-gray-500">Aggregate turnover above the notified limit (₹5 crore today). B2B invoices without an IRN are then flagged so they are not missed.</span></span>
        </label>
      </Card>

      <Card className="space-y-3 p-5">
        <h3 className="font-semibold text-gray-900">One-time setup on the government portals</h3>
        <ol className="list-decimal space-y-1.5 pl-5 text-sm text-gray-700">
          <li>e-Invoice: sign in on the <PortalLink to="einvoice_portal">e-invoice portal</PortalLink> → <b>API Registration</b> → <b>Create API User</b> → <b>Through GSP</b> → choose <b>{gsp}</b>. Set a username and password.</li>
          <li>e-Way bill: sign in on the <PortalLink to="ewaybill_portal">e-way bill portal</PortalLink> → <b>Registration</b> → <b>For GSP</b> → choose <b>{gsp}</b> → add an API username and password.</li>
          <li>Enter both below. They are stored encrypted and used only to file your own invoices and e-way bills.</li>
        </ol>
        <ErrorBox message={err} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="e-Invoice API username" info={false}><Input value={f.einvoice_username} onChange={(e) => setF({ ...f, einvoice_username: e.target.value })} /></Field>
          <Field label="e-Invoice API password" info={false} hint={business.einvoice_password_set ? "Saved — leave blank to keep it" : "Stored encrypted"}>
            <Input type="password" autoComplete="new-password" value={f.einvoice_password} onChange={(e) => setF({ ...f, einvoice_password: e.target.value })} />
          </Field>
          <Field label="e-Way bill API username" info={false}><Input value={f.ewb_username} onChange={(e) => setF({ ...f, ewb_username: e.target.value })} /></Field>
          <Field label="e-Way bill API password" info={false} hint={business.ewb_password_set ? "Saved — leave blank to keep it" : "Stored encrypted"}>
            <Input type="password" autoComplete="new-password" value={f.ewb_password} onChange={(e) => setF({ ...f, ewb_password: e.target.value })} />
          </Field>
        </div>
        <div className="flex justify-end">
          <Button onClick={() => onSave({ einvoice_applicable: f.einvoice_applicable, einvoice_username: f.einvoice_username || null,
            einvoice_password: f.einvoice_password || null, ewb_username: f.ewb_username || null, ewb_password: f.ewb_password || null })
            .catch((e) => setErr(e.message))}>Save</Button>
        </div>
      </Card>
    </div>
  );
}

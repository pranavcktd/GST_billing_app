"use client";

import { BarChart3, Search } from "lucide-react";
import { useState } from "react";
import { Modal } from "@/components/Modal";
import { Button, Card, Input, Loading, Select } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { downloadCsv, fmtDate } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";

interface Top { key: string; visitors: number; views: number }
interface Overview {
  days: number; since: string;
  series: { day: string; visitors: number; views: number; active_users: number }[];
  totals: { visitors: number; views: number; signups: number; set_up_business: number; paid_accounts: number; dau: number; wau: number; mau: number };
  pages: Top[]; referrers: Top[]; campaigns: Top[]; devices: Top[];
  plans: { plan: string; clicks: number; visitors: number; users: number; cycles: Record<string, number> }[];
  pricing_views: { visitors: number; users: number };
  modules: { module: string; views: number; users: number; businesses: number }[];
  settings: { enabled: boolean; respect_dnt: boolean; keep_days: number };
}
interface Person { user_id: string; name: string; email: string; businesses: string[]; plan: string | null; plan_status: string | null; views: number; active_days: number; last_at: string; modules: { module: string; views: number }[]; module_count: number }
interface PersonDetail {
  user: { id: string; name: string; email: string; created_at: string; last_login_at: string | null };
  modules: { module: string; business: string; views: number; days: number; last_at: string }[];
  per_day: { day: string; views: number }[];
  plan_interest: { kind: string; plan: string | null; cycle: string | null; at: string }[];
}

const cycleName = (c: string) => (c.startsWith("YEARS_") ? `${c.slice(6)} yrs` : c === "-" ? "—" : c.toLowerCase());

function Bars({ data }: { data: Overview["series"] }) {
  const max = Math.max(1, ...data.map((d) => Math.max(d.visitors, d.active_users)));
  return (
    <div>
      <div className="flex h-40 items-end gap-[2px]">
        {data.map((d) => (
          <div key={d.day} className="group relative flex h-full flex-1 items-end gap-[1px]" title={`${fmtDate(d.day)}: ${d.visitors} visitors, ${d.views} page views, ${d.active_users} active users`}>
            <div className="w-1/2 rounded-t bg-brand-500/80" style={{ height: `${(d.visitors / max) * 100}%` }} />
            <div className="w-1/2 rounded-t bg-emerald-500/80" style={{ height: `${(d.active_users / max) * 100}%` }} />
          </div>
        ))}
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-gray-400"><span>{fmtDate(data[0]?.day)}</span><span>{fmtDate(data[data.length - 1]?.day)}</span></div>
      <div className="mt-1 flex gap-4 text-xs text-gray-600">
        <span className="flex items-center gap-1"><i className="inline-block h-2 w-2 rounded-sm bg-brand-500" /> Website visitors</span>
        <span className="flex items-center gap-1"><i className="inline-block h-2 w-2 rounded-sm bg-emerald-500" /> Active app users</span>
      </div>
    </div>
  );
}

function TopList({ title, rows }: { title: string; rows: Top[] }) {
  const max = Math.max(1, ...rows.map((r) => r.visitors));
  return (
    <Card className="p-4">
      <h3 className="mb-2 text-sm font-semibold text-gray-900">{title}</h3>
      {rows.length === 0 ? <p className="text-xs text-gray-500">No data yet.</p> : rows.map((r) => (
        <div key={r.key} className="relative mb-1 flex justify-between overflow-hidden rounded px-2 py-1 text-xs">
          <span className="absolute inset-y-0 left-0 bg-brand-50" style={{ width: `${(r.visitors / max) * 100}%` }} />
          <span className="relative truncate text-gray-700">{r.key}</span><span className="relative tabular-nums text-gray-600">{r.visitors}</span>
        </div>
      ))}
    </Card>
  );
}

/** Admin → Analytics: website visitors, plan interest, the funnel, and which modules people use. */
export function AdminAnalytics() {
  const { me } = useAuth();
  const [days, setDays] = useState(30);
  const [view, setView] = useState<"overview" | "modules" | "people">("overview");
  const { data, reload } = useFetch<Overview>(`/admin/analytics?days=${days}`);
  const [q, setQ] = useState("");
  const [module, setModule] = useState("");
  const { data: people } = useFetch<Person[]>(view === "people" ? `/admin/analytics/users${qs({ days, q, module })}` : null);
  const [person, setPerson] = useState<string | null>(null);

  if (!data) return <Loading />;
  const t = data.totals;
  const maxModule = Math.max(1, ...data.modules.map((m) => m.users));
  const funnel: [string, number][] = [["Website visitors", t.visitors], ["Signed up", t.signups], ["Set up a business", t.set_up_business], ["Paid (live)", t.paid_accounts]];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900"><BarChart3 size={18} className="text-brand-600" /> Analytics</h2>
          <p className="text-sm text-gray-500">First-party only — a random browser id, no IP addresses, nothing shared with third parties.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-lg border border-gray-200 bg-white p-0.5 text-sm">
            {(["overview", "modules", "people"] as const).map((v) => (
              <button key={v} onClick={() => setView(v)} className={`rounded-md px-3 py-1.5 capitalize ${view === v ? "bg-brand-600 text-white" : "text-gray-700"}`}>
                {v === "people" ? "Users" : v === "modules" ? "Module usage" : "Overview"}
              </button>
            ))}
          </div>
          <Select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option><option value={365}>Last 12 months</option>
          </Select>
        </div>
      </div>
      {!data.settings.enabled && <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">Analytics is switched off — nothing new is being collected.</p>}

      {view === "overview" && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {([["Website visitors", t.visitors], ["Page views", t.views], ["Active today", t.dau], ["Active this week / month", `${t.wau} / ${t.mau}`]] as [string, number | string][]).map(([l, v]) => (
              <Card key={l} className="p-4"><div className="text-xs text-gray-500">{l}</div><div className="mt-1 text-2xl font-semibold">{v}</div></Card>
            ))}
          </div>
          <Card className="p-4"><Bars data={data.series} /></Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="p-4">
              <h3 className="mb-3 text-sm font-semibold text-gray-900">Funnel ({data.days} days)</h3>
              {funnel.map(([l, v], i) => (
                <div key={l} className="mb-2">
                  <div className="flex justify-between text-xs text-gray-600"><span>{l}</span><span className="tabular-nums">{v}{i > 0 && funnel[i - 1][1] ? ` · ${Math.round((v / funnel[i - 1][1]) * 100)}%` : ""}</span></div>
                  <div className="mt-1 h-2 rounded-full bg-gray-100"><div className="h-2 rounded-full bg-brand-500" style={{ width: `${funnel[0][1] ? Math.max(2, (v / Math.max(funnel[0][1], v)) * 100) : 0}%` }} /></div>
                </div>
              ))}
            </Card>
            <Card className="overflow-x-auto p-4">
              <h3 className="mb-1 text-sm font-semibold text-gray-900">Plans explored</h3>
              <p className="mb-2 text-xs text-gray-500">Pricing seen by {data.pricing_views.visitors} visitor(s) and {data.pricing_views.users} signed-in user(s).</p>
              {data.plans.length === 0 ? <p className="text-xs text-gray-500">No plan clicks yet.</p> : (
                <table className="tbl"><thead><tr><th>Plan</th><th className="num">Clicks</th><th className="num">Visitors</th><th className="num">Users</th><th>Billing cycle</th></tr></thead>
                  <tbody>{data.plans.map((p) => (
                    <tr key={p.plan}><td>{p.plan}</td><td className="num">{p.clicks}</td><td className="num">{p.visitors}</td><td className="num">{p.users}</td>
                      <td className="text-xs">{Object.entries(p.cycles).map(([c, n]) => `${cycleName(c)} ${n}`).join(" · ")}</td></tr>
                  ))}</tbody></table>
              )}
            </Card>
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <TopList title="Top pages" rows={data.pages} /><TopList title="Came from" rows={data.referrers} />
            <TopList title="Campaigns (utm_source)" rows={data.campaigns.filter((c) => c.key !== "(direct)")} /><TopList title="Devices" rows={data.devices} />
          </div>
        </>
      )}

      {view === "modules" && (
        <Card className="overflow-x-auto">
          <div className="flex items-center justify-between px-5 pt-4 pb-2">
            <p className="text-sm text-gray-500">Which parts of the app people open — most used first. Click a module to see who uses it.</p>
            <Button variant="secondary" onClick={() => downloadCsv("module-usage.csv", ["Module", "Users", "Businesses", "Opens"], data.modules.map((m) => [m.module, m.users, m.businesses, m.views]))}>CSV</Button>
          </div>
          {data.modules.length === 0 ? <p className="p-5 text-sm text-gray-500">No usage recorded yet.</p> : (
            <table className="tbl">
              <thead><tr><th>Module</th><th>Users</th><th className="num">Businesses</th><th className="num">Opens</th></tr></thead>
              <tbody>{data.modules.map((m) => (
                <tr key={m.module} className="cursor-pointer hover:bg-gray-50" onClick={() => { setModule(m.module); setView("people"); }}>
                  <td className="font-medium">{m.module}</td>
                  <td><div className="flex items-center gap-2"><div className="h-2 w-32 rounded-full bg-gray-100"><div className="h-2 rounded-full bg-emerald-500" style={{ width: `${(m.users / maxModule) * 100}%` }} /></div><span className="tabular-nums text-xs">{m.users}</span></div></td>
                  <td className="num">{m.businesses}</td><td className="num">{m.views}</td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </Card>
      )}

      {view === "people" && (
        <>
          <div className="flex flex-wrap gap-2">
            <div className="relative"><Search size={15} className="absolute top-2.5 left-2.5 text-gray-400" />
              <Input className="!pl-8" placeholder="Name or e-mail" value={q} onChange={(e) => setQ(e.target.value)} /></div>
            <Select value={module} onChange={(e) => setModule(e.target.value)}>
              <option value="">Any module</option>{data.modules.map((m) => <option key={m.module} value={m.module}>{m.module}</option>)}
            </Select>
          </div>
          <Card className="overflow-x-auto">
            {!people ? <Loading /> : people.length === 0 ? <p className="p-5 text-sm text-gray-500">Nobody yet.</p> : (
              <table className="tbl">
                <thead><tr><th>User</th><th>Plan</th><th className="num">Days active</th><th className="num">Opens</th><th>Uses most</th><th>Last seen</th></tr></thead>
                <tbody>{people.map((p) => (
                  <tr key={p.user_id} className="cursor-pointer hover:bg-gray-50" onClick={() => setPerson(p.user_id)}>
                    <td>{p.name}<div className="text-xs text-gray-500">{p.email}{p.businesses.length ? ` · ${p.businesses.join(", ")}` : ""}</div></td>
                    <td className="text-xs">{p.plan ?? "—"}{p.plan_status ? ` · ${p.plan_status.toLowerCase()}` : ""}</td>
                    <td className="num">{p.active_days}</td><td className="num">{p.views}</td>
                    <td className="text-xs">{p.modules.slice(0, 3).map((m) => `${m.module} (${m.views})`).join(", ")}{p.module_count > 3 ? ` +${p.module_count - 3}` : ""}</td>
                    <td className="text-xs whitespace-nowrap">{fmtDate(p.last_at)}</td>
                  </tr>
                ))}</tbody>
              </table>
            )}
          </Card>
        </>
      )}

      {me?.platform_role === "SUPERADMIN" && <TrackingSettings s={data.settings} onSaved={reload} />}
      {person && <PersonModal id={person} onClose={() => setPerson(null)} />}
    </div>
  );
}

function PersonModal({ id, onClose }: { id: string; onClose: () => void }) {
  const { data } = useFetch<PersonDetail>(`/admin/analytics/users/${id}?days=90`);
  return (
    <Modal title={data ? data.user.name : "User"} onClose={onClose} wide>
      {!data ? <Loading /> : (
        <div className="space-y-4 text-sm">
          <p className="text-xs text-gray-500">{data.user.email} · joined {fmtDate(data.user.created_at)} · last sign-in {fmtDate(data.user.last_login_at)} · last 90 days</p>
          <table className="tbl">
            <thead><tr><th>Module</th><th>Business</th><th className="num">Opens</th><th className="num">Days</th><th>Last</th></tr></thead>
            <tbody>{data.modules.map((m, i) => <tr key={i}><td>{m.module}</td><td className="text-xs">{m.business}</td><td className="num">{m.views}</td><td className="num">{m.days}</td><td className="text-xs">{fmtDate(m.last_at)}</td></tr>)}</tbody>
          </table>
          {data.plan_interest.length > 0 && (
            <div>
              <div className="mb-1 text-xs font-semibold text-gray-500 uppercase">Plan interest</div>
              <p className="text-xs text-gray-600">{data.plan_interest.map((e) => `${fmtDate(e.at)}: ${e.kind === "PLAN_CLICK" ? `clicked ${e.plan} (${cycleName(e.cycle ?? "-")})` : e.kind === "CYCLE" ? `looked at ${cycleName(e.cycle ?? "-")}` : "opened pricing"}`).join(" · ")}</p>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

function TrackingSettings({ s, onSaved }: { s: Overview["settings"]; onSaved: () => void }) {
  const [f, setF] = useState(s);
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <Card className="flex flex-wrap items-end gap-4 p-4 text-sm">
      <label className="flex items-center gap-2"><input type="checkbox" checked={f.enabled} onChange={(e) => setF({ ...f, enabled: e.target.checked })} /> Collect analytics</label>
      <label className="flex items-center gap-2"><input type="checkbox" checked={f.respect_dnt} onChange={(e) => setF({ ...f, respect_dnt: e.target.checked })} /> Skip browsers that send “Do Not Track”</label>
      <label className="flex items-center gap-2">Keep for <Input type="number" className="!w-24" value={f.keep_days} onChange={(e) => setF({ ...f, keep_days: Number(e.target.value) })} /> days</label>
      <Button variant="secondary" onClick={async () => { await api("/admin/analytics/settings", { method: "PUT", body: f }); setMsg("Saved"); onSaved(); }}>Save</Button>
      {msg && <span className="text-emerald-700">{msg}</span>}
    </Card>
  );
}

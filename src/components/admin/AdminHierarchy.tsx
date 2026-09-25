"use client";

import { Building2, ChevronDown, ChevronRight, Shield, Store, User, Users } from "lucide-react";
import { useState } from "react";
import { Card, Loading } from "@/components/ui";
import { useFetch } from "@/lib/useFetch";

interface Staff { id: string; name: string; email: string; role: string; active: boolean }
interface BizNode { id: string; name: string; gstin: string | null; staff: Staff[] }
interface Account { id: string; name: string; email: string; active: boolean; plan: string; status: string; businesses: BizNode[] }
interface Tree {
  superadmins: { id: string; name: string; email: string; active: boolean }[];
  resellers: { id: string; name: string; email: string; active: boolean; commission_pct: number; accounts: Account[] }[];
  direct_accounts: Account[];
}

function Row({ icon: Icon, title, sub, inactive, children, open: initial = false }: {
  icon: React.ElementType; title: string; sub?: string; inactive?: boolean; children?: React.ReactNode; open?: boolean;
}) {
  const [open, setOpen] = useState(initial);
  const has = !!children;
  return (
    <div>
      <button className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-gray-50 ${inactive ? "text-gray-400" : "text-gray-800"}`}
        onClick={() => has && setOpen(!open)}>
        {has ? (open ? <ChevronDown size={14} /> : <ChevronRight size={14} />) : <span className="w-3.5" />}
        <Icon size={15} className="shrink-0 text-gray-500" />
        <span className="font-medium">{title}</span>
        {sub && <span className="truncate text-xs text-gray-500">{sub}</span>}
        {inactive && <span className="text-xs text-red-600">inactive</span>}
      </button>
      {open && has && <div className="ml-5 border-l border-gray-200 pl-2">{children}</div>}
    </div>
  );
}

function AccountNode({ a }: { a: Account }) {
  return (
    <Row icon={User} title={a.name} sub={`${a.email} · ${a.plan}${a.status === "TRIAL" ? " (trial)" : ""}`} inactive={!a.active}>
      {a.businesses.length ? a.businesses.map((b) => (
        <Row key={b.id} icon={Building2} title={b.name} sub={b.gstin ?? "no GSTIN"}>
          {b.staff.length ? b.staff.map((s) => <Row key={s.id} icon={Users} title={s.name} sub={`${s.email} · ${s.role.toLowerCase()}`} inactive={!s.active} />)
            : <div className="px-2 py-1 text-xs text-gray-400">No staff</div>}
        </Row>
      )) : <div className="px-2 py-1 text-xs text-gray-400">No business set up yet</div>}
    </Row>
  );
}

/** Platform → resellers → accounts → businesses → staff. */
export function AdminHierarchy() {
  const { data } = useFetch<Tree>("/admin/hierarchy");
  if (!data) return <Loading />;
  return (
    <Card className="p-4">
      <Row icon={Shield} title={`Super admins (${data.superadmins.length})`} open>
        {data.superadmins.map((u) => <Row key={u.id} icon={Shield} title={u.name} sub={u.email} inactive={!u.active} />)}
      </Row>
      <Row icon={Store} title={`Resellers (${data.resellers.length})`} open>
        {data.resellers.map((r) => (
          <Row key={r.id} icon={Store} title={r.name} sub={`${r.email} · ${r.commission_pct}% · ${r.accounts.length} account(s)`} inactive={!r.active}>
            {r.accounts.length ? r.accounts.map((a) => <AccountNode key={a.id} a={a} />) : <div className="px-2 py-1 text-xs text-gray-400">No accounts yet</div>}
          </Row>
        ))}
      </Row>
      <Row icon={Users} title={`Direct customers (${data.direct_accounts.length})`} open>
        {data.direct_accounts.map((a) => <AccountNode key={a.id} a={a} />)}
      </Row>
    </Card>
  );
}

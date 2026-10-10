"use client";

import { Bell, CheckCheck, CircleAlert, CircleCheck, LifeBuoy, XCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFetch } from "@/lib/useFetch";

interface Item { id: string; kind: string; title: string; body: string | null; link: string | null; read: boolean; created_at: string }

const ago = (iso: string) => {
  const m = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  if (m < 1440) return `${Math.round(m / 60)} h ago`;
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
};

function KindIcon({ kind }: { kind: string }) {
  if (kind === "PAYMENT_OK") return <CircleCheck size={16} className="shrink-0 text-emerald-600" />;
  if (kind === "PAYMENT_FAILED") return <XCircle size={16} className="shrink-0 text-red-600" />;
  if (kind.startsWith("TICKET")) return <LifeBuoy size={16} className="shrink-0 text-brand-600" />;
  return <CircleAlert size={16} className="shrink-0 text-amber-600" />;
}

/** The bell: alerts for this person (payments, tickets …), checked every minute. */
export function NotificationBell() {
  const { me } = useAuth();
  const router = useRouter();
  const { data: count, reload: reloadCount } = useFetch<{ unread: number }>(me ? "/notifications/unread" : null, { refreshMs: 60000 });
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Item[] | null>(null);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  if (!me) return null;
  const unread = count?.unread ?? 0;

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next) setItems((await api<{ items: Item[] }>("/notifications")).items);
  }
  async function readAll() {
    await api("/notifications/read", { body: { ids: null } });
    setItems((l) => l?.map((i) => ({ ...i, read: true })) ?? null);
    reloadCount();
  }
  async function openItem(i: Item) {
    if (!i.read) await api("/notifications/read", { body: { ids: [i.id] } }).catch(() => undefined);
    reloadCount();
    setOpen(false);
    if (i.link) router.push(i.link);
  }

  return (
    <div className="relative" ref={box}>
      <button onClick={toggle} aria-label={`Notifications${unread ? ` (${unread} new)` : ""}`}
        className="relative rounded-lg p-2 text-gray-600 hover:bg-gray-100">
        <Bell size={19} />
        {unread > 0 && <span className="absolute -top-0.5 -right-0.5 min-w-4 rounded-full bg-red-600 px-1 text-center text-[10px] leading-4 font-semibold text-white">{unread > 99 ? "99+" : unread}</span>}
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-[22rem] max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-gray-200 bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-gray-100 px-4 py-2.5">
            <span className="text-sm font-semibold text-gray-900">Notifications</span>
            {unread > 0 && <button onClick={readAll} className="inline-flex items-center gap-1 text-xs text-brand-600 hover:underline"><CheckCheck size={13} /> Mark all read</button>}
          </div>
          <div className="max-h-[26rem] overflow-y-auto">
            {!items ? <p className="p-4 text-sm text-gray-500">Loading…</p> : items.length === 0 ? <p className="p-6 text-center text-sm text-gray-500">No notifications yet.</p> : items.map((i) => (
              <button key={i.id} onClick={() => openItem(i)}
                className={`flex w-full gap-2.5 border-b border-gray-50 px-4 py-3 text-left hover:bg-gray-50 ${i.read ? "" : "bg-brand-50/40"}`}>
                <KindIcon kind={i.kind} />
                <span className="min-w-0 flex-1">
                  <span className={`block text-sm ${i.read ? "text-gray-700" : "font-semibold text-gray-900"}`}>{i.title}</span>
                  {i.body && <span className="mt-0.5 line-clamp-2 block text-xs text-gray-500">{i.body}</span>}
                  <span className="mt-1 block text-[11px] text-gray-400">{ago(i.created_at)}</span>
                </span>
                {!i.read && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-brand-600" />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

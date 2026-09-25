"use client";

import { Clock, LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth";

const when = (d: string) =>
  new Date(d).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

/** Top-right: who is signed in, when they last signed in (before this session), and sign out. */
export function UserBar() {
  const { me, logout } = useAuth();
  if (!me) return null;
  return (
    <div className="flex items-center gap-3">
      <div className="hidden text-right leading-tight md:block">
        <div className="max-w-48 truncate text-sm font-medium text-gray-900" title={me.user.email}>{me.user.name}</div>
        <div className="flex items-center justify-end gap-1 text-[11px] text-gray-500" title="Your previous sign-in — if you don't recognise it, change your password">
          <Clock size={11} /> {me.previous_login_at ? `Last login ${when(me.previous_login_at)}` : "First sign-in"}
        </div>
      </div>
      <button onClick={logout} title="Sign out"
        className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-2.5 py-1.5 text-sm text-gray-700 hover:bg-gray-50">
        <LogOut size={15} /> <span className="hidden sm:inline">Logout</span>
      </button>
    </div>
  );
}

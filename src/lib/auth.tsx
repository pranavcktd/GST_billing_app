"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, session } from "./api";
import type { Action, Me, Module, MyBusiness } from "./types";

interface AuthState {
  me: Me | null;
  loading: boolean;
  business: MyBusiness | null;
  refresh: () => Promise<Me | null>;
  login: (token: string, me: Me) => void;
  logout: () => void;
  switchBusiness: (id: string) => void;
}

const AuthContext = createContext<AuthState | null>(null);

async function loadMe(): Promise<Me | null> {
  if (!session.token()) return null;
  try {
    return await api<Me>("/auth/me");
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [businessId, setBusinessId] = useState<string | null>(null);

  const pickBusiness = useCallback((m: Me) => {
    const saved = session.businessId();
    const chosen = m.businesses.find((b) => b.id === saved) ?? m.businesses[0] ?? null;
    session.setBusinessId(chosen?.id ?? null);
    setBusinessId(chosen?.id ?? null);
  }, []);

  const refresh = useCallback(async () => {
    const m = await loadMe();
    setMe(m);
    if (m) pickBusiness(m);
    setLoading(false);
    return m;
  }, [pickBusiness]);

  useEffect(() => {
    let cancelled = false;
    loadMe().then((m) => {
      if (cancelled) return;
      setMe(m);
      if (m) pickBusiness(m);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [pickBusiness]);

  const login = (token: string, m: Me) => {
    session.setToken(token);
    setMe(m);
    pickBusiness(m);
  };

  const logout = () => {
    session.setToken(null);
    session.setBusinessId(null);
    setMe(null);
    window.location.href = "/login";
  };

  const switchBusiness = (id: string) => {
    session.setBusinessId(id);
    setBusinessId(id);
    window.location.href = "/dashboard";
  };

  const business = me?.businesses.find((b) => b.id === businessId) ?? null;

  return (
    <AuthContext.Provider value={{ me, loading, business, refresh, login, logout, switchBusiness }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

/** Permission checks for the active business (mirror of the server's rules — the server always decides). */
export function usePerms() {
  const { business } = useAuth();
  const p = business?.permissions;
  const can = (module: Module, action: Action = "view") => !!p?.modules?.[module]?.includes(action);
  const flag = (f: "view_cost" | "edit_past") => !!p?.flags?.includes(f);
  return { can, flag, role: business?.role };
}

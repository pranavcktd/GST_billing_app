"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

interface State<T> {
  key: string | null;
  data: T | null;
  error: string | null;
}

/** Minimal data loader: refetches whenever `path` changes; pass null to skip. `refreshMs` reloads it periodically. */
export function useFetch<T>(path: string | null, opts: { refreshMs?: number } = {}) {
  const { refreshMs } = opts;
  const [state, setState] = useState<State<T>>({ key: null, data: null, error: null });
  const [nonce, setNonce] = useState(0);
  const key = path === null ? null : `${path}#${nonce}`;

  useEffect(() => {
    if (path === null) return;
    let cancelled = false;
    const k = `${path}#${nonce}`;
    api<T>(path).then(
      (data) => !cancelled && setState({ key: k, data, error: null }),
      (e: Error) => !cancelled && setState((s) => ({ key: k, data: s.data, error: e.message })),
    );
    return () => {
      cancelled = true;
    };
  }, [path, nonce]);

  useEffect(() => {
    if (!refreshMs || path === null) return;
    const t = setInterval(() => setNonce((n) => n + 1), refreshMs);
    return () => clearInterval(t);
  }, [refreshMs, path]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  const setData = useCallback((data: T) => setState((s) => ({ ...s, data })), []);

  return { data: state.data, error: state.error, loading: key !== null && state.key !== key, reload, setData };
}

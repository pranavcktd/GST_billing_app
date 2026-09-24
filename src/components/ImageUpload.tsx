"use client";

import { useState } from "react";
import { api } from "@/lib/api";

/** Uploads an image to Cloudinary via the backend and returns its URL. */
export function ImageUpload({
  kind,
  value,
  onChange,
  label,
}: {
  kind: "logo" | "signature" | "item";
  value: string | null;
  onChange: (url: string | null) => void;
  label: string;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function upload(file: File) {
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("kind", kind);
      const res = await api<{ url: string }>("/uploads", { form });
      onChange(res.url);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <span className="mb-1 block text-xs font-medium text-gray-600">{label}</span>
      <div className="flex items-center gap-3">
        <div className="flex h-16 w-24 items-center justify-center overflow-hidden rounded-lg border border-dashed border-gray-300 bg-gray-50">
          {value ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={value} alt={label} className="max-h-full max-w-full object-contain" />
          ) : (
            <span className="text-xs text-gray-400">None</span>
          )}
        </div>
        <div className="flex flex-col gap-1 text-sm">
          <label className="cursor-pointer font-medium text-brand-600 hover:underline">
            {busy ? "Uploading…" : value ? "Replace" : "Upload"}
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="hidden"
              disabled={busy}
              onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
            />
          </label>
          {value && (
            <button type="button" className="text-left text-gray-500 hover:underline" onClick={() => onChange(null)}>
              Remove
            </button>
          )}
        </div>
      </div>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}

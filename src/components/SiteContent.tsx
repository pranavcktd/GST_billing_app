"use client";

import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import { LegalPage } from "@/components/LegalPage";
import { Loading } from "@/components/ui";
import { APP_NAME } from "@/lib/brand";
import { type AppConfig, useConfig } from "@/lib/config";
import { useFetch } from "@/lib/useFetch";

export interface SitePageData { slug: string; title: string; body: string | null; custom: boolean; updated_at: string | null }

/** Fill {{brand}}, {{company.x}}, {{legal.x|fallback}} and {{#if legal.x}}…{{/if}} from the live settings. */
export function fillPlaceholders(text: string, cfg: AppConfig): string {
  const val = (path: string): string => {
    const [group, key] = path.split(".");
    if (group === "brand") return cfg.brand?.app_name || APP_NAME;
    const src = (group === "company" ? cfg.company : group === "legal" ? cfg.legal : undefined) as Record<string, string> | undefined;
    return (key && src?.[key]) || "";
  };
  return text
    .replace(/\{\{#if ([\w.]+)\}\}([\s\S]*?)\{\{\/if\}\}/g, (_, path: string, inner: string) => (val(path) ? inner : ""))
    .replace(/\{\{([\w.]+)(?:\|([^}]*))?\}\}/g, (_, path: string, fallback?: string) => val(path) || fallback || "");
}

/** Markdown with the site's link and table styles (no raw HTML is rendered). */
export function Markdown({ text }: { text: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}
      components={{
        a: ({ href, children }) => href?.startsWith("/")
          ? <Link href={href} className="text-brand-600 underline">{children}</Link>
          : <a href={href} target="_blank" rel="noopener noreferrer" className="text-brand-600 underline">{children}</a>,
        blockquote: ({ children }) => <div className="rounded-lg bg-gray-50 px-4 py-3 text-gray-700 [&_p]:m-0">{children}</div>,
        table: ({ children }) => <div className="overflow-x-auto"><table>{children}</table></div>,
      }}>
      {text}
    </ReactMarkdown>
  );
}

function updatedText(iso: string | null): string {
  if (!iso) return "10 October 2026";
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
}

/** A policy page whose text the super admin edits in Admin → Website. */
export function SiteContentPage({ slug }: { slug: string }) {
  const cfg = useConfig();
  const { data } = useFetch<SitePageData>(`/site/${slug}`);
  if (!data) return <LegalPage title="" updated=""><Loading /></LegalPage>;
  return (
    <LegalPage title={data.title} updated={updatedText(data.updated_at)}>
      <Markdown text={fillPlaceholders(data.body ?? "", cfg)} />
    </LegalPage>
  );
}

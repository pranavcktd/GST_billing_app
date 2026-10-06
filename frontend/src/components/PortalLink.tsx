"use client";

import { ExternalLink } from "lucide-react";
import { useLink } from "@/lib/config";

/** A link to a government portal / external site. The address comes from the platform configuration,
 *  so the super admin can update it without a code change when a department moves a page. */
export function PortalLink({ to, children, button = false, className = "" }:
  { to: string; children: React.ReactNode; button?: boolean; className?: string }) {
  const href = useLink(to);
  const style = button
    ? "inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
    : "inline-flex items-center gap-1 text-brand-700 hover:underline";
  return (
    <a href={href} target="_blank" rel="noreferrer" className={`${style} ${className}`}>
      <ExternalLink size={button ? 15 : 13} /> {children}
    </a>
  );
}

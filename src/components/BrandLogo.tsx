"use client";

import { APP_NAME, BY_LINE } from "@/lib/brand";
import { useConfig } from "@/lib/config";

/** Product logo: icon + name, with the "by Corenexgen" line when there is room. */
export function BrandLogo({ size = "md", byLine = true }: { size?: "sm" | "md" | "lg"; byLine?: boolean }) {
  const brand = useConfig().brand;
  const icon = { sm: "h-7 w-7", md: "h-8 w-8", lg: "h-9 w-9" }[size];
  const text = { sm: "text-base", md: "text-lg", lg: "text-xl" }[size];
  return (
    <span className="flex items-center gap-2">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/icon.svg" alt="" className={icon} />
      <span className="leading-tight">
        <span className={`block font-bold tracking-tight text-gray-900 ${text}`}>{brand?.app_name || APP_NAME}</span>
        {byLine && <span className="block text-[10px] font-medium text-gray-500">{brand?.by_line || BY_LINE}</span>}
      </span>
    </span>
  );
}

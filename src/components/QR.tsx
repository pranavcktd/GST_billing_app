"use client";

import QRCode from "qrcode";
import { useEffect, useState } from "react";

/** Renders text as a QR code image (UPI payment links, e-invoice signed QR). */
export function QR({ value, size = 96, className = "" }: { value: string; size?: number; className?: string }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    QRCode.toDataURL(value, { margin: 0, width: size * 2, errorCorrectionLevel: "M" })
      .then((url) => alive && setSrc(url))
      .catch(() => alive && setSrc(null));
    return () => {
      alive = false;
    };
  }, [value, size]);
  // eslint-disable-next-line @next/next/no-img-element
  return src ? <img src={src} alt="QR code" width={size} height={size} className={className} /> : <div style={{ width: size, height: size }} />;
}

export function upiLink(upiId: string, payee: string, amount: number, note: string): string {
  const p = new URLSearchParams({ pa: upiId, pn: payee.slice(0, 40), am: amount.toFixed(2), cu: "INR", tn: note.slice(0, 60) });
  return `upi://pay?${p.toString()}`;
}

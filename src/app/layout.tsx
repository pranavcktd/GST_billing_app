import type { Metadata, Viewport } from "next";
import { Nunito_Sans } from "next/font/google";
import { Providers } from "@/components/Providers";
import { APP_NAME, BY_LINE, DESCRIPTION } from "@/lib/brand";
import "./globals.css";

// warm, rounded and very readable at small sizes
const appFont = Nunito_Sans({ variable: "--font-app", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: `${APP_NAME} ${BY_LINE} — billing, stock & accounts`, template: `%s · ${APP_NAME}` },
  description: DESCRIPTION,
  applicationName: APP_NAME,
  icons: { icon: [{ url: "/icon.svg", type: "image/svg+xml" }, { url: "/icon-192.png", sizes: "192x192", type: "image/png" }],
    apple: "/apple-touch-icon.png" },
  // installed on a phone's home screen: opens full screen like an app
  appleWebApp: { capable: true, title: APP_NAME, statusBarStyle: "default" },
};

export const viewport: Viewport = { themeColor: "#b8532a", width: "device-width", initialScale: 1, viewportFit: "cover" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${appFont.variable} h-full antialiased`}>
      <body className="min-h-full font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

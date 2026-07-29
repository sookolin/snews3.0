import "./globals.css";
import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { Providers } from "@/components/Providers";
import { FaviconLoader } from "@/components/FaviconLoader";

export const metadata: Metadata = {
  title: "SNEWS Admin",
  description: "SNEWS — news monitoring & publishing admin panel",
  manifest: "/manifest.webmanifest",
  // Standalone mode is what unlocks push notifications on iOS.
  appleWebApp: { capable: true, title: "SNEWS", statusBarStyle: "black-translucent" },
};

export const viewport: Viewport = {
  themeColor: "#0f172a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <head>
        <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
      </head>
      <body>
        <Providers>
          <FaviconLoader />
          {children}
        </Providers>
      </body>
    </html>
  );
}

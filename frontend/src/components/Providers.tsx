"use client";

import type { ReactNode } from "react";
import { ThemeProvider } from "next-themes";
import { ToastProvider } from "@/components/Toast";
import { ConfirmDialog } from "@/components/ConfirmDialog";

/** Client-side providers (theme, toasts, confirm dialog) rendered inside <body>. */
export function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      // "dim" is the third mode: dark page with a light sidebar.
      themes={["light", "dark", "dim"]}
      enableSystem
      disableTransitionOnChange
    >
      <ToastProvider>
        {children}
        <ConfirmDialog />
      </ToastProvider>
    </ThemeProvider>
  );
}

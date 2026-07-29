"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Menu, X } from "lucide-react";
import { getToken } from "@/lib/api";
import { Sidebar } from "@/components/Sidebar";
import { useProfileWatcher } from "@/lib/useProfileWatcher";

const COLLAPSE_KEY = "snews.sidebar.collapsed";

/** Authenticated shell: redirects to /login when no token is present. */
export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  // Desktop sidebar: false = full, true = icon-only
  const [collapsed, setCollapsed] = useState(false);

  // Poll for profile changes (role, permissions, is_active) — toast when changed by another user.
  useProfileWatcher();

  useEffect(() => {
    if (!getToken()) router.replace("/login");
    else setReady(true);
  }, [router]);

  useEffect(() => {
    setCollapsed(localStorage.getItem(COLLAPSE_KEY) === "1");
  }, []);

  const toggleCollapsed = () =>
    setCollapsed((v) => {
      localStorage.setItem(COLLAPSE_KEY, v ? "0" : "1");
      return !v;
    });

  // Close the mobile drawer on navigation.
  useEffect(() => setMenuOpen(false), [pathname]);

  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center text-muted-foreground">
        Загрузка…
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Desktop sidebar — shrinks to icon-only strip when collapsed. */}
      <div
        className={`hidden shrink-0 overflow-hidden transition-[width] duration-300 ease-in-out lg:block ${
          collapsed ? "w-16" : "w-60"
        }`}
      >
        <Sidebar onCollapse={toggleCollapsed} iconOnly={collapsed} />
      </div>

      {/* Mobile drawer */}
      {menuOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMenuOpen(false)} />
          <div className="relative h-full w-64">
            <Sidebar />
          </div>
        </div>
      )}

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile top bar */}
        <header className="flex h-14 items-center gap-3 border-b border-border bg-card px-4 lg:hidden">
          <button className="btn-icon" onClick={() => setMenuOpen((v) => !v)} aria-label="Меню">
            {menuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
          <span className="text-base font-semibold tracking-wide">SNEWS</span>
        </header>

        <main className="flex-1 overflow-y-auto p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}

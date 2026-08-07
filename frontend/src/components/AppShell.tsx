"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Menu, X, LogOut, Sun, Moon, SunMoon, UserCircle } from "lucide-react";
import Link from "next/link";
import { useTheme } from "next-themes";
import useSWR from "swr";
import { getToken, clearTokens, fetcher, tryTelegramWebAppLogin } from "@/lib/api";
import { Sidebar } from "@/components/Sidebar";
import { BellButton } from "@/components/BellButton";
import { useProfileWatcher } from "@/lib/useProfileWatcher";
import { useRoleLabels } from "@/lib/roles";
import { useNewsPing } from "@/lib/useNewsPing";
import { canAccessRoute, useMyPermissions } from "@/lib/permissions";

const COLLAPSE_KEY = "snews.sidebar.collapsed";

const THEMES = [
  { value: "dark",  label: "Тёмная тема",    icon: Moon },
  { value: "light", label: "Светлая тема",   icon: Sun },
  { value: "dim",   label: "Светлая + меню", icon: SunMoon },
] as const;

/** Authenticated shell: redirects to /login when no token is present. */
export function AppShell({ children }: { children: ReactNode }) {
  const router   = useRouter();
  const pathname = usePathname();
  const [ready, setReady]       = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [mounted, setMounted]   = useState(false);

  const { setTheme, theme } = useTheme();
  const { data: me } = useSWR<{ email: string; full_name?: string; role: string; photo_url?: string | null }>(
    "/auth/me", fetcher, { revalidateOnFocus: false }
  );
  const labels = useRoleLabels();

  useProfileWatcher();
  useNewsPing();
  const { permissions: myPermissions, isLoading: permsLoading } = useMyPermissions();

  useEffect(() => {
    if (getToken()) {
      setReady(true);
      return;
    }
    // No token yet: if opened as a Telegram Mini App, sign in automatically.
    tryTelegramWebAppLogin().then((ok) => {
      if (ok) setReady(true);
      else router.replace("/login");
    });
  }, [router]);

  // Route guard: block direct URL navigation to a page the current user has
  // no permission for — the sidebar hiding the link is not enough, typing
  // the URL must not work either.
  useEffect(() => {
    if (!ready || permsLoading) return;
    if (!canAccessRoute(myPermissions, pathname)) {
      router.replace("/dashboard");
    }
  }, [ready, permsLoading, myPermissions, pathname, router]);

  useEffect(() => {
    setCollapsed(localStorage.getItem(COLLAPSE_KEY) === "1");
    setMounted(true);
  }, []);

  const toggleCollapsed = () =>
    setCollapsed((v) => {
      localStorage.setItem(COLLAPSE_KEY, v ? "0" : "1");
      return !v;
    });

  useEffect(() => setMenuOpen(false), [pathname]);

  const current = mounted ? THEMES.findIndex((t) => t.value === theme) : -1;
  const next    = THEMES[(current + 1) % THEMES.length];
  const NextIcon = next.icon;

  const cycleTheme = () => {
    const root = document.documentElement;
    root.classList.add("theme-anim");
    window.setTimeout(() => root.classList.remove("theme-anim"), 300);
    setTheme(next.value);
  };

  const logout = () => {
    clearTokens();
    router.push("/login");
  };

  const initials = (me?.full_name || me?.email || "?").slice(0, 2).toUpperCase();

  const blocked = ready && !permsLoading && !canAccessRoute(myPermissions, pathname);

  if (!ready || permsLoading || blocked) {
    return (
      <div className="flex h-screen items-center justify-center text-muted-foreground">
        Загрузка…
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Desktop sidebar */}
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
        {/* Top bar */}
        <header className="flex h-14 items-center gap-2 border-b border-border bg-card px-4">
          {/* Hamburger — mobile only */}
          <button className="btn-icon lg:hidden" onClick={() => setMenuOpen((v) => !v)} aria-label="Меню">
            {menuOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
          </button>
          <span className="text-base font-semibold tracking-wide lg:hidden">SNEWS</span>

          <div className="flex-1" />

          {/* Notifications */}
          <BellButton />

          {/* Theme toggle */}
          {mounted && (
            <button
              className="btn-icon"
              title={next.label}
              aria-label={next.label}
              onClick={cycleTheme}
            >
              <NextIcon className="h-4 w-4" />
            </button>
          )}

          {/* Profile link — round hit-area matching the round avatar, so no
              square corners show outside the circular image/ring. */}
          <Link
            href="/profile"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-transform duration-200 ease-out hover:scale-105 active:scale-90"
            title={`${me?.full_name || me?.email || "Профиль"} · ${labels[me?.role ?? ""] ?? me?.role ?? ""}`}
            aria-label="Личный кабинет"
          >
            {me?.photo_url ? (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={me.photo_url}
                alt={me.full_name || me.email || "Аватар"}
                className="h-7 w-7 rounded-full object-cover ring-2 ring-sky-500/40"
                width={28}
                height={28}
              />
            ) : (
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-sky-600/20 text-xs font-semibold text-sky-600 dark:text-sky-300">
                {initials}
              </span>
            )}
          </Link>

          {/* Logout */}
          <button
            className="btn-icon"
            title="Выйти"
            aria-label="Выйти"
            onClick={logout}
          >
            <LogOut className="h-4 w-4" />
          </button>
        </header>

        <main className="flex-1 overflow-y-auto p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}

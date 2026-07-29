"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard, Newspaper, Radio, Building2, Send, FileText,
  Droplets, Image as ImageIcon, Bot, ListChecks, Users, ScrollText,
  Settings, LogOut, Sun, Moon, SunMoon, Megaphone, PlusCircle,
  PanelLeftClose, PanelLeftOpen, UserCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { cn } from "@/lib/utils";
import { clearTokens, fetcher } from "@/lib/api";
import { getPreviewRole, setPreviewRole, useRoleLabels } from "@/lib/roles";
import { useTheme } from "next-themes";

const SECTIONS: { title: string; items: { href: string; label: string; icon: typeof Newspaper }[] }[] = [
  {
    title: "Обзор",
    items: [{ href: "/dashboard", label: "Дашборд", icon: LayoutDashboard }],
  },
  {
    title: "Контент",
    items: [
      { href: "/news", label: "Новости", icon: Newspaper },
      { href: "/compose", label: "Создать пост", icon: PlusCircle },
      { href: "/ads", label: "Реклама", icon: Megaphone },
    ],
  },
  {
    title: "Сбор новостей",
    items: [
      { href: "/sources", label: "Источники", icon: Radio },
      { href: "/cities", label: "Города", icon: Building2 },
    ],
  },
  {
    title: "Публикация",
    items: [
      { href: "/channels", label: "Telegram-каналы", icon: Send },
      { href: "/templates", label: "Шаблоны", icon: FileText },
      { href: "/watermarks", label: "Водяной знак", icon: Droplets },
      { href: "/ai", label: "AI-обработка", icon: Bot },
    ],
  },
  {
    title: "Система",
    items: [
      { href: "/queue", label: "Очередь и мониторинг", icon: ListChecks },
      { href: "/users", label: "Пользователи", icon: Users },
      { href: "/logs", label: "Логи", icon: ScrollText },
      { href: "/settings", label: "Настройки", icon: Settings },
    ],
  },
];

const ITEM_PERMISSION: Record<string, string> = {
  "/news": "news:view",
  "/compose": "news:edit",
  "/ads": "channel:manage",
  "/sources": "source:view",
  "/cities": "city:view",
  "/channels": "channel:manage",
  "/templates": "template:manage",
  "/watermarks": "watermark:manage",
  "/ai": "ai:manage",
  "/queue": "monitoring:view",
  "/users": "user:view",
  "/logs": "logs:view",
  "/settings": "settings:manage",
};

const THEMES = [
  { value: "dark", label: "Тёмная тема", icon: Moon },
  { value: "light", label: "Светлая тема", icon: Sun },
  { value: "dim", label: "Светлая + меню", icon: SunMoon },
] as const;

export function Sidebar({
  onCollapse,
  iconOnly = false,
}: {
  onCollapse?: () => void;
  iconOnly?: boolean;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { setTheme, theme } = useTheme();

  const [previewRole, setRole] = useState<string | null>(null);
  useEffect(() => {
    const sync = () => setRole(getPreviewRole());
    sync();
    window.addEventListener("snews:preview-role", sync);
    return () => window.removeEventListener("snews:preview-role", sync);
  }, []);

  const { data: catalog } = useSWR<{ roles: Record<string, string[]> }>(
    "/users/permissions",
    fetcher
  );
  const { data: me } = useSWR<{ email: string; full_name?: string; role: string }>(
    "/auth/me",
    fetcher,
    { revalidateOnFocus: false }
  );
  const labels = useRoleLabels();
  const allowed = previewRole ? catalog?.roles?.[previewRole] : undefined;
  const visible = (href: string) => {
    const need = ITEM_PERMISSION[href];
    if (!previewRole || !need || !allowed) return true;
    return allowed.includes(need);
  };

  const logout = () => {
    clearTokens();
    router.push("/login");
  };

  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const current = mounted ? THEMES.findIndex((t) => t.value === theme) : -1;
  const next = THEMES[(current + 1) % THEMES.length];
  const NextIcon = next.icon;

  const cycleTheme = () => {
    const root = document.documentElement;
    root.classList.add("theme-anim");
    window.setTimeout(() => root.classList.remove("theme-anim"), 300);
    setTheme(next.value);
  };

  const initials = (me?.full_name || me?.email || "?").slice(0, 2).toUpperCase();

  // Icon-only: compact strip showing only icons with tooltips.
  if (iconOnly) {
    return (
      <aside className="flex h-full min-h-screen w-16 shrink-0 flex-col items-center bg-sidebar text-sidebar-foreground">
        {/* Logo / expand button */}
        <div className="flex h-16 w-full items-center justify-center border-b border-sidebar-border">
          {onCollapse ? (
            <button
              onClick={onCollapse}
              className="rounded-md p-2 text-sidebar-foreground transition-colors hover:bg-sidebar-hover hover:text-sidebar-strong"
              title="Развернуть меню"
              aria-label="Развернуть меню"
            >
              <PanelLeftOpen className="h-5 w-5" />
            </button>
          ) : (
            <ImageIcon className="h-6 w-6 text-sky-400" />
          )}
        </div>

        {/* Nav icons */}
        <nav className="flex flex-1 flex-col items-center gap-1 overflow-y-auto py-3">
          {SECTIONS.flatMap((s) => s.items).filter((i) => visible(i.href)).map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(href + "/");
            return (
              <Link
                key={href}
                href={href}
                title={label}
                aria-label={label}
                className={cn(
                  "flex h-10 w-10 items-center justify-center rounded-md transition-colors",
                  active
                    ? "bg-sky-600 text-white"
                    : "hover:bg-sidebar-hover hover:text-sidebar-strong"
                )}
              >
                <Icon className="h-5 w-5" />
              </Link>
            );
          })}
        </nav>

        {/* Bottom icons */}
        <div className="flex flex-col items-center gap-1 border-t border-sidebar-border py-3">
          <Link
            href="/profile"
            title="Личный кабинет"
            aria-label="Личный кабинет"
            className={cn(
              "flex h-10 w-10 items-center justify-center rounded-md transition-colors",
              pathname === "/profile"
                ? "bg-sky-600 text-white"
                : "hover:bg-sidebar-hover hover:text-sidebar-strong"
            )}
          >
            <UserCircle className="h-5 w-5" />
          </Link>
          <button
            onClick={cycleTheme}
            title={next.label}
            aria-label={next.label}
            className="flex h-10 w-10 items-center justify-center rounded-md transition-colors hover:bg-sidebar-hover hover:text-sidebar-strong"
          >
            <NextIcon className="h-5 w-5" />
          </button>
          <button
            onClick={logout}
            title="Выйти"
            aria-label="Выйти"
            className="flex h-10 w-10 items-center justify-center rounded-md transition-colors hover:bg-sidebar-hover hover:text-sidebar-strong"
          >
            <LogOut className="h-5 w-5" />
          </button>
        </div>
      </aside>
    );
  }

  // Full sidebar.
  return (
    <aside className="flex h-full min-h-screen w-60 shrink-0 flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex h-16 items-center gap-2 border-b border-sidebar-border px-5 text-sidebar-strong">
        <ImageIcon className="h-6 w-6 text-sky-400" />
        <span className="text-lg font-semibold tracking-wide">SNEWS</span>
        {onCollapse && (
          <button
            onClick={onCollapse}
            className="ml-auto rounded-md p-1.5 text-sidebar-foreground transition-colors hover:bg-sidebar-hover hover:text-sidebar-strong"
            title="Скрыть меню"
            aria-label="Скрыть меню"
          >
            <PanelLeftClose className="h-4 w-4" />
          </button>
        )}
      </div>
      <nav className="flex-1 space-y-4 overflow-y-auto p-3">
        {previewRole && (
          <button
            type="button"
            onClick={() => setPreviewRole(null)}
            className="w-full rounded-lg bg-amber-500/15 px-3 py-2 text-left text-[11px] leading-tight text-amber-200 ring-1 ring-amber-500/30"
          >
            Просмотр от лица: <b>{labels[previewRole] ?? previewRole}</b>
            <span className="mt-0.5 block opacity-70">Нажмите, чтобы выйти</span>
          </button>
        )}
        {SECTIONS.map((section) => {
          const items = section.items.filter((i) => visible(i.href));
          if (items.length === 0) return null;
          return (
            <div key={section.title}>
              <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-sidebar-title">
                {section.title}
              </div>
              <div className="space-y-1">
                {items.map(({ href, label, icon: Icon }) => {
                  const active = pathname === href || pathname.startsWith(href + "/");
                  return (
                    <Link
                      key={href}
                      href={href}
                      className={cn(
                        "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                        active
                          ? "bg-sky-600 text-white"
                          : "hover:bg-sidebar-hover hover:text-sidebar-strong"
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      {label}
                    </Link>
                  );
                })}
              </div>
            </div>
          );
        })}
      </nav>
      <div className="space-y-2 border-t border-sidebar-border p-3">
        <Link
          href="/profile"
          className={cn(
            "flex items-center gap-3 rounded-md px-3 py-2 transition-colors",
            pathname === "/profile"
              ? "bg-sky-600 text-white"
              : "hover:bg-sidebar-hover hover:text-sidebar-strong"
          )}
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sky-600/20 text-xs font-semibold text-sky-300">
            {initials}
          </span>
          <span className="min-w-0 flex-1 leading-tight">
            <span className="block truncate text-sm font-medium">
              {me?.full_name || me?.email || "Личный кабинет"}
            </span>
            <span className="block truncate text-[11px] opacity-70">
              {me ? labels[me.role] ?? me.role : "Профиль и уведомления"}
            </span>
          </span>
          <UserCircle className="h-4 w-4 shrink-0 opacity-70" />
        </Link>
        <button
          onClick={cycleTheme}
          className="flex w-full items-center justify-start gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-sidebar-hover hover:text-sidebar-strong"
        >
          <NextIcon className="h-4 w-4" />
          <span>{next.label}</span>
        </button>
        <button
          onClick={logout}
          className="flex w-full items-center justify-start gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-sidebar-hover hover:text-sidebar-strong"
        >
          <LogOut className="h-4 w-4" /> Выйти
        </button>
      </div>
    </aside>
  );
}

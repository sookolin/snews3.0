"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Newspaper, Radio, Building2, Send, FileText,
  Droplets, Image as ImageIcon, Bot, ListChecks, Users, ScrollText,
  Settings, Megaphone, PlusCircle,
  PanelLeftClose, PanelLeftOpen,
} from "lucide-react";
import { useEffect, useState } from "react";
import useSWR from "swr";
import { cn } from "@/lib/utils";
import { fetcher } from "@/lib/api";
import { getPreviewRole, setPreviewRole, useRoleLabels } from "@/lib/roles";
import { ROUTE_PERMISSION, useMyPermissions } from "@/lib/permissions";

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

const ITEM_PERMISSION = ROUTE_PERMISSION;

export function Sidebar({
  onCollapse,
  iconOnly = false,
}: {
  onCollapse?: () => void;
  iconOnly?: boolean;
}) {
  const pathname = usePathname();

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
  const { data: me } = useSWR<{ email: string; full_name?: string; role: string; photo_url?: string | null }>(
    "/auth/me",
    fetcher,
    { revalidateOnFocus: false }
  );
  const labels = useRoleLabels();
  const { permissions: myPermissions } = useMyPermissions();
  const allowed = previewRole ? catalog?.roles?.[previewRole] : undefined;
  const visible = (href: string) => {
    const need = ITEM_PERMISSION[href];
    if (!need) return true;
    // Previewing another role: simulate that role's tab visibility.
    if (previewRole) return !!allowed?.includes(need);
    // Real (non-preview) session: gate by the actual logged-in user's
    // effective permissions, not just the role simulation — a tab the user
    // has no access to must never be reachable at all, not even by URL.
    if (!myPermissions) return false; // still loading — don't flash it open
    return myPermissions.has(need);
  };

  // Icon-only: compact strip showing only icons with tooltips.
  if (iconOnly) {
    return (
      <aside className="flex h-full min-h-screen w-16 shrink-0 flex-col items-center bg-sidebar text-sidebar-foreground">
        {/* Logo / expand button */}
        <div className="flex h-14 w-full items-center justify-center border-b border-sidebar-border">
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

        </aside>
    );
  }

  // Full sidebar.
  return (
    <aside className="flex h-full min-h-screen w-60 shrink-0 flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex h-14 items-center gap-2 border-b border-sidebar-border px-5 text-sidebar-strong">
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

      {/* Current user strip at the bottom */}
      {me && (
        <Link
          href="/profile"
          className="flex items-center gap-2.5 border-t border-sidebar-border px-4 py-3 text-sm hover:bg-sidebar-hover"
          title="Личный кабинет"
        >
          {me.photo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={me.photo_url}
              alt={me.full_name || me.email}
              className="h-7 w-7 shrink-0 rounded-full object-cover"
              width={28}
              height={28}
            />
          ) : (
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-sky-600/20 text-xs font-semibold text-sky-600 dark:text-sky-300">
              {(me.full_name || me.email || "?").slice(0, 2).toUpperCase()}
            </span>
          )}
          <div className="min-w-0">
            <div className="truncate font-medium text-sidebar-strong">
              {me.full_name || me.email}
            </div>
            <div className="truncate text-[11px] text-sidebar-foreground/60">
              {labels[me.role] ?? me.role}
            </div>
          </div>
        </Link>
      )}
      </aside>
  );
}

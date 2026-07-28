"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard, Newspaper, Radio, Building2, Send, FileText,
  Droplets, Image as ImageIcon, Bot, ListChecks, Users, ScrollText,
  Settings, LogOut, Sun, Moon, Megaphone, PlusCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { clearTokens } from "@/lib/api";
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

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { setTheme, resolvedTheme } = useTheme();

  const logout = () => {
    clearTokens();
    router.push("/login");
  };

  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const isDark = mounted && resolvedTheme === "dark";

  return (
    <aside className="flex h-full min-h-screen w-60 shrink-0 flex-col bg-sidebar text-slate-300">
      <div className="flex h-16 items-center gap-2 border-b border-white/10 px-5 text-white">
        <ImageIcon className="h-6 w-6 text-sky-400" />
        <span className="text-lg font-semibold tracking-wide">SNEWS</span>
      </div>
      <nav className="flex-1 space-y-4 overflow-y-auto p-3">
        {SECTIONS.map((section) => (
          <div key={section.title}>
            <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              {section.title}
            </div>
            <div className="space-y-1">
              {section.items.map(({ href, label, icon: Icon }) => {
                const active = pathname === href || pathname.startsWith(href + "/");
                return (
                  <Link
                    key={href}
                    href={href}
                    className={cn(
                      "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                      active
                        ? "bg-sky-600 text-white"
                        : "text-slate-300 hover:bg-white/10 hover:text-white"
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {label}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
      <div className="space-y-2 border-t border-white/10 p-3">
        <button
          onClick={() => {
            // Enable colour transitions only for the duration of the switch.
            const root = document.documentElement;
            root.classList.add("theme-anim");
            window.setTimeout(() => root.classList.remove("theme-anim"), 300);
            setTheme(isDark ? "light" : "dark");
          }}
          className="flex w-full items-center justify-start gap-2 rounded-md px-3 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 hover:text-white"
        >
          {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          <span>{isDark ? "Светлая тема" : "Тёмная тема"}</span>
        </button>
        <button
          onClick={logout}
          className="flex w-full items-center justify-start gap-2 rounded-md px-3 py-2 text-sm font-medium text-slate-300 hover:bg-white/10 hover:text-white"
        >
          <LogOut className="h-4 w-4" /> Выйти
        </button>
      </div>
    </aside>
  );
}

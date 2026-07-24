"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard, Newspaper, Radio, Building2, Send, FileText,
  Droplets, Image as ImageIcon, Bot, ListChecks, Users, ScrollText,
  Settings, LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { clearTokens } from "@/lib/api";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/news", label: "Новости", icon: Newspaper },
  { href: "/sources", label: "Источники", icon: Radio },
  { href: "/cities", label: "Города", icon: Building2 },
  { href: "/channels", label: "Telegram", icon: Send },
  { href: "/templates", label: "Шаблоны", icon: FileText },
  { href: "/watermarks", label: "Водяной знак", icon: Droplets },
  { href: "/ai", label: "AI", icon: Bot },
  { href: "/queue", label: "Очередь", icon: ListChecks },
  { href: "/users", label: "Пользователи", icon: Users },
  { href: "/logs", label: "Логи", icon: ScrollText },
  { href: "/settings", label: "Настройки", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  const logout = () => {
    clearTokens();
    router.push("/login");
  };

  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-card">
      <div className="flex h-16 items-center gap-2 border-b border-border px-5">
        <ImageIcon className="h-6 w-6 text-primary" />
        <span className="text-lg font-semibold">CityNews</span>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium",
                active ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <button onClick={logout} className="btn-outline m-3">
        <LogOut className="h-4 w-4" /> Выйти
      </button>
    </aside>
  );
}

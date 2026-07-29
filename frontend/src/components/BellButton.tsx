"use client";

import { useRef, useState } from "react";
import { Bell, Check, X } from "lucide-react";
import useSWR, { mutate as globalMutate } from "swr";
import { api, fetcher } from "@/lib/api";
import { useRouter } from "next/navigation";

interface AppNotification {
  id: number;
  type: string;
  title: string;
  body?: string;
  url?: string;
  is_read: boolean;
  created_at: string;
}

const POLL_MS = 30_000;

export function BellButton() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { data, mutate } = useSWR<AppNotification[]>("/notifications?limit=50", fetcher, {
    refreshInterval: POLL_MS,
    revalidateOnFocus: true,
  });

  const items = data ?? [];
  const unread = items.filter((n) => !n.is_read).length;

  const markRead = async (id: number) => {
    await api(`/notifications/${id}/read`, { method: "POST" });
    mutate();
  };

  const markAllRead = async () => {
    await api("/notifications/read-all", { method: "POST" });
    mutate();
  };

  const handleClick = async (n: AppNotification) => {
    if (!n.is_read) await markRead(n.id);
    setOpen(false);
    if (n.url) router.push(n.url);
  };

  return (
    <div ref={ref} className="relative">
      <button
        className="btn-icon relative"
        title="Уведомления"
        onClick={() => setOpen((v) => !v)}
        aria-label="Уведомления"
      >
        <Bell className="h-4 w-4" />
        {unread > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[10px] font-bold text-white leading-none">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
          />
          {/* Dropdown */}
          <div className="absolute right-0 top-full z-50 mt-1.5 w-80 origin-top-right animate-in">
            <div className="card overflow-hidden">
              <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
                <span className="text-sm font-semibold">Уведомления</span>
                <div className="flex gap-1">
                  {unread > 0 && (
                    <button
                      className="btn-icon h-6 w-6 text-xs"
                      title="Прочитать все"
                      onClick={markAllRead}
                    >
                      <Check className="h-3.5 w-3.5" />
                    </button>
                  )}
                  <button
                    className="btn-icon h-6 w-6"
                    onClick={() => setOpen(false)}
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>

              <div className="max-h-[400px] overflow-y-auto">
                {items.length === 0 && (
                  <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                    Уведомлений нет
                  </div>
                )}
                {items.map((n) => (
                  <button
                    key={n.id}
                    type="button"
                    className={`w-full border-b border-border/60 px-4 py-3 text-left transition-colors last:border-0
                                hover:bg-muted ${n.is_read ? "opacity-60" : ""}`}
                    onClick={() => handleClick(n)}
                  >
                    <div className="flex items-start gap-2">
                      {!n.is_read && (
                        <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary" />
                      )}
                      <div className={!n.is_read ? "" : "pl-4"}>
                        <div className="text-sm font-medium leading-snug">{n.title}</div>
                        {n.body && (
                          <div className="mt-0.5 text-xs text-muted-foreground line-clamp-2">
                            {n.body}
                          </div>
                        )}
                        <div className="mt-1 text-[11px] text-muted-foreground">
                          {new Date(n.created_at).toLocaleString("ru-RU")}
                        </div>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

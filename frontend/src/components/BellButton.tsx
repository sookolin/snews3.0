"use client";

import { useEffect, useRef, useState } from "react";
import { Bell, Check, X } from "lucide-react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import { useRouter } from "next/navigation";
import { useRoleLabels } from "@/lib/roles";

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

/** Play a short two-tone ping using Web Audio API — no asset required. */
function playPing() {
  try {
    const ctx = new (window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    const play = (freq: number, start: number, dur: number) => {
      const osc  = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = freq;
      osc.type = "sine";
      gain.gain.setValueAtTime(0.18, ctx.currentTime + start);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur);
      osc.start(ctx.currentTime + start);
      osc.stop(ctx.currentTime + start + dur);
    };
    play(880, 0,    0.12);
    play(1100, 0.13, 0.10);
  } catch {
    // Audio blocked or unsupported — silently skip.
  }
}

/**
 * Replace raw role keys in a notification body with their display labels.
 * The backend writes e.g. «super_admin» — we turn it into «Супер-админ».
 */
function translateRoles(text: string | undefined, labels: Record<string, string>): string {
  if (!text) return "";
  return Object.entries(labels).reduce(
    (s, [key, label]) => s.replaceAll(`«${key}»`, `«${label}»`),
    text
  );
}

export function BellButton() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref     = useRef<HTMLDivElement>(null);
  const prevUnread = useRef<number>(0);
  const labels  = useRoleLabels();

  const { data, mutate } = useSWR<AppNotification[]>("/notifications?limit=50", fetcher, {
    refreshInterval: POLL_MS,
    revalidateOnFocus: true,
  });

  // Heartbeat: ping presence every 60s while tab is active
  useEffect(() => {
    const ping = () => api("/profile/heartbeat", { method: "POST" }).catch(() => {});
    ping(); // initial
    const timer = setInterval(ping, 60_000);
    return () => clearInterval(timer);
  }, []);

  const items  = data ?? [];
  const unread = items.filter((n) => !n.is_read).length;

  // Play a sound when unread count increases (new notifications arrived).
  useEffect(() => {
    if (unread > prevUnread.current) playPing();
    prevUnread.current = unread;
  }, [unread]);

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
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
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
                  <button className="btn-icon h-6 w-6" onClick={() => setOpen(false)}>
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
                            {translateRoles(n.body, labels)}
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

"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";

interface SystemStatus {
  services: { name: string; healthy: boolean; detail?: string | null }[];
  cpu_percent: number;
  memory_percent: number;
  queue_depth: number;
  active_workers: number;
  running_tasks: number;
  pending_moderation: number;
  scheduled: number;
  approved_waiting: number;
  failed: number;
  published_today: number;
  workers: string[];
  resources_detail?: string | null;
}

/** Pipeline counters come straight from the database, so they stay correct
 *  even when Redis or Celery are unreachable. */
const PIPELINE: { key: keyof SystemStatus; label: string }[] = [
  { key: "pending_moderation", label: "На модерации" },
  { key: "approved_waiting", label: "Одобрено, ждёт публикации" },
  { key: "scheduled", label: "Отложено" },
  { key: "published_today", label: "Опубликовано сегодня" },
  { key: "failed", label: "Ошибки публикации" },
];

export default function QueuePage() {
  const { data, error } = useSWR<SystemStatus>("/dashboard/system", fetcher, {
    refreshInterval: 5000,
  });

  return (
    <div>
      <PageHeader title="Очередь и мониторинг" />
      {error && <p className="text-red-600">Ошибка загрузки статуса</p>}
      {data && (
        <>
          <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-5">
            <div className="card p-5">
              <div className="text-sm text-muted-foreground">Задач в очереди</div>
              <div className="mt-2 text-3xl font-semibold">{data.queue_depth}</div>
            </div>
            <div className="card p-5">
              <div className="text-sm text-muted-foreground">В работе у воркеров</div>
              <div className="mt-2 text-3xl font-semibold">{data.running_tasks}</div>
            </div>
            <div className="card p-5">
              <div className="text-sm text-muted-foreground">Активных воркеров</div>
              <div className="mt-2 text-3xl font-semibold">{data.active_workers}</div>
              {data.workers.length > 0 && (
                <div className="mt-1 truncate font-mono text-xs text-muted-foreground" title={data.workers.join(", ")}>
                  {data.workers.join(", ")}
                </div>
              )}
            </div>
            <div className="card p-5">
              <div className="text-sm text-muted-foreground">CPU</div>
              <div className="mt-2 text-3xl font-semibold">{data.cpu_percent.toFixed(0)}%</div>
            </div>
            <div className="card p-5">
              <div className="text-sm text-muted-foreground">Память</div>
              <div className="mt-2 text-3xl font-semibold">{data.memory_percent.toFixed(0)}%</div>
            </div>
          </div>

          {data.resources_detail && (
            <p className="mb-6 rounded-md bg-amber-50 p-3 text-sm text-amber-800">{data.resources_detail}</p>
          )}

          <div className="mb-6 card p-5">
            <h2 className="mb-4 text-lg font-medium">Конвейер новостей</h2>
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
              {PIPELINE.map((p) => (
                <div key={p.key} className="rounded-md border border-border p-3">
                  <div className="text-xs text-muted-foreground">{p.label}</div>
                  <div className="mt-1 text-2xl font-semibold">{data[p.key] as number}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="card p-5">
            <h2 className="mb-4 text-lg font-medium">Сервисы</h2>
            <div className="space-y-2">
              {data.services.map((s) => (
                <div key={s.name} className="flex items-start justify-between gap-3 rounded-md border border-border p-3">
                  <div className="min-w-0">
                    <span className="font-medium">{s.name}</span>
                    {s.detail && (
                      <p className="mt-1 break-words text-xs text-muted-foreground">{s.detail}</p>
                    )}
                  </div>
                  <span className={`badge shrink-0 ${s.healthy ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                    {s.healthy ? "работает" : "недоступен"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

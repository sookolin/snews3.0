"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";

interface SystemStatus {
  services: { name: string; healthy: boolean; detail?: string }[];
  cpu_percent: number;
  memory_percent: number;
  queue_depth: number;
  active_workers: number;
}

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
          <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
            <div className="card p-5">
              <div className="text-sm text-muted-foreground">Задач в очереди</div>
              <div className="mt-2 text-3xl font-semibold">{data.queue_depth}</div>
            </div>
            <div className="card p-5">
              <div className="text-sm text-muted-foreground">Активных воркеров</div>
              <div className="mt-2 text-3xl font-semibold">{data.active_workers}</div>
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

          <div className="card p-5">
            <h2 className="mb-4 text-lg font-medium">Сервисы</h2>
            <div className="space-y-2">
              {data.services.map((s) => (
                <div key={s.name} className="flex items-center justify-between rounded-md border border-border p-3">
                  <span className="font-medium">{s.name}</span>
                  <span className={`badge ${s.healthy ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
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

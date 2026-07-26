"use client";

import useSWR from "swr";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import { fetcher } from "@/lib/api";
import type { DashboardStats } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";

function StatCard({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <div className="card p-5">
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className={`mt-2 text-3xl font-semibold ${tone ?? ""}`}>{value}</div>
    </div>
  );
}

export default function DashboardPage() {
  const { data, error, isLoading } = useSWR<DashboardStats>("/dashboard/stats", fetcher, {
    refreshInterval: 15000,
  });

  if (isLoading) return <p className="text-muted-foreground">Загрузка…</p>;
  if (error) return <p className="text-red-600">Ошибка загрузки статистики</p>;
  if (!data) return null;

  return (
    <div>
      <PageHeader title="Dashboard" />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4 mb-6">
        <StatCard label="Всего новостей" value={data.total_news} />
        <StatCard label="Опубликовано" value={data.published} tone="text-green-600" />
        <StatCard label="На модерации" value={data.pending} tone="text-amber-600" />
        <StatCard label="Ошибки" value={data.failed} tone="text-red-600" />
        <StatCard label="Города" value={data.total_cities} />
        <StatCard label="Активные источники" value={data.active_sources} />
        <StatCard label="Всего источников" value={data.total_sources} />
        <StatCard label="Дубликаты" value={data.duplicates} />
        <StatCard label="Всего каналов" value={data.total_channels} />
        <StatCard label="Активные каналы" value={data.active_channels} tone="text-blue-600" />
      </div>

      <div className="mb-6 card p-5">
        <h2 className="mb-4 text-lg font-medium">Статистика бота</h2>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <div className="text-sm text-muted-foreground">Предложено через бота</div>
            <div className="mt-1 text-2xl font-semibold">{data.bot_submissions}</div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">Уникальных пользователей</div>
            <div className="mt-1 text-2xl font-semibold">{data.bot_unique_users}</div>
          </div>
          <div>
            <div className="text-sm text-muted-foreground">Анонимных заявок</div>
            <div className="mt-1 text-2xl font-semibold">{data.bot_anonymous}</div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card p-5">
          <h2 className="mb-4 text-lg font-medium">Новости за 7 дней</h2>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.last_7_days}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" fontSize={12} />
                <YAxis allowDecimals={false} fontSize={12} />
                <Tooltip />
                <Bar dataKey="count" fill="hsl(222 47% 31%)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-5">
          <h2 className="mb-4 text-lg font-medium">Каналы по городам</h2>
          <div className="space-y-3 max-h-72 overflow-y-auto">
            {data.channels_by_city?.map((item: { city: string; count: number }) => (
              <div key={item.city} className="flex items-center justify-between">
                <span className="text-sm font-medium">{item.city}</span>
                <div className="flex items-center gap-2">
                  <div className="w-32 h-4 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full"
                      style={{ width: `${Math.min(item.count * 20, 100)}%` }}
                    />
                  </div>
                  <span className="text-sm text-muted-foreground w-10 text-right">{item.count}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

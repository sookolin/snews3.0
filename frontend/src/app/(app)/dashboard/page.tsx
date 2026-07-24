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
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Всего новостей" value={data.total_news} />
        <StatCard label="Опубликовано" value={data.published} tone="text-green-600" />
        <StatCard label="На модерации" value={data.pending} tone="text-amber-600" />
        <StatCard label="Ошибки" value={data.failed} tone="text-red-600" />
        <StatCard label="Города" value={data.total_cities} />
        <StatCard label="Активные источники" value={data.active_sources} />
        <StatCard label="Всего источников" value={data.total_sources} />
        <StatCard label="Дубликаты" value={data.duplicates} />
      </div>

      <div className="mt-6 card p-5">
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
    </div>
  );
}

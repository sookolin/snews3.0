"use client";

import useSWR from "swr";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  AreaChart, Area, PieChart, Pie, Cell, Legend,
} from "recharts";

const PIE_COLORS = ["#6366f1", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#94a3b8"];
import { fetcher } from "@/lib/api";
import type { DashboardStats } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { STATUS_LABELS } from "@/components/StatusBadge";

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
      <PageHeader title="Дашборд" />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4 mb-6">
        <StatCard label="Всего новостей" value={data.total_news} />
        <StatCard label="Опубликовано" value={data.published} tone="text-green-600" />
        <StatCard label="На модерации" value={data.pending} tone="text-amber-600" />
        <StatCard label="Ошибки" value={data.failed} tone="text-red-600" />
        <StatCard label="Города" value={data.total_cities} />
        <StatCard label="Активные источники" value={data.active_sources} />
        <StatCard label="Всего источников" value={data.total_sources} />
        <StatCard label="Отклонено" value={data.rejected} />
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
              <AreaChart data={data.last_7_days}>
                <defs>
                  <linearGradient id="gradNews" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.7} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" fontSize={12} />
                <YAxis allowDecimals={false} fontSize={12} />
                <Tooltip />
                <Area type="monotone" dataKey="count" stroke="#6366f1" strokeWidth={2} fill="url(#gradNews)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-5">
          <h2 className="mb-4 text-lg font-medium">Распределение по статусам</h2>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  // Statuses come from the API as raw keys; label them in Russian.
                  data={data.by_status.map((s) => ({
                    ...s,
                    status: STATUS_LABELS[s.status] ?? s.status,
                  }))}
                  dataKey="count"
                  nameKey="status"
                  innerRadius={55}
                  outerRadius={95}
                  paddingAngle={2}
                >
                  {data.by_status.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-5">
          <h2 className="mb-4 text-lg font-medium">Воронка обработки</h2>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                layout="vertical"
                data={[
                  { name: "Найдено", value: data.total_news },
                  { name: "На модерации", value: data.pending },
                  { name: "Опубликовано", value: data.published },
                  { name: "Отклонено", value: data.rejected },
                  { name: "Ошибки", value: data.failed },
                ]}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" allowDecimals={false} fontSize={12} />
                <YAxis type="category" dataKey="name" width={110} fontSize={12} />
                <Tooltip />
                <Bar dataKey="value" fill="#6366f1" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-5">
          <h2 className="mb-1 text-lg font-medium">Источники за 30 дней</h2>
          <p className="mb-4 text-sm text-muted-foreground">Сколько принесли и сколько дошло до канала</p>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart layout="vertical" data={data.top_sources} barGap={2}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" allowDecimals={false} fontSize={12} />
                <YAxis type="category" dataKey="name" width={130} fontSize={11} />
                <Tooltip />
                <Legend />
                <Bar dataKey="total" name="Найдено" fill="#94a3b8" radius={[0, 4, 4, 0]} />
                <Bar dataKey="published" name="Опубликовано" fill="#22c55e" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-5">
          <h2 className="mb-1 text-lg font-medium">Активность по часам</h2>
          <p className="mb-4 text-sm text-muted-foreground">
            Публикации за 30 дней. Среднее время до публикации: {data.avg_moderation_minutes} мин
          </p>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.by_hour}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="hour" fontSize={12} tickFormatter={(h: number) => `${h}:00`} />
                <YAxis allowDecimals={false} fontSize={12} />
                <Tooltip labelFormatter={(h) => `${h}:00`} />
                <Bar dataKey="count" name="Публикаций" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}

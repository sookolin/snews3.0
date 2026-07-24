"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { NewsItem, Page } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";

const STATUSES = ["", "pending", "approved", "published", "rejected", "failed", "duplicate"];

export default function NewsPage() {
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const query = new URLSearchParams();
  if (status) query.set("status", status);
  if (search) query.set("search", search);

  const { data, mutate, isLoading } = useSWR<Page<NewsItem>>(
    `/news?${query.toString()}`,
    fetcher
  );

  const act = async (id: number, action: "approve" | "reject") => {
    await api(`/news/${id}/${action}`, { method: "POST" });
    mutate();
  };

  return (
    <div>
      <PageHeader title="Новости" />
      <div className="mb-4 flex flex-wrap gap-3">
        <select className="input max-w-[200px]" value={status} onChange={(e) => setStatus(e.target.value)}>
          {STATUSES.map((s) => (
            <option key={s} value={s}>{s || "Все статусы"}</option>
          ))}
        </select>
        <input
          className="input max-w-xs"
          placeholder="Поиск…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-muted-foreground">
            <tr>
              <th className="px-4 py-3">ID</th>
              <th className="px-4 py-3">Заголовок</th>
              <th className="px-4 py-3">Статус</th>
              <th className="px-4 py-3">Совпадение</th>
              <th className="px-4 py-3">Создано</th>
              <th className="px-4 py-3 text-right">Действия</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">Загрузка…</td></tr>
            )}
            {data?.items.map((n) => (
              <tr key={n.id} className="border-t border-border">
                <td className="px-4 py-3 text-muted-foreground">{n.id}</td>
                <td className="px-4 py-3 font-medium">{n.title || n.original_title || "—"}</td>
                <td className="px-4 py-3"><StatusBadge status={n.status} /></td>
                <td className="px-4 py-3">{n.match_score != null ? `${Math.round(n.match_score * 100)}%` : "—"}</td>
                <td className="px-4 py-3 text-muted-foreground">
                  {new Date(n.created_at).toLocaleString("ru-RU")}
                </td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    {n.status === "pending" && (
                      <>
                        <button className="btn-primary py-1" onClick={() => act(n.id, "approve")}>Одобрить</button>
                        <button className="btn-danger py-1" onClick={() => act(n.id, "reject")}>Отклонить</button>
                      </>
                    )}
                    <a className="btn-outline py-1" href={`/news/${n.id}`}>Открыть</a>
                  </div>
                </td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">Нет новостей</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {data && <p className="mt-3 text-sm text-muted-foreground">Всего: {data.total}</p>}
    </div>
  );
}

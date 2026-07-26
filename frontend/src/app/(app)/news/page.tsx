"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { City, NewsItem, Page } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge, STATUS_LABELS } from "@/components/StatusBadge";

const STATUSES = ["", "new", "pending", "approved", "published", "rejected", "failed", "duplicate"];

export default function NewsPage() {
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const query = new URLSearchParams();
  if (status) query.set("status", status);
  if (search) query.set("search", search);
  query.set("size", "100");

  const { data, mutate, isLoading } = useSWR<Page<NewsItem>>(
    `/news?${query.toString()}`,
    fetcher
  );
  const { data: cities } = useSWR<Page<City>>("/cities?size=200", fetcher);
  const cityName = (id?: number) =>
    id ? cities?.items.find((c) => c.id === id)?.name ?? `#${id}` : "—";

  const act = async (id: number, action: "approve" | "reject") => {
    await api(`/news/${id}/${action}`, { method: "POST" });
    mutate();
  };

  const remove = async (id: number) => {
    if (!confirm("Удалить новость безвозвратно?")) return;
    await api(`/news/${id}`, { method: "DELETE" });
    mutate();
  };

  const sendToModeration = async (id: number) => {
    try {
      await api(`/news/${id}/send-to-moderation`, { method: "POST" });
      alert("Карточка отправлена в топик модерации Telegram");
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const author = (n: NewsItem) => {
    if (n.origin === "user") {
      return n.submitted_anonymously ? "Аноним" : (n.author_name || "Пользователь");
    }
    return "—";
  };

  return (
    <div>
      <PageHeader title="Новости" />
      <div className="mb-4 flex flex-wrap gap-3">
        <select className="input max-w-[220px]" value={status} onChange={(e) => setStatus(e.target.value)}>
          {STATUSES.map((s) => (
            <option key={s} value={s}>{s ? STATUS_LABELS[s] ?? s : "Все статусы"}</option>
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
              <th className="px-4 py-3">Город / канал</th>
              <th className="px-4 py-3">Автор</th>
              <th className="px-4 py-3">Статус</th>
              <th className="px-4 py-3">Создано</th>
              <th className="px-4 py-3 text-right">Действия</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-muted-foreground">Загрузка…</td></tr>
            )}
            {data?.items.map((n) => (
              <tr key={n.id} className="border-t border-border">
                <td className="px-4 py-3 text-muted-foreground">{n.id}</td>
                <td className="px-4 py-3 font-medium">{n.title || n.original_title || "—"}</td>
                <td className="px-4 py-3">
                  <span className="badge bg-sky-100 text-sky-700 dark:bg-sky-900/50 dark:text-sky-300">
                    {cityName(n.city_id)}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted-foreground">{author(n)}</td>
                <td className="px-4 py-3"><StatusBadge status={n.status} /></td>
                <td className="px-4 py-3 text-muted-foreground">
                  {new Date(n.created_at).toLocaleString("ru-RU")}
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap justify-end gap-2">
                    {n.status === "pending" && (
                      <>
                        <button className="btn-primary py-1" onClick={() => act(n.id, "approve")}>Одобрить</button>
                        <button className="btn-danger py-1" onClick={() => act(n.id, "reject")}>Отклонить</button>
                      </>
                    )}
                    {n.city_id && (
                      <button className="btn-outline py-1" onClick={() => sendToModeration(n.id)} title="Отправить карточку в топик Telegram">
                        В топик
                      </button>
                    )}
                    <a className="btn-outline py-1" href={`/news/${n.id}`}>Открыть</a>
                    <button className="btn-danger py-1" onClick={() => remove(n.id)}>Удалить</button>
                  </div>
                </td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-6 text-center text-muted-foreground">Нет новостей</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {data && <p className="mt-3 text-sm text-muted-foreground">Всего: {data.total}</p>}
    </div>
  );
}

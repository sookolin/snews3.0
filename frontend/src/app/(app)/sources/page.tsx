"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { Page, Source } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";

const TYPES = ["rss", "telegram", "website", "html", "api"];

export default function SourcesPage() {
  const { data, mutate } = useSWR<Page<Source>>("/sources?size=100", fetcher);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", url: "", type: "rss", check_interval_seconds: 300 });
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api("/sources", { method: "POST", body: JSON.stringify(form) });
      setForm({ name: "", url: "", type: "rss", check_interval_seconds: 300 });
      setOpen(false);
      mutate();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const check = async (id: number) => {
    await api(`/sources/${id}/check`, { method: "POST" });
    alert("Проверка источника поставлена в очередь");
  };

  const remove = async (id: number) => {
    if (!confirm("Удалить источник?")) return;
    await api(`/sources/${id}`, { method: "DELETE" });
    mutate();
  };

  return (
    <div>
      <PageHeader
        title="Источники"
        action={<button className="btn-primary" onClick={() => setOpen(!open)}>Добавить источник</button>}
      />

      {open && (
        <div className="card mb-5 space-y-3 p-5">
          {error && <p className="text-sm text-red-600">{error}</p>}
          <input className="input" placeholder="Название" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input className="input" placeholder="URL" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} />
          <div className="flex gap-3">
            <select className="input max-w-[160px]" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
              {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <input
              type="number"
              className="input max-w-[200px]"
              placeholder="Интервал, сек"
              value={form.check_interval_seconds}
              onChange={(e) => setForm({ ...form, check_interval_seconds: Number(e.target.value) })}
            />
          </div>
          <button className="btn-primary" onClick={create}>Создать</button>
        </div>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-muted-foreground">
            <tr>
              <th className="px-4 py-3">Название</th>
              <th className="px-4 py-3">Тип</th>
              <th className="px-4 py-3">Интервал</th>
              <th className="px-4 py-3">Ошибки</th>
              <th className="px-4 py-3 text-right">Действия</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((s) => (
              <tr key={s.id} className="border-t border-border">
                <td className="px-4 py-3">
                  <div className="font-medium">{s.name}</div>
                  <div className="max-w-xs truncate text-xs text-muted-foreground">{s.url}</div>
                </td>
                <td className="px-4 py-3">{s.type}</td>
                <td className="px-4 py-3">{s.check_interval_seconds}s</td>
                <td className="px-4 py-3">{s.error_count > 0 ? <span className="text-red-600">{s.error_count}</span> : "0"}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    <button className="btn-outline py-1" onClick={() => check(s.id)}>Проверить</button>
                    <button className="btn-danger py-1" onClick={() => remove(s.id)}>Удалить</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

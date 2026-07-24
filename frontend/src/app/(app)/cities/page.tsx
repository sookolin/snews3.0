"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { City, Page } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";

export default function CitiesPage() {
  const { data, mutate } = useSWR<Page<City>>("/cities?size=100", fetcher);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", keywords: "", exclude_keywords: "", language: "ru" });
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api("/cities", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          keywords: form.keywords.split(",").map((s) => s.trim()).filter(Boolean),
          exclude_keywords: form.exclude_keywords.split(",").map((s) => s.trim()).filter(Boolean),
          language: form.language,
        }),
      });
      setForm({ name: "", keywords: "", exclude_keywords: "", language: "ru" });
      setOpen(false);
      mutate();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const remove = async (id: number) => {
    if (!confirm("Удалить город?")) return;
    await api(`/cities/${id}`, { method: "DELETE" });
    mutate();
  };

  return (
    <div>
      <PageHeader
        title="Города"
        action={<button className="btn-primary" onClick={() => setOpen(!open)}>Добавить город</button>}
      />

      {open && (
        <div className="card mb-5 space-y-3 p-5">
          {error && <p className="text-sm text-red-600">{error}</p>}
          <input className="input" placeholder="Название" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input className="input" placeholder="Ключевые слова (через запятую)" value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} />
          <input className="input" placeholder="Исключающие слова (через запятую)" value={form.exclude_keywords} onChange={(e) => setForm({ ...form, exclude_keywords: e.target.value })} />
          <select className="input max-w-[160px]" value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })}>
            <option value="ru">ru</option>
            <option value="en">en</option>
          </select>
          <button className="btn-primary" onClick={create}>Создать</button>
        </div>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-muted-foreground">
            <tr>
              <th className="px-4 py-3">Название</th>
              <th className="px-4 py-3">Ключевые слова</th>
              <th className="px-4 py-3">Topic</th>
              <th className="px-4 py-3">Активен</th>
              <th className="px-4 py-3 text-right">Действия</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((c) => (
              <tr key={c.id} className="border-t border-border">
                <td className="px-4 py-3 font-medium">{c.name}</td>
                <td className="px-4 py-3 text-muted-foreground">{c.keywords.join(", ") || "—"}</td>
                <td className="px-4 py-3">{c.telegram_topic_id ?? "—"}</td>
                <td className="px-4 py-3">{c.is_active ? "Да" : "Нет"}</td>
                <td className="px-4 py-3 text-right">
                  <button className="btn-danger py-1" onClick={() => remove(c.id)}>Удалить</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

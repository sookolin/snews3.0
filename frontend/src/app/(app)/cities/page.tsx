"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { City, Page } from "@/lib/types";
import { Copy, Pencil, PlugZap, RefreshCw, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Modal, Field } from "@/components/Modal";

interface CityForm {
  id?: number;
  name: string;
  description?: string;
  keywords: string;
  extra_keywords: string;
  exclude_keywords: string;
  region?: string;
  country?: string;
  language: string;
  is_active: boolean;
  telegram_topic_id?: number | null;
}

const EMPTY: CityForm = {
  name: "", description: "", keywords: "", extra_keywords: "", exclude_keywords: "",
  region: "", country: "", language: "ru", is_active: true, telegram_topic_id: null,
};

const toArr = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);
const fromArr = (a?: string[]) => (a ?? []).join(", ");

export default function CitiesPage() {
  const { data, mutate } = useSWR<Page<City>>("/cities?size=100", fetcher);
  const { data: settings } = useSWR<Record<string, unknown>>("/settings", fetcher);
  const botUsername = String(settings?.["bot.username"] ?? "").replace(/^@/, "");
  const [form, setForm] = useState<CityForm | null>(null);
  const [error, setError] = useState<string | null>(null);

  const openNew = () => { setForm({ ...EMPTY }); setError(null); };
  const openEdit = (c: City) => {
    setForm({
      id: c.id, name: c.name, description: c.description ?? "",
      keywords: fromArr(c.keywords), extra_keywords: fromArr(c.extra_keywords),
      exclude_keywords: fromArr(c.exclude_keywords), region: c.region ?? "",
      country: c.country ?? "", language: c.language, is_active: c.is_active,
      telegram_topic_id: c.telegram_topic_id,
    });
    setError(null);
  };
  const upd = (patch: Partial<CityForm>) => setForm((f) => (f ? { ...f, ...patch } : f));

  const save = async () => {
    if (!form) return;
    setError(null);
    const body = {
      name: form.name,
      description: form.description || null,
      keywords: toArr(form.keywords),
      extra_keywords: toArr(form.extra_keywords),
      exclude_keywords: toArr(form.exclude_keywords),
      region: form.region || null,
      country: form.country || null,
      language: form.language,
      is_active: form.is_active,
      telegram_topic_id: form.telegram_topic_id ?? null,
    };
    try {
      if (form.id) await api(`/cities/${form.id}`, { method: "PATCH", body: JSON.stringify(body) });
      else await api("/cities", { method: "POST", body: JSON.stringify(body) });
      setForm(null);
      mutate();
    } catch (e) { setError((e as Error).message); }
  };

  const remove = async (id: number) => {
    if (!confirm("Удалить город?")) return;
    await api(`/cities/${id}`, { method: "DELETE" });
    mutate();
  };

  const recreateTopic = async (id: number) => {
    try { await api(`/cities/${id}/create-topic`, { method: "POST" }); mutate(); }
    catch (e) { alert((e as Error).message); }
  };

  const testTopic = async (id: number) => {
    try {
      const r = await api<{ detail: string }>(`/cities/${id}/test-topic`, { method: "POST" });
      alert("Топик привязан: " + r.detail);
    } catch (e) {
      alert("Ошибка: " + (e as Error).message);
    }
  };

  return (
    <div>
      <PageHeader title="Города" action={<button className="btn-primary" onClick={openNew}>Добавить город</button>} />

      <div className="card overflow-hidden">
        <div className="table-wrap">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-muted-foreground">
            <tr>
              <th className="px-4 py-3">Название</th>
              <th className="px-4 py-3">Ключевые слова</th>
              <th className="px-4 py-3">Topic ID</th>
              <th className="px-4 py-3">Ссылка для предложки</th>
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
                <td className="px-4 py-3">
                  {botUsername ? (
                    <div className="flex items-center gap-2">
                      <a
                        className="text-xs text-primary underline"
                        href={`https://t.me/${botUsername}?start=suggest_${c.id}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Предложить новость
                      </a>
                      <button
                        className="btn-icon h-6 w-6"
                        title="Скопировать ссылку"
                        onClick={() => {
                          navigator.clipboard.writeText(
                            `https://t.me/${botUsername}?start=suggest_${c.id}`
                          );
                          alert("Ссылка скопирована");
                        }}
                      >
                        <Copy className="h-3 w-3" />
                      </button>
                    </div>
                  ) : (
                    <span className="text-xs text-muted-foreground">задайте bot.username в настройках</span>
                  )}
                </td>
                <td className="px-4 py-3">{c.is_active ? "Да" : "Нет"}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    <button className="btn-icon" title="Изменить" onClick={() => openEdit(c)}>
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button className="btn-icon" title="Пересоздать топик" onClick={() => recreateTopic(c.id)}>
                      <RefreshCw className="h-4 w-4" />
                    </button>
                    <button className="btn-icon-primary" title="Проверить привязку топика" onClick={() => testTopic(c.id)}>
                      <PlugZap className="h-4 w-4" />
                    </button>
                    <button className="btn-icon-danger" title="Удалить" onClick={() => remove(c.id)}>
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "Редактировать город" : "Новый город"} wide>
        {form && (
          <div className="space-y-4">
            {error && <p className="rounded-md bg-red-50 p-2 text-sm text-red-600 dark:bg-red-950/40">{error}</p>}
            <Field label="Название" hint="Название города — используется в шаблоне {city} и как ключевое слово">
              <input className="input" value={form.name} onChange={(e) => upd({ name: e.target.value })} />
            </Field>
            <Field label="Описание" hint="Необязательно, для внутренних заметок">
              <textarea className="input" value={form.description} onChange={(e) => upd({ description: e.target.value })} />
            </Field>
            <Field label="Ключевые слова" hint="Через запятую. Новость относится к городу, если содержит эти слова (учёт морфологии)">
              <input className="input" value={form.keywords} onChange={(e) => upd({ keywords: e.target.value })} />
            </Field>
            <Field label="Доп. ключевые слова" hint="Через запятую. Слабые признаки (район, улицы) — повышают релевантность">
              <input className="input" value={form.extra_keywords} onChange={(e) => upd({ extra_keywords: e.target.value })} />
            </Field>
            <Field label="Исключающие слова" hint="Через запятую. Если встречаются — новость НЕ относится к городу (тёзки, спорт-клубы и т.п.)">
              <input className="input" value={form.exclude_keywords} onChange={(e) => upd({ exclude_keywords: e.target.value })} />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Регион" hint="Область/край (необязательно)"><input className="input" value={form.region} onChange={(e) => upd({ region: e.target.value })} /></Field>
              <Field label="Страна" hint="Необязательно"><input className="input" value={form.country} onChange={(e) => upd({ country: e.target.value })} /></Field>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Язык" hint="Язык публикаций и AI-обработки">
                <select className="input" value={form.language} onChange={(e) => upd({ language: e.target.value })}>
                  <option value="ru">ru</option>
                  <option value="en">en</option>
                </select>
              </Field>
              <Field label="Topic ID" hint="ID ветки в группе модерации Telegram. Создаётся автоматически, но можно задать вручную.">
                <input className="input" type="number" value={form.telegram_topic_id ?? ""} onChange={(e) => upd({ telegram_topic_id: e.target.value ? Number(e.target.value) : null })} />
              </Field>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.is_active} onChange={(e) => upd({ is_active: e.target.checked })} /> Активен (собирать новости)
            </label>
            <div className="flex justify-end border-t border-border pt-4">
              <button className="btn-primary" onClick={save}>Сохранить</button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

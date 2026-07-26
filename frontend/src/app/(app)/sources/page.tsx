"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { Page, Source } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Modal, Field } from "@/components/Modal";

const TYPES = ["rss", "telegram", "website", "html", "api"];
const ENGINES = ["auto", "beautifulsoup", "lxml", "playwright"];

export default function SourcesPage() {
  const { data, mutate } = useSWR<Page<Source>>("/sources?size=100", fetcher);
  const [form, setForm] = useState<Partial<Source> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const openNew = () => setForm({ name: "", url: "", type: "rss", parser_engine: "auto", check_interval_seconds: 300, is_active: true });
  const openEdit = (s: Source) => setForm({ ...s });
  const upd = (patch: Partial<Source>) => setForm((f) => ({ ...f!, ...patch }));

  const save = async () => {
    if (!form) return;
    setError(null);
    try {
      if (form.id) await api(`/sources/${form.id}`, { method: "PATCH", body: JSON.stringify(form) });
      else await api("/sources", { method: "POST", body: JSON.stringify(form) });
      setForm(null);
      mutate();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const remove = async (id: number) => {
    if (!confirm("Удалить источник?")) return;
    await api(`/sources/${id}`, { method: "DELETE" });
    mutate();
  };

  const check = async (id: number) => {
    await api(`/sources/${id}/check`, { method: "POST" });
    alert("Проверка источника поставлена в очередь");
  };

  return (
    <div>
      <PageHeader
        title="Источники"
        action={<button className="btn-primary" onClick={openNew}>Добавить источник</button>}
      />

      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "Редактировать источник" : "Новый источник"} wide>
        {form && (
          <div className="space-y-4">
            {error && <p className="rounded-md bg-red-50 p-2 text-sm text-red-600">{error}</p>}
            <div className="grid grid-cols-2 gap-4">
              <Field label="Название"><input className="input" value={form.name ?? ""} onChange={(e) => upd({ name: e.target.value })} /></Field>
              <Field label="Тип">
                <select className="input" value={form.type} onChange={(e) => upd({ type: e.target.value })}>
                  {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </Field>
            </div>
            <Field label="URL"><input className="input" value={form.url ?? ""} onChange={(e) => upd({ url: e.target.value })} /></Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Парсер">
                <select className="input" value={form.parser_engine} onChange={(e) => upd({ parser_engine: e.target.value })}>
                  {ENGINES.map((e) => <option key={e} value={e}>{e}</option>)}
                </select>
              </Field>
              <Field label="Интервал проверки (сек)"><input type="number" className="input" value={form.check_interval_seconds ?? 300} onChange={(e) => upd({ check_interval_seconds: Number(e.target.value) })} /></Field>
            </div>
            <Field label="Приоритет"><input type="number" className="input" value={form.priority ?? 100} onChange={(e) => upd({ priority: Number(e.target.value) })} /></Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Использовать прокси">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={!!form.use_proxy} onChange={(e) => upd({ use_proxy: e.target.checked })} />
                  Да
                </label>
              </Field>
              <Field label="URL прокси"><input className="input" value={form.proxy_url ?? ""} onChange={(e) => upd({ proxy_url: e.target.value })} /></Field>
            </div>
            <Field label="Заголовки (JSON)"><textarea className="input min-h-[80px]" value={JSON.stringify(form.headers ?? {}, null, 2)} onChange={(e) => { try { upd({ headers: JSON.parse(e.target.value) }); } catch {} }} /></Field>
            <Field label="Cookies (JSON)"><textarea className="input min-h-[80px]" value={JSON.stringify(form.cookies ?? {}, null, 2)} onChange={(e) => { try { upd({ cookies: JSON.parse(e.target.value) }); } catch {} }} /></Field>
            <Field label="Auth (JSON)"><textarea className="input min-h-[80px]" value={JSON.stringify(form.auth ?? {}, null, 2)} onChange={(e) => { try { upd({ auth: JSON.parse(e.target.value) }); } catch {} }} /></Field>
            <Field label="Селекторы (JSON)"><textarea className="input min-h-[80px]" value={JSON.stringify(form.selectors ?? {}, null, 2)} onChange={(e) => { try { upd({ selectors: JSON.parse(e.target.value) }); } catch {} }} /></Field>
            <div className="flex gap-6">
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_active ?? true} onChange={(e) => upd({ is_active: e.target.checked })} /> Активен</label>
            </div>
            <div className="flex justify-end border-t border-border pt-4">
              <button className="btn-primary" onClick={save}>Сохранить</button>
            </div>
          </div>
        )}
      </Modal>

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
                    <button className="btn-outline py-1" onClick={() => openEdit(s)}>Редактировать</button>
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

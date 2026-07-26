"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { Page } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Modal, Field } from "@/components/Modal";

interface Template {
  id: number;
  name: string;
  is_default: boolean;
  is_active: boolean;
  format: string;
  header: string;
  body: string;
  footer: string;
  separator: string;
  custom_emoji_id?: string | null;
  subscribe_link?: string | null;
  disable_web_preview: boolean;
}

const EMPTY: Partial<Template> = {
  name: "",
  format: "telegram_html",
  header: "🔥 <b>{title}</b>",
  body: "{text}",
  footer: 'Источник: {source}\n————————\n👉 <a href="{link}">Подписаться</a>',
  separator: "\n\n",
  subscribe_link: "",
  is_default: false,
  is_active: true,
  disable_web_preview: true,
};

const PLACEHOLDERS = "{title} {text} {source} {source_url} {city} {date} {link}";

export default function TemplatesPage() {
  const { data, mutate } = useSWR<Page<Template>>("/templates?size=100", fetcher);
  const [form, setForm] = useState<Partial<Template> | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const openNew = () => { setForm({ ...EMPTY }); setError(null); };
  const openEdit = (t: Template) => { setForm({ ...t }); setError(null); };

  const save = async () => {
    if (!form) return;
    setError(null);
    try {
      if (form.id) {
        await api(`/templates/${form.id}`, { method: "PATCH", body: JSON.stringify(form) });
      } else {
        await api("/templates", { method: "POST", body: JSON.stringify(form) });
      }
      setForm(null);
      mutate();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const doPreview = async () => {
    if (!form?.id) { setError("Сначала сохраните шаблон, затем предпросмотр"); return; }
    const res = await api<{ detail: string }>(`/templates/${form.id}/preview`, { method: "POST" });
    setPreview(res.detail);
  };

  const remove = async (id: number) => {
    if (!confirm("Удалить шаблон?")) return;
    await api(`/templates/${id}`, { method: "DELETE" });
    mutate();
  };

  const upd = (patch: Partial<Template>) => setForm((f) => ({ ...f, ...patch }));

  return (
    <div>
      <PageHeader
        title="Шаблоны"
        action={<button className="btn-primary" onClick={openNew}>Создать шаблон</button>}
      />

      <div className="grid gap-4 md:grid-cols-2">
        {data?.items.map((t) => (
          <div key={t.id} className="card p-5">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="font-medium">{t.name}</h3>
              <div className="flex gap-1">
                {t.is_default && <span className="badge bg-emerald-100 text-emerald-700">по умолчанию</span>}
                {!t.is_active && <span className="badge bg-gray-100 text-gray-600">выключен</span>}
              </div>
            </div>
            <div className="space-y-1 whitespace-pre-wrap rounded-md bg-muted p-3 text-xs font-mono">
              <div>{t.header}</div>
              <div className="text-muted-foreground">{t.body}</div>
              <div>{t.footer}</div>
            </div>
            <div className="mt-3 flex gap-2">
              <button className="btn-outline py-1" onClick={() => openEdit(t)}>Редактировать</button>
              <button className="btn-danger py-1" onClick={() => remove(t.id)}>Удалить</button>
            </div>
          </div>
        ))}
        {data && data.items.length === 0 && (
          <p className="text-muted-foreground">Шаблонов нет. Создайте первый.</p>
        )}
      </div>

      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "Редактировать шаблон" : "Новый шаблон"} wide>
        {form && (
          <div className="space-y-4">
            {error && <p className="rounded-md bg-red-50 p-2 text-sm text-red-600">{error}</p>}
            <p className="rounded-md bg-blue-50 p-2 text-xs text-blue-800">
              Доступные плейсхолдеры: <span className="font-mono">{PLACEHOLDERS}</span>
            </p>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Название"><input className="input" value={form.name ?? ""} onChange={(e) => upd({ name: e.target.value })} /></Field>
              <Field label="Формат">
                <select className="input" value={form.format} onChange={(e) => upd({ format: e.target.value })}>
                  <option value="telegram_html">Telegram HTML</option>
                  <option value="html">HTML</option>
                  <option value="markdown">Markdown</option>
                </select>
              </Field>
            </div>
            <Field label="Заголовок (header)" hint="Верхняя строка публикации">
              <textarea className="input font-mono" value={form.header ?? ""} onChange={(e) => upd({ header: e.target.value })} />
            </Field>
            <Field label="Тело (body)" hint="Основной текст новости">
              <textarea className="input min-h-[80px] font-mono" value={form.body ?? ""} onChange={(e) => upd({ body: e.target.value })} />
            </Field>
            <Field label="Футер (footer)" hint="Нижняя часть: источник, подписка, разделители">
              <textarea className="input min-h-[80px] font-mono" value={form.footer ?? ""} onChange={(e) => upd({ footer: e.target.value })} />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Разделитель" hint="Между header/body/footer (\n\n)">
                <input className="input font-mono" value={form.separator ?? ""} onChange={(e) => upd({ separator: e.target.value })} />
              </Field>
              <Field label="Ссылка подписки {link}">
                <input className="input" value={form.subscribe_link ?? ""} onChange={(e) => upd({ subscribe_link: e.target.value })} />
              </Field>
            </div>
            <Field label="ID кастомного эмодзи" hint="Опционально, для Telegram Premium эмодзи">
              <input className="input" value={form.custom_emoji_id ?? ""} onChange={(e) => upd({ custom_emoji_id: e.target.value })} />
            </Field>
            <div className="flex gap-6">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={!!form.is_default} onChange={(e) => upd({ is_default: e.target.checked })} /> По умолчанию
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.is_active ?? true} onChange={(e) => upd({ is_active: e.target.checked })} /> Активен
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.disable_web_preview ?? true} onChange={(e) => upd({ disable_web_preview: e.target.checked })} /> Без превью ссылок
              </label>
            </div>

            {preview && (
              <div className="rounded-md border border-border bg-muted p-3">
                <div className="mb-1 text-xs text-muted-foreground">Предпросмотр:</div>
                <div className="whitespace-pre-wrap text-sm" dangerouslySetInnerHTML={{ __html: preview }} />
              </div>
            )}

            <div className="flex justify-end gap-2 border-t border-border pt-4">
              {form.id && <button className="btn-outline" onClick={doPreview}>Предпросмотр</button>}
              <button className="btn-primary" onClick={save}>Сохранить</button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

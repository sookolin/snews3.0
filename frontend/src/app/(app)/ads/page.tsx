"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { City, Page } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Modal, Field } from "@/components/Modal";
import { ButtonsEditor } from "@/components/ButtonsEditor";
import { TelegramPreview, type PreviewButton } from "@/components/TelegramPreview";

interface Channel { id: number; city_id: number; title: string; username?: string; avatar_url?: string }

interface Ad {
  id: number;
  title: string;
  advertiser?: string | null;
  text: string;
  status: string;
  channel_id?: number | null;
  buttons: PreviewButton[][];
  media_urls: string[];
  is_spoiler: boolean;
  price?: number | null;
  impressions: number;
  clicks: number;
  published_at?: string | null;
}

interface AdStats {
  total: number; published: number; draft: number; scheduled: number;
  total_impressions: number; total_clicks: number; total_revenue: number; ctr: number;
}

const EMPTY: Partial<Ad> = { title: "", text: "", buttons: [], media_urls: [], is_spoiler: false };

export default function AdsPage() {
  const { data, mutate } = useSWR<Page<Ad>>("/ads?size=100", fetcher);
  const { data: stats } = useSWR<AdStats>("/ads/stats", fetcher, { refreshInterval: 15000 });
  const { data: channels } = useSWR<Page<Channel>>("/channels?size=200", fetcher);
  const [form, setForm] = useState<Partial<Ad> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const openNew = () => { setForm({ ...EMPTY }); setError(null); };
  const openEdit = (a: Ad) => { setForm({ ...a, media_urls: a.media_urls ?? [] }); setError(null); };
  const upd = (patch: Partial<Ad>) => setForm((f) => ({ ...f, ...patch }));
  const channel = channels?.items.find((c) => c.id === form?.channel_id);

  const save = async () => {
    if (!form) return;
    setError(null);
    try {
      const payload = { ...form, media_urls: form.media_urls ?? [] };
      if (form.id) await api(`/ads/${form.id}`, { method: "PATCH", body: JSON.stringify(payload) });
      else await api("/ads", { method: "POST", body: JSON.stringify(payload) });
      setForm(null);
      mutate();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const publish = async (id: number) => {
    try { await api(`/ads/${id}/publish`, { method: "POST" }); mutate(); }
    catch (e) { alert((e as Error).message); }
  };
  const remove = async (id: number) => {
    if (!confirm("Удалить рекламу?")) return;
    await api(`/ads/${id}`, { method: "DELETE" });
    mutate();
  };

  return (
    <div>
      <PageHeader title="Реклама" action={<button className="btn-primary" onClick={openNew}>Создать рекламу</button>} />

      {stats && (
        <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div className="card p-4"><div className="text-sm text-muted-foreground">Всего</div><div className="mt-1 text-2xl font-semibold">{stats.total}</div></div>
          <div className="card p-4"><div className="text-sm text-muted-foreground">Опубликовано</div><div className="mt-1 text-2xl font-semibold text-green-600">{stats.published}</div></div>
          <div className="card p-4"><div className="text-sm text-muted-foreground">Показы / Клики</div><div className="mt-1 text-2xl font-semibold">{stats.total_impressions} / {stats.total_clicks}</div></div>
          <div className="card p-4"><div className="text-sm text-muted-foreground">CTR / Доход</div><div className="mt-1 text-2xl font-semibold">{stats.ctr}% / {stats.total_revenue.toLocaleString("ru-RU")} ₽</div></div>
        </div>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-muted-foreground">
            <tr>
              <th className="px-4 py-3">Название</th>
              <th className="px-4 py-3">Рекламодатель</th>
              <th className="px-4 py-3">Статус</th>
              <th className="px-4 py-3">Показы/Клики</th>
              <th className="px-4 py-3">Цена</th>
              <th className="px-4 py-3 text-right">Действия</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((a) => (
              <tr key={a.id} className="border-t border-border">
                <td className="px-4 py-3 font-medium">{a.title}</td>
                <td className="px-4 py-3">{a.advertiser || "—"}</td>
                <td className="px-4 py-3"><span className="badge bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-200">{a.status}</span></td>
                <td className="px-4 py-3">{a.impressions} / {a.clicks}</td>
                <td className="px-4 py-3">{a.price != null ? `${a.price} ₽` : "—"}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    <button className="btn-outline py-1" onClick={() => openEdit(a)}>Изменить</button>
                    <button className="btn-primary py-1" onClick={() => publish(a.id)}>Опубликовать</button>
                    <button className="btn-danger py-1" onClick={() => remove(a.id)}>Удалить</button>
                  </div>
                </td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">Рекламы нет</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "Редактировать рекламу" : "Новая реклама"} wide>
        {form && (
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-4">
              {error && <p className="rounded-md bg-red-50 p-2 text-sm text-red-600 dark:bg-red-950/40">{error}</p>}
              <div className="grid grid-cols-2 gap-3">
                <Field label="Название"><input className="input" value={form.title ?? ""} onChange={(e) => upd({ title: e.target.value })} /></Field>
                <Field label="Рекламодатель"><input className="input" value={form.advertiser ?? ""} onChange={(e) => upd({ advertiser: e.target.value })} /></Field>
              </div>
              <Field label="Канал">
                <select className="input" value={form.channel_id ?? ""} onChange={(e) => upd({ channel_id: e.target.value ? Number(e.target.value) : null })}>
                  <option value="">— выберите канал —</option>
                  {channels?.items.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
                </select>
              </Field>
              <Field label="Текст (HTML)"><textarea className="input min-h-[140px] font-mono" value={form.text ?? ""} onChange={(e) => upd({ text: e.target.value })} /></Field>
              <Field label="Медиа (URL, по одному в строке)">
                <textarea className="input min-h-[60px] font-mono" value={(form.media_urls ?? []).join("\n")} onChange={(e) => upd({ media_urls: e.target.value.split("\n").map((s) => s.trim()).filter(Boolean) })} />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Цена (₽)"><input type="number" className="input" value={form.price ?? ""} onChange={(e) => upd({ price: e.target.value ? Number(e.target.value) : null })} /></Field>
                <Field label="Спойлер">
                  <label className="mt-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={!!form.is_spoiler} onChange={(e) => upd({ is_spoiler: e.target.checked })} /> Скрыть медиа</label>
                </Field>
              </div>
              <div>
                <div className="mb-2 text-sm font-medium">Кнопки</div>
                <ButtonsEditor value={form.buttons ?? []} onChange={(b) => upd({ buttons: b })} />
              </div>
              <div className="flex justify-end border-t border-border pt-4">
                <button className="btn-primary" onClick={save}>Сохранить</button>
              </div>
            </div>
            <div>
              <div className="mb-2 text-sm font-medium">Предпросмотр</div>
              <TelegramPreview
                channelName={channel?.title || "Канал"}
                channelAvatar={channel?.avatar_url}
                title={form.title}
                text={form.text}
                media={(form.media_urls ?? []).map((u) => ({ url: u }))}
                buttons={form.buttons ?? []}
              />
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

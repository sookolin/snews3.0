"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { Pencil, Send, Trash2, Upload, Trash } from "lucide-react";
import { api, fetcher, getToken } from "@/lib/api";
import type { Page } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Modal, Field } from "@/components/Modal";
import { Checkbox, Select, Switch } from "@/components/Controls";
import { ButtonsEditor } from "@/components/ButtonsEditor";
import { RichTextEditor } from "@/components/RichTextEditor";
import { TelegramPreview, type PreviewButton } from "@/components/TelegramPreview";
import { YandexMapPicker } from "@/components/YandexMapPicker";
import { ResizableTable } from "@/components/ResizableTable";
import { useToast } from "@/components/Toast";
import { confirm } from "@/components/ConfirmDialog";

interface Channel { id: number; city_id: number; title: string; username?: string; avatar_url?: string }
interface Template { id: number; name: string }
interface AdMediaFile { path: string; type: string; spoiler?: boolean }

interface AdSchedule {
  times?: string[];
  weekdays?: number[];
  day_parity?: "any" | "even" | "odd";
  date_from?: string;
  date_to?: string;
}

interface Ad {
  id: number;
  title: string;
  heading?: string | null;
  advertiser?: string | null;
  text: string;
  status: string;
  channel_id?: number | null;
  template_id?: number | null;
  buttons: PreviewButton[][];
  media_urls: string[];
  media_files: AdMediaFile[];
  is_spoiler: boolean;
  price?: number | null;
  erid?: string | null;
  advertiser_inn?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  location_title?: string | null;
  location_address?: string | null;
  schedule: AdSchedule;
  auto_publish: boolean;
  impressions: number;
  clicks: number;
}

interface AdStats {
  total: number; published: number; draft: number; scheduled: number;
  total_impressions: number; total_clicks: number; total_revenue: number; ctr: number;
}

const EMPTY: Partial<Ad> = {
  title: "", text: "", buttons: [], media_urls: [], media_files: [], is_spoiler: false,
  schedule: {}, auto_publish: false,
};

/** Ad lifecycle statuses (mirrors `shared.enums.AdStatus`). */
const AD_STATUS: Record<string, { label: string; className: string }> = {
  draft: {
    label: "Черновик",
    className:
      "bg-slate-50 text-slate-700 ring-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700",
  },
  scheduled: {
    label: "Запланирована",
    className:
      "bg-violet-50 text-violet-700 ring-violet-200 dark:bg-violet-950/50 dark:text-violet-300 dark:ring-violet-900",
  },
  published: {
    label: "Опубликована",
    className:
      "bg-green-50 text-green-700 ring-green-200 dark:bg-green-950/50 dark:text-green-300 dark:ring-green-900",
  },
  archived: {
    label: "В архиве",
    className:
      "bg-gray-50 text-gray-600 ring-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:ring-gray-700",
  },
  failed: {
    label: "Ошибка",
    className:
      "bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-950/50 dark:text-rose-300 dark:ring-rose-900",
  },
};

const WEEKDAYS = [
  { v: 1, l: "Пн" }, { v: 2, l: "Вт" }, { v: 3, l: "Ср" }, { v: 4, l: "Чт" },
  { v: 5, l: "Пт" }, { v: 6, l: "Сб" }, { v: 7, l: "Вс" },
];

export default function AdsPage() {
  const { data, mutate } = useSWR<Page<Ad>>("/ads?size=100", fetcher);
  const { data: stats } = useSWR<AdStats>("/ads/stats", fetcher, { refreshInterval: 15000 });
  const { data: channels } = useSWR<Page<Channel>>("/channels?size=200", fetcher);
  const { data: templates } = useSWR<Page<Template>>("/templates?size=100", fetcher);
  const [form, setForm] = useState<Partial<Ad> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [showMap, setShowMap] = useState(false);
  const [renderedAd, setRenderedAd] = useState("");
  const toast = useToast();

  // Render the ad exactly as it will be published (template + legal marking).
  useEffect(() => {
    if (!form) {
      setRenderedAd("");
      return;
    }
    const t = setTimeout(async () => {
      try {
        const r = await api<{ detail: string }>("/ads/render", {
          method: "POST",
          body: JSON.stringify({
            heading: form.heading ?? "",
            text: form.text ?? "",
            advertiser: form.advertiser ?? "",
            advertiser_inn: form.advertiser_inn ?? "",
            erid: form.erid ?? "",
            template_id: form.template_id ?? null,
          }),
        });
        setRenderedAd(r.detail);
      } catch {
        /* keep the previous preview */
      }
    }, 400);
    return () => clearTimeout(t);
  }, [
    form?.heading, form?.text, form?.advertiser, form?.advertiser_inn,
    form?.erid, form?.template_id,
  ]);

  const openNew = () => { setForm({ ...EMPTY }); setError(null); };
  const openEdit = (a: Ad) => {
    setForm({ ...a, media_urls: a.media_urls ?? [], media_files: a.media_files ?? [], schedule: a.schedule ?? {} });
    setError(null);
  };
  const upd = (patch: Partial<Ad>) => setForm((f) => ({ ...f, ...patch }));
  const updSched = (patch: Partial<AdSchedule>) =>
    setForm((f) => ({ ...f, schedule: { ...(f?.schedule ?? {}), ...patch } }));
  const channel = channels?.items.find((c) => c.id === form?.channel_id);

  const persistAndGetId = async (): Promise<number> => {
    if (form?.id) return form.id;
    const created = await api<Ad>("/ads", { method: "POST", body: JSON.stringify({ ...form }) });
    setForm((f) => ({ ...f, ...created }));
    return created.id;
  };

  const save = async () => {
    if (!form) return;
    setError(null);
    try {
      const payload = { ...form, media_urls: form.media_urls ?? [], media_files: form.media_files ?? [] };
      if (form.id) await api(`/ads/${form.id}`, { method: "PATCH", body: JSON.stringify(payload) });
      else await api("/ads", { method: "POST", body: JSON.stringify(payload) });
      setForm(null);
      mutate();
    } catch (e) { setError((e as Error).message); }
  };

  const uploadMedia = async (files: FileList | null) => {
    if (!files || !files.length || !form) return;
    setUploading(true);
    setError(null);
    try {
      const id = await persistAndGetId();
      let last: Ad | null = null;
      for (const file of Array.from(files)) {
        const fd = new FormData();
        fd.append("file", file);
        const res = await fetch(`/api/v1/ads/${id}/media`, {
          method: "POST",
          headers: { Authorization: `Bearer ${getToken()}` },
          body: fd,
        });
        if (res.ok) last = await res.json();
      }
      if (last) setForm((f) => ({ ...f, media_files: last!.media_files }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
    }
  };

  const removeFile = (path: string) =>
    upd({ media_files: (form?.media_files ?? []).filter((m) => m.path !== path) });

  /** Toggle the spoiler flag on a single uploaded file. */
  const toggleFileSpoiler = (path: string, spoiler: boolean) =>
    upd({
      media_files: (form?.media_files ?? []).map((m) =>
        m.path === path ? { ...m, spoiler } : m
      ),
    });

  const publish = async (id: number) => {
    try {
      await api(`/ads/${id}/publish`, { method: "POST" });
      mutate();
      toast.success("Реклама отправлена на публикацию");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  const remove = async (id: number) => {
    if (!(await confirm({ message: "Удалить рекламу?", danger: true }))) return;
    try {
      await api(`/ads/${id}`, { method: "DELETE" });
      mutate();
      toast.success("Реклама удалена");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const previewMedia = [
    ...(form?.media_files ?? []).map((m) => ({
      url: `/media/${m.path}`,
      type: m.type,
      spoiler: m.spoiler ?? form?.is_spoiler,
    })),
    ...(form?.media_urls ?? []).map((u) => ({ url: u, spoiler: form?.is_spoiler })),
  ];

  const sched = form?.schedule ?? {};
  const toggleWeekday = (v: number) => {
    const cur = new Set(sched.weekdays ?? []);
    cur.has(v) ? cur.delete(v) : cur.add(v);
    updSched({ weekdays: [...cur].sort() });
  };

  return (
    <div>
      <PageHeader title="Реклама" action={<button className="btn-primary" onClick={openNew}>Создать рекламу</button>} />

      {stats && (
        <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div className="card p-4"><div className="text-sm text-muted-foreground">Всего</div><div className="mt-1 text-2xl font-semibold">{stats.total}</div></div>
          <div className="card p-4"><div className="text-sm text-muted-foreground">Опубликовано</div><div className="mt-1 text-2xl font-semibold text-emerald-600">{stats.published}</div></div>
          <div className="card p-4"><div className="text-sm text-muted-foreground">Показы / Клики</div><div className="mt-1 text-2xl font-semibold">{stats.total_impressions} / {stats.total_clicks}</div></div>
          <div className="card p-4"><div className="text-sm text-muted-foreground">CTR / Доход</div><div className="mt-1 text-2xl font-semibold">{stats.ctr}% / {stats.total_revenue.toLocaleString("ru-RU")} ₽</div></div>
        </div>
      )}

      <div className="card overflow-hidden">
        <div className="table-wrap">
        <ResizableTable
          id="ads"
          columns={[
            "Название",
            "Рекламодатель",
            "erid",
            "Авто",
            "Статус",
            "Показы/Клики",
            "Цена",
            "Действия",
          ]}
        >
            {data?.items.map((a) => (
              <tr key={a.id} className="border-t border-border">
                <td className="px-4 py-3 font-medium">{a.title}</td>
                <td className="px-4 py-3">{a.advertiser || "—"}</td>
                <td className="px-4 py-3 font-mono text-xs">{a.erid || "—"}</td>
                <td className="px-4 py-3">{a.auto_publish ? "✓" : "—"}</td>
                <td className="px-4 py-3">
                  <span
                    className={`badge whitespace-nowrap ${
                      AD_STATUS[a.status]?.className ??
                      "bg-slate-50 text-slate-700 ring-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700"
                    }`}
                  >
                    {AD_STATUS[a.status]?.label ?? a.status}
                  </span>
                </td>
                <td className="px-4 py-3">{a.impressions} / {a.clicks}</td>
                <td className="px-4 py-3">{a.price != null ? `${a.price} ₽` : "—"}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-center gap-1.5">
                    <button className="btn-icon" title="Изменить" onClick={() => openEdit(a)}><Pencil className="h-4 w-4" /></button>
                    <button className="btn-icon-primary" title="Опубликовать" onClick={() => publish(a.id)}><Send className="h-4 w-4" /></button>
                    <button className="btn-icon-danger" title="Удалить" onClick={() => remove(a.id)}><Trash2 className="h-4 w-4" /></button>
                  </div>
                </td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-6 text-center text-muted-foreground">Рекламы нет</td></tr>
            )}
        </ResizableTable>
        </div>
      </div>

      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "Редактировать рекламу" : "Новая реклама"} size="xl">
        {form && (
          <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
            {/* Left: form */}
            <div className="space-y-4">
              {error && <p className="rounded-md bg-rose-50 p-2 text-sm text-rose-600 dark:bg-rose-950/40">{error}</p>}
              <div className="grid items-start gap-4 sm:grid-cols-2">
                <Field label="Название" hint="Только для списка в админке, в пост не попадает">
                  <input className="input" value={form.title ?? ""} onChange={(e) => upd({ title: e.target.value })} />
                </Field>
                <Field label="Рекламодатель" hint="Для маркировки «Реклама. …»">
                  <input className="input" value={form.advertiser ?? ""} onChange={(e) => upd({ advertiser: e.target.value })} />
                </Field>
              </div>
              <Field label="Заголовок поста" hint="Публикуется в сообщении (подставляется в {title} шаблона)">
                <input className="input" value={form.heading ?? ""} onChange={(e) => upd({ heading: e.target.value })} />
              </Field>
              <div className="grid items-start gap-4 sm:grid-cols-2">
                <Field label="Канал" hint="Куда публиковать">
                  <Select
                    value={form.channel_id ?? ""}
                    onChange={(v) => upd({ channel_id: v ? Number(v) : null })}
                  >
                    <option value="">— выберите канал —</option>
                    {channels?.items.map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}
                  </Select>
                </Field>
                <Field label="Шаблон" hint="Оформление поста">
                  <Select
                    value={form.template_id ?? ""}
                    onChange={(v) => upd({ template_id: v ? Number(v) : null })}
                  >
                    <option value="">Без шаблона</option>
                    {templates?.items.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                  </Select>
                </Field>
              </div>

              <div>
                <span className="text-sm font-medium">Текст</span>
                <div className="mt-1">
                  <RichTextEditor value={form.text ?? ""} onChange={(html) => upd({ text: html })} />
                </div>
              </div>

              {/* Media */}
              <div className="rounded-lg border border-border p-3">
                <div className="mb-2 text-sm font-medium">Вложения</div>
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <label className="btn-outline cursor-pointer py-1">
                    <Upload className="h-4 w-4" /> С устройства
                    <input type="file" accept="image/*,video/*" multiple className="hidden" disabled={uploading} onChange={(e) => uploadMedia(e.target.files)} />
                  </label>
                  {uploading && <span className="text-xs text-muted-foreground">Загрузка…</span>}
                </div>
                {(form.media_files ?? []).length > 0 && (
                  <div className="mb-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
                    {(form.media_files ?? []).map((m) => (
                      <div key={m.path} className="rounded-lg border border-border p-2">
                        <div className="aspect-video overflow-hidden rounded bg-muted">
                          {m.type === "video" ? (
                            <video src={`/media/${m.path}`} className="h-full w-full object-cover" controls />
                          ) : (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              src={`/media/${m.path}`}
                              alt=""
                              className={`h-full w-full object-cover ${m.spoiler ? "blur-md" : ""}`}
                            />
                          )}
                        </div>
                        <div className="mt-2 flex items-center justify-between gap-2">
                          <Checkbox
                            checked={!!m.spoiler}
                            onChange={(v) => toggleFileSpoiler(m.path, v)}
                            label={<span className="text-xs">Спойлер</span>}
                          />
                          <button className="btn-icon-danger h-6 w-6" title="Убрать" onClick={() => removeFile(m.path)}>
                            <Trash className="h-3 w-3" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <Field label="Медиа по URL" hint="По одному в строке">
                  <textarea className="input input-compact font-mono text-xs" value={(form.media_urls ?? []).join("\n")} onChange={(e) => upd({ media_urls: e.target.value.split("\n").map((s) => s.trim()).filter(Boolean) })} />
                </Field>
                <div className="mt-2">
                  <Checkbox
                    checked={!!form.is_spoiler}
                    onChange={(v) => upd({ is_spoiler: v })}
                    label="Скрыть все медиа (спойлер по умолчанию)"
                  />
                </div>
              </div>

              {/* Geolocation */}
              <div className="rounded-lg border border-border p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-medium">Геолокация</span>
                  <button className="btn-outline py-1 text-xs" onClick={() => setShowMap((v) => !v)}>
                    {showMap ? "Скрыть карту" : "Выбрать на Яндекс.Картах"}
                  </button>
                </div>
                {showMap && (
                  <div className="mb-3">
                    <YandexMapPicker
                      latitude={form.latitude ?? null}
                      longitude={form.longitude ?? null}
                      onPick={(lat, lon, addr) => upd({ latitude: lat, longitude: lon, location_address: addr ?? form.location_address })}
                    />
                  </div>
                )}
                <div className="grid grid-cols-2 gap-2">
                  <input className="input" type="number" step="any" placeholder="Широта" value={form.latitude ?? ""} onChange={(e) => upd({ latitude: e.target.value ? Number(e.target.value) : null })} />
                  <input className="input" type="number" step="any" placeholder="Долгота" value={form.longitude ?? ""} onChange={(e) => upd({ longitude: e.target.value ? Number(e.target.value) : null })} />
                  <input className="input" placeholder="Название места" value={form.location_title ?? ""} onChange={(e) => upd({ location_title: e.target.value })} />
                  <input className="input" placeholder="Адрес" value={form.location_address ?? ""} onChange={(e) => upd({ location_address: e.target.value })} />
                </div>
              </div>

              {/* Schedule */}
              <div className="rounded-lg border border-border p-3">
                <div className="mb-3">
                  <Switch
                    checked={!!form.auto_publish}
                    onChange={(v) => upd({ auto_publish: v })}
                    label={<span className="font-medium">Автопубликация по расписанию</span>}
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Field label="Время (через запятую)" hint="Напр. 09:00, 18:30">
                    <input className="input" value={(sched.times ?? []).join(", ")} onChange={(e) => updSched({ times: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} />
                  </Field>
                  <Field label="Чётность дней">
                    <Select
                      value={sched.day_parity ?? "any"}
                      onChange={(v) => updSched({ day_parity: v as AdSchedule["day_parity"] })}
                    >
                      <option value="any">Любые дни</option>
                      <option value="even">Только чётные</option>
                      <option value="odd">Только нечётные</option>
                    </Select>
                  </Field>
                </div>
                <div className="mt-2">
                  <div className="mb-1 text-xs text-muted-foreground">Дни недели</div>
                  <div className="flex gap-1">
                    {WEEKDAYS.map((d) => (
                      <button key={d.v} type="button"
                        className={`h-8 w-9 rounded-md border text-xs font-medium ${(sched.weekdays ?? []).includes(d.v) ? "border-transparent bg-primary text-white" : "border-border bg-card text-muted-foreground"}`}
                        onClick={() => toggleWeekday(d.v)}>{d.l}</button>
                    ))}
                  </div>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2">
                  <Field label="Дата с"><input className="input" type="date" value={sched.date_from ?? ""} onChange={(e) => updSched({ date_from: e.target.value })} /></Field>
                  <Field label="Дата по"><input className="input" type="date" value={sched.date_to ?? ""} onChange={(e) => updSched({ date_to: e.target.value })} /></Field>
                </div>
              </div>

              {/* Commercial */}
              <div className="grid grid-cols-3 gap-3">
                <Field label="Цена (₽)"><input type="number" className="input" value={form.price ?? ""} onChange={(e) => upd({ price: e.target.value ? Number(e.target.value) : null })} /></Field>
                <Field label="erid" hint="Токен ОРД"><input className="input" value={form.erid ?? ""} onChange={(e) => upd({ erid: e.target.value })} /></Field>
                <Field label="ИНН"><input className="input" value={form.advertiser_inn ?? ""} onChange={(e) => upd({ advertiser_inn: e.target.value })} /></Field>
              </div>

              <div>
                <div className="mb-2 text-sm font-medium">Кнопки</div>
                <ButtonsEditor value={form.buttons ?? []} onChange={(b) => upd({ buttons: b })} />
              </div>

              <div className="flex justify-end border-t border-border pt-4">
                <button className="btn-primary" onClick={save}>Сохранить</button>
              </div>
            </div>

            {/* Right: sticky preview */}
            <div className="lg:sticky lg:top-0 lg:self-start">
              <div className="mb-2 text-sm font-medium">Предпросмотр</div>
              <TelegramPreview
                channelName={channel?.title || "Канал"}
                channelAvatar={channel?.avatar_url}
                text={renderedAd || form.text || ""}
                media={previewMedia}
                buttons={form.buttons ?? []}
                locationTitle={form.location_title}
              />
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

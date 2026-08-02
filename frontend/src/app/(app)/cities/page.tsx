"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { City, Page } from "@/lib/types";
import { Copy, Pencil, PlugZap, RefreshCw, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Modal, Field } from "@/components/Modal";
import { Checkbox, Select } from "@/components/Controls";
import { ResizableTable } from "@/components/ResizableTable";
import { useToast } from "@/components/Toast";
import { confirm } from "@/components/ConfirmDialog";

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
  kind: string;
  is_world_bucket: boolean;
  weather_enabled: boolean;
  weather_time: string;
  weather_lat?: number | null;
  weather_lon?: number | null;
}

const EMPTY: CityForm = {
  name: "", description: "", keywords: "", extra_keywords: "", exclude_keywords: "",
  region: "", country: "", language: "ru", is_active: true, telegram_topic_id: null,
  kind: "city", is_world_bucket: false,
  weather_enabled: false, weather_time: "08:00", weather_lat: null, weather_lon: null,
};

/** "other" entries are non-geographic sections: мир, интернет, спорт и т.п. */
const KINDS = [
  { value: "city", label: "Город" },
  { value: "other", label: "Другое (мир, интернет…)" },
];

const toArr = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);
const fromArr = (a?: string[]) => (a ?? []).join(", ");

export default function CitiesPage() {
  const { data, mutate } = useSWR<Page<City>>("/cities?size=100", fetcher);
  const { data: settings } = useSWR<Record<string, unknown>>("/settings", fetcher);
  const botUsername = String(settings?.["bot.username"] ?? "").replace(/^@/, "");
  const [form, setForm] = useState<CityForm | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [worldTopicName, setWorldTopicName] = useState("🌍 Мировые новости");
  const [worldTopicModalOpen, setWorldTopicModalOpen] = useState(false);
  const toast = useToast();

  const openNew = () => { setForm({ ...EMPTY }); setError(null); };
  const openEdit = (c: City) => {
    setForm({
      id: c.id, name: c.name, description: c.description ?? "",
      keywords: fromArr(c.keywords), extra_keywords: fromArr(c.extra_keywords),
      exclude_keywords: fromArr(c.exclude_keywords), region: c.region ?? "",
      country: c.country ?? "", language: c.language, is_active: c.is_active,
      telegram_topic_id: c.telegram_topic_id,
      kind: c.kind ?? "city", is_world_bucket: c.is_world_bucket ?? false,
      weather_enabled: c.weather_enabled ?? false,
      weather_time: c.weather_time ?? "08:00",
      weather_lat: c.weather_lat ?? null,
      weather_lon: c.weather_lon ?? null,
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
      kind: form.kind,
      // Only a non-geographic entry can collect world / unmatched news.
      is_world_bucket: form.kind === "other" ? form.is_world_bucket : false,
      weather_enabled: form.weather_enabled,
      weather_time: form.weather_time || null,
      weather_lat: form.weather_lat ?? null,
      weather_lon: form.weather_lon ?? null,
    };
    try {
      if (form.id) await api(`/cities/${form.id}`, { method: "PATCH", body: JSON.stringify(body) });
      else await api("/cities", { method: "POST", body: JSON.stringify(body) });
      setForm(null);
      mutate();
      toast.success(form.id ? "Раздел обновлён" : "Раздел создан");
    } catch (e) {
      setError((e as Error).message);
      toast.error((e as Error).message);
    }
  };

  const remove = async (id: number) => {
    if (!(await confirm({ message: "Удалить раздел?", danger: true }))) return;
    try {
      await api(`/cities/${id}`, { method: "DELETE" });
      mutate();
      toast.success("Раздел удалён");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const [testingWeather, setTestingWeather] = useState(false);
  const testWeather = async (id: number) => {
    setTestingWeather(true);
    try {
      const r = await api<{ detail: string }>(`/cities/${id}/weather/test`, { method: "POST" });
      toast.success(r.detail);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setTestingWeather(false);
    }
  };

  const recreateTopic = async (id: number) => {
    try {
      await api(`/cities/${id}/create-topic`, { method: "POST" });
      mutate();
      toast.success("Топик пересоздан");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const testTopic = async (id: number) => {
    try {
      const r = await api<{ detail: string }>(`/cities/${id}/test-topic`, { method: "POST" });
      toast.success("Топик привязан: " + r.detail);
    } catch (e) {
      toast.error("Ошибка: " + (e as Error).message);
    }
  };

  const createWorldTopic = async () => {
    try {
      const r = await api<{ topic_id: number }>("/settings/world-topic", {
        method: "POST",
        body: JSON.stringify({ name: worldTopicName }),
      });
      setWorldTopicModalOpen(false);
      mutate();
      toast.success(`Топик мировых новостей создан (ID ${r.topic_id})`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <div>
      <PageHeader
        title="Города и разделы"
        action={
          <div className="flex gap-2">
            <button className="btn-outline" onClick={() => setWorldTopicModalOpen(true)}>
              Создать топик «Мировые»
            </button>
            <button className="btn-primary" onClick={openNew}>Добавить раздел</button>
          </div>
        }
      />

      <div className="card overflow-hidden">
        <div className="table-wrap">
        <ResizableTable
          id="cities"
          columns={[
            "Название",
            "Тип",
            "Ключевые слова",
            "Topic ID",
            "Ссылка для предложки",
            "Активен",
            "Действия",
          ]}
        >
            {data?.items.map((c) => (
              <tr key={c.id} className="border-t border-border">
                <td className="px-4 py-3 font-medium">{c.name}</td>
                <td className="px-4 py-3 text-xs text-muted-foreground">
                  {c.kind === "other" ? "Другое" : "Город"}
                  {c.is_world_bucket && <span className="ml-1" title="Собирает мировые новости">🌍</span>}
                </td>
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
                          toast.info("Ссылка скопирована");
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
                  <div className="flex justify-center gap-2">
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
        </ResizableTable>
        </div>
      </div>

      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "Редактировать раздел" : "Новый раздел"} wide>
        {form && (
          <div className="space-y-4">
            {error && <p className="rounded-md bg-red-50 p-2 text-sm text-red-600 dark:bg-red-950/40">{error}</p>}
            <Field label="Тип раздела" hint="«Другое» — для негеографических разделов: мир, интернет и т.п.">
              <Select value={form.kind} onChange={(v) => upd({ kind: v })}>
                {KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
              </Select>
            </Field>
            <Field label="Название" hint="Используется в шаблоне {city} и как ключевое слово">
              <input className="input" value={form.name} onChange={(e) => upd({ name: e.target.value })} />
            </Field>
            {form.kind === "other" && (
              <div className="flex items-start gap-2 text-sm">
                <div className="mt-0.5">
                  <Checkbox
                    checked={form.is_world_bucket}
                    onChange={(v) => upd({ is_world_bucket: v })}
                  />
                </div>
                <span>
                  Собирать мировые новости
                  <span className="block text-xs text-muted-foreground">
                    Новости, не подошедшие ни к одному городу, попадут сюда, а не в первый город.
                    Такой раздел может быть только один.
                  </span>
                </span>
              </div>
            )}
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
                <Select value={form.language} onChange={(v) => upd({ language: v })}>
                  <option value="ru">ru</option>
                  <option value="en">en</option>
                </Select>
              </Field>
              <Field label="Topic ID" hint="ID ветки в группе модерации Telegram. Создаётся автоматически, но можно задать вручную.">
                <input className="input" type="number" value={form.telegram_topic_id ?? ""} onChange={(e) => upd({ telegram_topic_id: e.target.value ? Number(e.target.value) : null })} />
              </Field>
            </div>
            <Checkbox
              checked={form.is_active}
              onChange={(v) => upd({ is_active: v })}
              label="Активен (собирать новости)"
            />

            {/* Daily weather post */}
            <div className="rounded-lg border border-border p-4">
              <Checkbox
                checked={form.weather_enabled}
                onChange={(v) => upd({ weather_enabled: v })}
                label="Публиковать погоду на день в канал города"
              />
              {form.weather_enabled && (
                <div className="mt-3 grid grid-cols-2 gap-4">
                  <Field label="Время публикации" hint="Часовой пояс — как в настройках интерфейса">
                    <input
                      className="input"
                      type="time"
                      value={form.weather_time}
                      onChange={(e) => upd({ weather_time: e.target.value })}
                    />
                  </Field>
                  <div />
                  <Field label="Широта" hint="Необязательно — иначе определится по названию города">
                    <input
                      className="input"
                      type="number"
                      step="any"
                      value={form.weather_lat ?? ""}
                      onChange={(e) => upd({ weather_lat: e.target.value === "" ? null : Number(e.target.value) })}
                    />
                  </Field>
                  <Field label="Долгота" hint="Необязательно">
                    <input
                      className="input"
                      type="number"
                      step="any"
                      value={form.weather_lon ?? ""}
                      onChange={(e) => upd({ weather_lon: e.target.value === "" ? null : Number(e.target.value) })}
                    />
                  </Field>
                  {form.id && (
                    <div className="col-span-2">
                      <button
                        type="button"
                        className="btn-outline text-sm"
                        disabled={testingWeather}
                        onClick={() => testWeather(form.id!)}
                      >
                        {testingWeather ? "Публикация…" : "Опубликовать погоду сейчас"}
                      </button>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Проверка: сразу отправит прогноз в каналы города (минуя расписание).
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="flex justify-end border-t border-border pt-4">
              <button className="btn-primary" onClick={save}>Сохранить</button>
            </div>
          </div>
        )}
      </Modal>

      {/* World topic creation modal */}
      <Modal
        open={worldTopicModalOpen}
        onClose={() => setWorldTopicModalOpen(false)}
        title="Создать топик для мировых новостей"
      >
        <div className="space-y-4">
          <Field label="Название топика" hint="Будет отображаться в группе модерации Telegram">
            <input
              className="input"
              value={worldTopicName}
              onChange={(e) => setWorldTopicName(e.target.value)}
            />
          </Field>
          <div className="flex justify-end border-t border-border pt-4">
            <button className="btn-primary" onClick={createWorldTopic}>
              Создать
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

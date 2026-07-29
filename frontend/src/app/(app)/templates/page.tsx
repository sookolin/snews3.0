"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { Check, Copy, Pencil, Plus, Trash2, X } from "lucide-react";
import { api, fetcher } from "@/lib/api";
import type { Page } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Modal, Field } from "@/components/Modal";
import { EmojiPickerButton } from "@/components/EmojiPickerButton";
import { Checkbox, Select } from "@/components/Controls";
import { useToast } from "@/components/Toast";
import { confirm } from "@/components/ConfirmDialog";

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
  variables: Record<string, string>;
  disable_web_preview: boolean;
  uppercase_title: boolean;
}

const EMPTY: Partial<Template> = {
  name: "",
  format: "telegram_html",
  header: "{emoji} <b>{title}</b>",
  body: "{text}",
  footer: 'Источник: {source}\nАвтор: {author}\n————————\n👉 <a href="{link}">Подписаться</a>',
  separator: "\n\n",
  subscribe_link: "",
  variables: {},
  is_default: false,
  is_active: true,
  disable_web_preview: true,
  uppercase_title: false,
};

const TAGS: { tag: string; desc: string }[] = [
  { tag: "{title}", desc: "Заголовок новости (после AI)" },
  { tag: "{text}", desc: "Основной текст новости" },
  { tag: "{emoji}", desc: "Эмодзи, подобранный AI/редактором" },
  { tag: "{custom_emoji}", desc: "Премиум-эмодзи по ID (tg-emoji), нужен Telegram Premium у владельца бота" },
  { tag: "{source}", desc: "Название источника (пусто → строка скрывается)" },
  { tag: "{source_url}", desc: "Ссылка на оригинал" },
  { tag: "{author}", desc: "Автор (для предложенных; пусто → скрывается)" },
  { tag: "{city}", desc: "Название города" },
  { tag: "{date}", desc: "Дата/время публикации" },
  {
    tag: "{link}",
    desc: "Ссылка подписки — подставляется автоматически по каналу города, в который идёт пост",
  },
];

const HTML_TAGS = "<b>жирный</b> · <i>курсив</i> · <u>подчёркнутый</u> · <s>зачёркнутый</s> · <a href=\"URL\">ссылка</a> · <code>моно</code> · <tg-spoiler>спойлер</tg-spoiler>";

export default function TemplatesPage() {
  const { data, mutate } = useSWR<Page<Template>>("/templates?size=100", fetcher);
  const { data: settingsData } = useSWR<Record<string, unknown>>("/settings", fetcher);
  const [activeTab, setActiveTab] = useState<"templates" | "moderation">("templates");
  const [form, setForm] = useState<Partial<Template> | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [varKey, setVarKey] = useState("");
  const [varVal, setVarVal] = useState("");
  // Custom tag currently being edited (its original key), plus draft values.
  const [editingVar, setEditingVar] = useState<string | null>(null);
  const [editKey, setEditKey] = useState("");
  const [editVal, setEditVal] = useState("");
  // Moderation card template
  const [modTemplate, setModTemplate] = useState<string>("");
  const [modSaving, setModSaving] = useState(false);
  const toast = useToast();

  // Init moderation template from settings
  useEffect(() => {
    if (settingsData) {
      setModTemplate(String(settingsData["moderation.card_template"] ?? ""));
    }
  }, [settingsData]);

  const openNew = () => { setForm({ ...EMPTY }); setPreview(null); setError(null); setEditingVar(null); };
  const openEdit = (t: Template) => { setForm({ ...t, variables: t.variables ?? {} }); setPreview(null); setError(null); setEditingVar(null); };
  const upd = (patch: Partial<Template>) => setForm((f) => ({ ...f, ...patch }));

  const save = async () => {
    if (!form) return;
    setError(null);
    try {
      if (form.id) await api(`/templates/${form.id}`, { method: "PATCH", body: JSON.stringify(form) });
      else await api("/templates", { method: "POST", body: JSON.stringify(form) });
      setForm(null);
      mutate();
    } catch (e) { setError((e as Error).message); }
  };

  const doPreview = async () => {
    if (!form?.id) { setError("Сначала сохраните шаблон, затем предпросмотр"); return; }
    const res = await api<{ detail: string }>(`/templates/${form.id}/preview`, { method: "POST" });
    setPreview(res.detail);
  };

  const remove = async (id: number) => {
    if (!(await confirm({ message: "Удалить шаблон?", danger: true }))) return;
    try {
      await api(`/templates/${id}`, { method: "DELETE" });
      mutate();
      toast.success("Шаблон удалён");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  /** Duplicate a template so a variant can be built without retyping it. */
  const duplicate = async (id: number) => {
    try {
      const copy = await api<Template>(`/templates/${id}/duplicate`, { method: "POST" });
      await mutate();
      openEdit(copy);
      toast.success("Копия шаблона создана");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const addVar = () => {
    if (!form || !varKey.trim()) return;
    upd({ variables: { ...(form.variables ?? {}), [varKey.trim()]: varVal } });
    setVarKey(""); setVarVal("");
  };
  const removeVar = (k: string) => {
    if (!form) return;
    const v = { ...(form.variables ?? {}) };
    delete v[k];
    upd({ variables: v });
    if (editingVar === k) setEditingVar(null);
  };

  /** Start editing an existing custom tag (name and value are both editable). */
  const startEditVar = (k: string, v: string) => {
    setEditingVar(k);
    setEditKey(k);
    setEditVal(v);
  };

  /** Commit the edit, preserving tag order and renaming the key if needed. */
  const commitEditVar = () => {
    if (!form || editingVar === null) return;
    const nextKey = editKey.trim();
    if (!nextKey) return;
    const entries = Object.entries(form.variables ?? {}).map(([k, v]) =>
      k === editingVar ? ([nextKey, editVal] as const) : ([k, v] as const)
    );
    upd({ variables: Object.fromEntries(entries) });
    setEditingVar(null);
  };

  const saveModTemplate = async () => {
    setModSaving(true);
    try {
      await api(`/settings/${encodeURIComponent("moderation.card_template")}`, {
        method: "PUT",
        body: JSON.stringify({ value: modTemplate }),
      });
      toast.success("Шаблон карточки сохранён");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setModSaving(false);
    }
  };

  const TAB_CLASSES = (active: boolean) =>
    `px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
      active
        ? "border-primary text-primary"
        : "border-transparent text-muted-foreground hover:text-foreground"
    }`;

  return (
    <div>
      <PageHeader
        title="Шаблоны"
        action={activeTab === "templates" ? <button className="btn-primary" onClick={openNew}>Создать шаблон</button> : null}
      />

      {/* Tabs */}
      <div className="mb-5 flex gap-1 border-b border-border">
        <button className={TAB_CLASSES(activeTab === "templates")} onClick={() => setActiveTab("templates")}>
          Шаблоны публикаций
        </button>
        <button className={TAB_CLASSES(activeTab === "moderation")} onClick={() => setActiveTab("moderation")}>
          Карточка модерации
        </button>
      </div>

      {activeTab === "templates" && (
        <div className="grid gap-4 md:grid-cols-2">
          {data?.items.map((t) => (
          <div key={t.id} className="card p-5">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="font-medium">{t.name}</h3>
              <div className="flex gap-1">
                {t.is_default && <span className="badge bg-emerald-100 text-emerald-700">по умолчанию</span>}
                {t.uppercase_title && <span className="badge bg-blue-100 text-blue-700">CAPS</span>}
                {!t.is_active && <span className="badge bg-gray-100 text-gray-600">выключен</span>}
              </div>
            </div>
            <div className="space-y-1 whitespace-pre-wrap rounded-md bg-muted p-3 text-xs font-mono">
              <div>{t.header}</div>
              <div className="text-muted-foreground">{t.body}</div>
              <div>{t.footer}</div>
            </div>
            <div className="mt-3 flex gap-1.5">
              <button className="btn-icon" title="Редактировать" onClick={() => openEdit(t)}>
                <Pencil className="h-4 w-4" />
              </button>
              <button className="btn-icon" title="Создать копию" onClick={() => duplicate(t.id)}>
                <Copy className="h-4 w-4" />
              </button>
              <button className="btn-icon-danger" title="Удалить" onClick={() => remove(t.id)}>
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
        {data && data.items.length === 0 && <p className="text-muted-foreground">Шаблонов нет. Создайте первый.</p>}
        </div>
      )}

      {activeTab === "moderation" && (
        <div className="max-w-3xl">
          <div className="card">
            <div className="border-b border-border px-5 py-3 font-medium">Шаблон карточки модерации</div>
            <div className="space-y-4 p-5">
              <div className="rounded-md bg-blue-50 p-3 text-xs text-blue-900 dark:bg-blue-950/40 dark:text-blue-200">
                <div className="mb-2 font-semibold">Плейсхолдеры:</div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
                  {[
                    ["{post}", "Текст новости"],
                    ["{title}", "Заголовок"],
                    ["{id}", "ID новости"],
                    ["{place}", "Место (город + регион)"],
                    ["{city}", "Название города"],
                    ["{score}", "Релевантность (0–1)"],
                    ["{source}", "Название источника"],
                    ["{source_time}", "Время источника"],
                    ["{processed_at}", "Время обработки"],
                    ["{moderator}", "Кто модерирует"],
                    ["{reply_to}", "Reply to ID"],
                    ["{status}", "Статус новости"],
                    ["{url}", "Ссылка на оригинал"],
                  ].map(([tag, desc]) => (
                    <div key={tag}>
                      <span className="font-mono font-semibold">{tag}</span> — {desc}
                    </div>
                  ))}
                </div>
                <div className="mt-2 text-muted-foreground">
                  Пусто — используется встроенный вид карточки.
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium">Шаблон</label>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Telegram HTML. Пусто — встроенный формат карточки.
                </p>
                <textarea
                  className="input mt-1 min-h-[280px] w-full font-mono text-xs"
                  value={modTemplate}
                  onChange={(e) => setModTemplate(e.target.value)}
                  placeholder={"<b>{title}</b>\n\n{post}\n\n🏙 {city} · ⚡ {score}\n🔗 {url}"}
                />
              </div>
              <div className="flex justify-end border-t border-border pt-4">
                <button className="btn-primary" disabled={modSaving} onClick={saveModTemplate}>
                  {modSaving ? "Сохранение…" : "Сохранить"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "Редактировать шаблон" : "Новый шаблон"} wide>
        {form && (
          <div className="space-y-4">
            {error && <p className="rounded-md bg-red-50 p-2 text-sm text-red-600 dark:bg-red-950/40">{error}</p>}

            <div className="rounded-md bg-blue-50 p-3 text-xs text-blue-900 dark:bg-blue-950/40 dark:text-blue-200">
              <div className="mb-1 font-semibold">Доступные теги (плейсхолдеры):</div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
                {TAGS.map((t) => (
                  <div key={t.tag}><span className="font-mono font-semibold">{t.tag}</span> — {t.desc}</div>
                ))}
              </div>
              <div className="mt-2 font-semibold">HTML-теги Telegram:</div>
              <div className="font-mono">{HTML_TAGS}</div>
              <div className="mt-2">Свои теги можно добавить ниже — они станут доступны как <span className="font-mono">{"{имя}"}</span>.</div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Название"><input className="input" value={form.name ?? ""} onChange={(e) => upd({ name: e.target.value })} /></Field>
              <Field label="Формат">
                <Select value={form.format ?? "telegram_html"} onChange={(v) => upd({ format: v })}>
                  <option value="telegram_html">Telegram HTML</option>
                  <option value="html">HTML</option>
                  <option value="markdown">Markdown</option>
                </Select>
              </Field>
            </div>

            <Field label="Заголовок (header)" hint="Верхняя строка. Напр. {emoji} <b>{title}</b>">
              <textarea className="input input-compact font-mono" value={form.header ?? ""} onChange={(e) => upd({ header: e.target.value })} />
            </Field>
            <Field label="Тело (body)">
              <textarea className="input min-h-[240px] font-mono" value={form.body ?? ""} onChange={(e) => upd({ body: e.target.value })} />
            </Field>
            <Field label="Футер (footer)">
              <textarea className="input input-compact font-mono" value={form.footer ?? ""} onChange={(e) => upd({ footer: e.target.value })} />
            </Field>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Разделитель" hint="Между header/body/footer">
                <input className="input font-mono" value={form.separator ?? ""} onChange={(e) => upd({ separator: e.target.value })} />
              </Field>
              <Field
                label="Ссылка подписки {link}"
                hint="Обычно не нужна: {link} сам берёт канал города. Заполните, чтобы жёстко задать ссылку."
              >
                <input className="input" value={form.subscribe_link ?? ""} onChange={(e) => upd({ subscribe_link: e.target.value })} />
              </Field>
            </div>

            <Field label="ID премиум-эмодзи {custom_emoji}" hint="Число из документа Telegram; выводится тегом {custom_emoji}. Нужен Telegram Premium у владельца бота.">
              <input className="input" value={form.custom_emoji_id ?? ""} onChange={(e) => upd({ custom_emoji_id: e.target.value })} />
            </Field>



            {/* Custom variables (own tags) */}
            <div className="rounded-lg border border-border p-4">
              <div className="mb-1 text-sm font-medium">Свои теги</div>
              <p className="mb-3 text-xs text-muted-foreground">
                Создайте тег с любым значением — в шаблоне он доступен как
                <span className="mx-1 font-mono">{"{имя}"}</span>. Значением может быть
                текст или эмодзи (выберите ниже).
              </p>

              {Object.keys(form.variables ?? {}).length > 0 && (
                <div className="mb-3 space-y-1.5">
                  {Object.entries(form.variables ?? {}).map(([k, v]) =>
                    editingVar === k ? (
                      <div
                        key={k}
                        className="flex flex-wrap items-center gap-2 rounded-md border border-primary/60 px-2.5 py-1.5 text-sm"
                      >
                        <input
                          className="input h-8 w-[150px] font-mono"
                          value={editKey}
                          onChange={(e) => setEditKey(e.target.value)}
                        />
                        <span className="text-muted-foreground">=</span>
                        <input
                          className="input h-8 flex-1"
                          value={editVal}
                          onChange={(e) => setEditVal(e.target.value)}
                        />
                        <EmojiPickerButton
                          onPick={(em) => setEditVal((x) => x + em)}
                          className="h-8 w-8"
                        />
                        <button
                          type="button"
                          className="btn-icon-success h-8 w-8"
                          title="Сохранить тег"
                          onClick={commitEditVar}
                        >
                          <Check className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          className="btn-icon h-8 w-8"
                          title="Отменить"
                          onClick={() => setEditingVar(null)}
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ) : (
                      <div
                        key={k}
                        className="flex items-center gap-2 rounded-md border border-border/70 px-2.5 py-1.5 text-sm"
                      >
                        <span className="font-mono text-primary">{`{${k}}`}</span>
                        <span className="text-muted-foreground">=</span>
                        <span className="flex-1 truncate">{v}</span>
                        <button
                          type="button"
                          className="btn-icon h-6 w-6"
                          title="Редактировать тег"
                          onClick={() => startEditVar(k, v)}
                        >
                          <Pencil className="h-3 w-3" />
                        </button>
                        <button
                          type="button"
                          className="btn-icon-danger h-6 w-6"
                          title="Удалить тег"
                          onClick={() => removeVar(k)}
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    )
                  )}
                </div>
              )}

              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Имя тега" hint="Латиницей, без пробелов">
                  <input
                    className="input"
                    placeholder="subscribe_icon"
                    value={varKey}
                    onChange={(e) => setVarKey(e.target.value)}
                  />
                </Field>
                <Field label="Значение" hint="Текст и/или эмодзи (кнопка добавляет к тексту)">
                  <div className="flex gap-1">
                    <input
                      className="input"
                      placeholder="текст или эмодзи"
                      value={varVal}
                      onChange={(e) => setVarVal(e.target.value)}
                    />
                    {/* Appends to the value instead of replacing it. */}
                    <EmojiPickerButton onPick={(em) => setVarVal((v) => v + em)} />
                  </div>
                </Field>
              </div>

              <button type="button" className="btn-outline mt-3" onClick={addVar}>
                <Plus className="h-4 w-4" /> Добавить тег
              </button>
            </div>

            <div className="flex flex-wrap gap-x-6 gap-y-3">
              <Checkbox checked={!!form.uppercase_title} onChange={(v) => upd({ uppercase_title: v })} label="Заголовок ЗАГЛАВНЫМИ" />
              <Checkbox checked={!!form.is_default} onChange={(v) => upd({ is_default: v })} label="По умолчанию" />
              <Checkbox checked={form.is_active ?? true} onChange={(v) => upd({ is_active: v })} label="Активен" />
              <Checkbox checked={form.disable_web_preview ?? true} onChange={(v) => upd({ disable_web_preview: v })} label="Без превью ссылок" />
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

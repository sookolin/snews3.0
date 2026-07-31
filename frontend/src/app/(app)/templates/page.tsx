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

const MOD_STATES = [
  { key: "pending",   label: "⏳ Ожидает модерации", color: "text-amber-600 dark:text-amber-400" },
  { key: "approved",  label: "✅ Одобрено",           color: "text-emerald-600 dark:text-emerald-400" },
  { key: "published", label: "📢 Опубликовано",        color: "text-blue-600 dark:text-blue-400" },
  { key: "withdrawn", label: "↩️ Снято",              color: "text-orange-600 dark:text-orange-400" },
  { key: "rejected",  label: "❌ Отклонено",           color: "text-red-600 dark:text-red-400" },
  { key: "failed",    label: "💥 Ошибка",              color: "text-gray-500 dark:text-gray-400" },
] as const;

type ModState = (typeof MOD_STATES)[number]["key"];

const EMPTY_MOD: Record<ModState, string> = {
  pending: "", approved: "", published: "", withdrawn: "", rejected: "", failed: "",
};

const MOD_KEYBOARD_PREVIEW: Record<string, string[][]> = {
  pending: [
    ["✅ Одобрить", "❌ Отклонить"],
    ["✏️ Редактировать", "🗑 Удалить"],
    ["⚡️ Опубликовать сразу", "🌐 Во все каналы"],
  ],
  approved: [
    ["⚡️ Опубликовать сразу", "❌ Отклонить"],
    ["✏️ Редактировать", "🗑 Удалить"],
  ],
  published: [
    ["✏️ Редактировать"],
    ["↩️ Снять с публикации"],
    ["🗑 Удалить полностью"],
  ],
  withdrawn: [
    ["✏️ Редактировать"],
    ["📤 Опубликовать снова", "🌐 Во все каналы"],
    ["🗑 Удалить полностью"],
  ],
  rejected: [
    ["✅ Одобрить", "✏️ Редактировать"],
    ["🗑 Удалить полностью"],
  ],
  failed: [
    ["✅ Одобрить", "❌ Отклонить"],
    ["✏️ Редактировать", "🗑 Удалить"],
    ["⚡️ Опубликовать сразу", "🌐 Во все каналы"],
  ],
};

const MOD_PLACEHOLDERS = [
  ["{post}", "Текст новости (готовый)"],
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
];

/** ---- Tags tab ---- */
interface GlobalTag {
  key: string;
  value: string;
  /** Optional: Telegram Premium custom emoji document ID */
  custom_emoji_id?: string;
}

function TagsTab() {
  const toast = useToast();
  const { data: settings, mutate } = useSWR<Record<string, unknown>>("/settings", fetcher);

  // Global tags stored as a JSON array in settings["templates.global_tags"]
  const [tags, setTags] = useState<GlobalTag[]>([]);
  const [saving, setSaving] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newVal, setNewVal] = useState("");
  const [newEmojiId, setNewEmojiId] = useState("");
  const [editingIdx, setEditingIdx] = useState<number | null>(null);
  const [editKey, setEditKey] = useState("");
  const [editVal, setEditVal] = useState("");
  const [editEmojiId, setEditEmojiId] = useState("");

  useEffect(() => {
    if (!settings) return;
    const raw = settings["templates.global_tags"];
    if (typeof raw === "string" && raw.trim().startsWith("[")) {
      try { setTags(JSON.parse(raw)); return; } catch {}
    }
    setTags([]);
  }, [settings]);

  const saveTags = async (next: GlobalTag[]) => {
    setSaving(true);
    try {
      await api(`/settings/${encodeURIComponent("templates.global_tags")}`, {
        method: "PUT",
        body: JSON.stringify({ value: JSON.stringify(next) }),
      });
      setTags(next);
      await mutate();
      toast.success("Теги сохранены");
    } catch (e) {
      toast.error((e as Error).message);
    } finally { setSaving(false); }
  };

  const addTag = () => {
    if (!newKey.trim()) return;
    const tag: GlobalTag = { key: newKey.trim(), value: newVal };
    if (newEmojiId.trim()) tag.custom_emoji_id = newEmojiId.trim();
    saveTags([...tags, tag]);
    setNewKey(""); setNewVal(""); setNewEmojiId(""); setAdding(false);
  };

  const commitEdit = (idx: number) => {
    if (!editKey.trim()) return;
    const next = tags.map((t, i) => {
      if (i !== idx) return t;
      const updated: GlobalTag = { key: editKey.trim(), value: editVal };
      if (editEmojiId.trim()) updated.custom_emoji_id = editEmojiId.trim();
      return updated;
    });
    saveTags(next);
    setEditingIdx(null);
  };

  const removeTag = (idx: number) => saveTags(tags.filter((_, i) => i !== idx));

  return (
    <div className="max-w-3xl space-y-5">
      <div className="rounded-md bg-blue-50 p-3 text-xs text-blue-900 dark:bg-blue-950/40 dark:text-blue-200">
        <div className="mb-1 font-semibold">Глобальные теги</div>
        <p className="mb-2">
          Теги доступны во всех шаблонах как <span className="font-mono">{"{имя}"}</span>.
          Поддерживается тип <span className="font-mono">custom_emoji_id</span> — премиум-эмодзи Telegram.
        </p>
        <div className="text-[11px] opacity-90">
          <strong>Как получить Custom Emoji ID:</strong><br />
          1. Найдите нужный эмодзи в Telegram Premium или стикерпаке<br />
          2. Отправьте его боту <a href="https://t.me/usinfobot" target="_blank" rel="noopener" className="underline">@usinfobot</a><br />
          3. Скопируйте <span className="font-mono">Document ID</span> (длинное число)<br />
          4. Вставьте в поле ниже — при рендере шаблона будет использован premium-эмодзи вместо текстового значения
        </div>
      </div>

      <div className="card overflow-hidden">
        {tags.length === 0 && !adding && (
          <div className="px-5 py-8 text-center text-sm text-muted-foreground">Глобальных тегов нет.</div>
        )}

        {tags.map((t, idx) => (
          editingIdx === idx ? (
            <div key={idx} className="border-b border-border/60 px-5 py-3 space-y-2">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="mb-1 text-xs font-medium">Имя тега</div>
                  <input className="input" value={editKey} onChange={(e) => setEditKey(e.target.value)} />
                </div>
                <div>
                  <div className="mb-1 text-xs font-medium">Значение</div>
                  <div className="flex gap-1">
                    <input className="input flex-1" value={editVal} onChange={(e) => setEditVal(e.target.value)} />
                    <EmojiPickerButton onPick={(em) => setEditVal((v) => v + em)} />
                  </div>
                </div>
              </div>
              <div>
                <div className="mb-1 text-xs font-medium text-muted-foreground">
                  TG Premium Custom Emoji ID <span className="font-normal">(опционально)</span>
                </div>
                <input
                  className="input font-mono"
                  placeholder="5123456789012345678"
                  value={editEmojiId}
                  onChange={(e) => setEditEmojiId(e.target.value.replace(/\D/g, ""))}
                />
                <div className="mt-1 text-[11px] text-muted-foreground">
                  💡 Как получить ID: отправьте стикер боту <a href="https://t.me/usinfobot" target="_blank" rel="noopener" className="text-blue-600 hover:underline dark:text-blue-400">@usinfobot</a>, скопируйте Document ID
                </div>
              </div>
              <div className="flex gap-2">
                <button className="btn-primary text-sm" disabled={saving} onClick={() => commitEdit(idx)}>Сохранить</button>
                <button className="btn-outline text-sm" onClick={() => setEditingIdx(null)}>Отмена</button>
              </div>
            </div>
          ) : (
            <div key={idx} className="flex items-center gap-3 border-b border-border/60 px-5 py-3 last:border-0">
              <div className="flex-1 min-w-0">
                <span className="font-mono font-semibold text-primary">{`{${t.key}}`}</span>
                <span className="mx-2 text-muted-foreground">=</span>
                <span className="text-sm">{t.value || <em className="text-muted-foreground">пусто</em>}</span>
                {t.custom_emoji_id && (
                  <span className="ml-2 rounded bg-violet-50 px-1.5 py-0.5 font-mono text-[11px] text-violet-700 dark:bg-violet-950/40 dark:text-violet-300" title={`Telegram Premium Emoji ID: ${t.custom_emoji_id}`}>
                    🌟 emoji:{t.custom_emoji_id.slice(0, 8)}...
                  </span>
                )}
              </div>
              <button
                className="btn-icon h-7 w-7"
                title="Редактировать"
                onClick={() => { setEditingIdx(idx); setEditKey(t.key); setEditVal(t.value); setEditEmojiId(t.custom_emoji_id ?? ""); }}
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
              <button className="btn-icon-danger h-7 w-7" title="Удалить" onClick={() => removeTag(idx)}>
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          )
        ))}

        {adding && (
          <div className="border-t border-border/60 px-5 py-3 space-y-2">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="mb-1 text-xs font-medium">Имя тега</div>
                <input className="input" placeholder="subscribe_icon" value={newKey} onChange={(e) => setNewKey(e.target.value)} />
              </div>
              <div>
                <div className="mb-1 text-xs font-medium">Значение</div>
                <div className="flex gap-1">
                  <input className="input flex-1" placeholder="текст или эмодзи" value={newVal} onChange={(e) => setNewVal(e.target.value)} />
                  <EmojiPickerButton onPick={(em) => setNewVal((v) => v + em)} />
                </div>
              </div>
            </div>
            <div>
              <div className="mb-1 text-xs font-medium text-muted-foreground">
                TG Premium Custom Emoji ID <span className="font-normal">(опционально — заменяет значение при рендере)</span>
              </div>
              <input
                className="input font-mono"
                placeholder="5123456789012345678"
                value={newEmojiId}
                onChange={(e) => setNewEmojiId(e.target.value.replace(/\D/g, ""))}
              />
              <div className="mt-1 text-[11px] text-muted-foreground">
                💡 Как получить ID: отправьте стикер боту <a href="https://t.me/usinfobot" target="_blank" rel="noopener" className="text-blue-600 hover:underline dark:text-blue-400">@usinfobot</a>, скопируйте Document ID
              </div>
            </div>
            <div className="flex gap-2">
              <button className="btn-primary text-sm" disabled={saving || !newKey.trim()} onClick={addTag}>
                <Plus className="h-4 w-4" /> Добавить
              </button>
              <button className="btn-outline text-sm" onClick={() => { setAdding(false); setNewKey(""); setNewVal(""); setNewEmojiId(""); }}>Отмена</button>
            </div>
          </div>
        )}
      </div>

      {!adding && (
        <button className="btn-outline" onClick={() => setAdding(true)}>
          <Plus className="h-4 w-4" /> Новый тег
        </button>
      )}
    </div>
  );
}

export default function TemplatesPage() {
  const { data, mutate } = useSWR<Page<Template>>("/templates?size=100", fetcher);
  const { data: settingsData } = useSWR<Record<string, unknown>>("/settings", fetcher);
  const [activeTab, setActiveTab] = useState<"templates" | "moderation" | "tags">("templates");
  const [form, setForm] = useState<Partial<Template> | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [varKey, setVarKey] = useState("");
  const [varVal, setVarVal] = useState("");
  // Custom tag currently being edited (its original key), plus draft values.
  const [editingVar, setEditingVar] = useState<string | null>(null);
  const [editKey, setEditKey] = useState("");
  const [editVal, setEditVal] = useState("");
  // Moderation card templates (one per status)
  const [modTemplates, setModTemplates] = useState<Record<ModState, string>>({ ...EMPTY_MOD });
  const [modSaving, setModSaving] = useState(false);
  const toast = useToast();

  // Init moderation templates from settings
  useEffect(() => {
    if (!settingsData) return;
    const raw = settingsData["moderation.card_template"];
    if (typeof raw === "string" && raw.trim().startsWith("{")) {
      try {
        setModTemplates({ ...EMPTY_MOD, ...JSON.parse(raw) });
        return;
      } catch {}
    }
    // Legacy single-string value — leave all states empty
    setModTemplates({ ...EMPTY_MOD });
  }, [settingsData]);

  const openNew = () => { setForm({ ...EMPTY }); setPreview(null); setError(null); setEditingVar(null); };
  const openEdit = (t: Template) => { setForm({ ...t, variables: t.variables ?? {} }); setPreview(null); setError(null); setEditingVar(null); };
  const upd = (patch: Partial<Template>) => setForm((f) => ({ ...f, ...patch }));

  const save = async () => {
    if (!form) return;
    setError(null);
    // Send only the editable fields; id/created_at must never go in the body.
    const payload = {
      name: form.name ?? "",
      format: form.format ?? "telegram_html",
      header: form.header ?? "",
      body: form.body ?? "",
      footer: form.footer ?? "",
      separator: form.separator ?? "\n\n",
      subscribe_link: form.subscribe_link || null,
      variables: form.variables ?? {},
      is_default: !!form.is_default,
      is_active: form.is_active ?? true,
      disable_web_preview: form.disable_web_preview ?? true,
      uppercase_title: !!form.uppercase_title,
    };
    try {
      if (form.id) await api(`/templates/${form.id}`, { method: "PATCH", body: JSON.stringify(payload) });
      else await api("/templates", { method: "POST", body: JSON.stringify(payload) });
      setForm(null);
      mutate();
      toast.success(form.id ? "Шаблон сохранён" : "Шаблон создан");
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
        body: JSON.stringify({ value: JSON.stringify(modTemplates) }),
      });
      toast.success("Шаблоны карточки сохранены");
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
        <button className={TAB_CLASSES(activeTab === "tags")} onClick={() => setActiveTab("tags")}>
          Теги
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
        <div className="space-y-5">
          {/* Placeholder reference */}
          <div className="rounded-md bg-blue-50 p-3 text-xs text-blue-900 dark:bg-blue-950/40 dark:text-blue-200">
            <div className="mb-2 font-semibold">Плейсхолдеры (одинаковы для всех состояний):</div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
              {MOD_PLACEHOLDERS.map(([tag, desc]) => (
                <div key={tag}><span className="font-mono font-semibold">{tag}</span> — {desc}</div>
              ))}
            </div>
            <div className="mt-2 text-muted-foreground">Пусто — встроенный формат карточки для этого состояния.</div>
          </div>

          {/* Cards in 2x2 grid */}
          <div className="grid gap-4 md:grid-cols-2">
            {MOD_STATES.map(({ key, label, color }) => (
              <div key={key} className="card">
                <div className="flex items-center gap-2 border-b border-border px-5 py-3">
                  <span className={`text-sm font-semibold ${color}`}>{label}</span>
                </div>
                <div className="p-5 space-y-3">
                  <div className="flex items-start gap-1">
                    <textarea
                      id={`mod-tpl-${key}`}
                      className="input min-h-[140px] flex-1 font-mono text-xs"
                      placeholder={`Шаблон для статуса «${label}». Пусто — встроенный вид.`}
                      value={modTemplates[key]}
                      onChange={(e) =>
                        setModTemplates((t) => ({ ...t, [key]: e.target.value }))
                      }
                    />
                    <EmojiPickerButton
                      onPick={(em) => {
                        const el = document.getElementById(`mod-tpl-${key}`) as HTMLTextAreaElement | null;
                        setModTemplates((t) => {
                          const cur = t[key] ?? "";
                          if (!el) return { ...t, [key]: cur + em };
                          const s = el.selectionStart, e2 = el.selectionEnd;
                          const next = cur.slice(0, s) + em + cur.slice(e2);
                          setTimeout(() => { el.selectionStart = el.selectionEnd = s + em.length; el.focus(); }, 0);
                          return { ...t, [key]: next };
                        });
                      }}
                    />
                  </div>

                  {/* Button keyboard preview */}
                  <div>
                    <div className="mb-1 text-xs text-muted-foreground font-medium">Кнопки модерации для этого состояния:</div>
                    <div className="space-y-1">
                      {(MOD_KEYBOARD_PREVIEW[key] ?? []).map((row, ri) => (
                        <div key={ri} className="flex flex-wrap gap-1">
                          {row.map((btn) => (
                            <span
                              key={btn}
                              className="inline-block rounded border border-border bg-muted px-2.5 py-1 text-xs"
                            >
                              {btn}
                            </span>
                          ))}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="flex justify-end">
            <button className="btn-primary" disabled={modSaving} onClick={saveModTemplate}>
              {modSaving ? "Сохранение…" : "Сохранить все шаблоны"}
            </button>
          </div>
        </div>
      )}

      {activeTab === "tags" && (
        <TagsTab />
      )}

      <Modal
        open={!!form}
        onClose={() => { setForm(null); setPreview(null); setError(null); }}
        title={form?.id ? "Редактировать шаблон" : "Новый шаблон"}
        size="xl"
      >
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
              <div className="flex items-start gap-1">
                <textarea
                  id="tpl-header"
                  className="input input-compact flex-1 font-mono"
                  value={form.header ?? ""}
                  onChange={(e) => upd({ header: e.target.value })}
                />
                <EmojiPickerButton
                  onPick={(em) => {
                    const el = document.getElementById("tpl-header") as HTMLTextAreaElement | null;
                    if (!el) { upd({ header: (form.header ?? "") + em }); return; }
                    const s = el.selectionStart, e2 = el.selectionEnd;
                    const next = (form.header ?? "").slice(0, s) + em + (form.header ?? "").slice(e2);
                    upd({ header: next });
                    setTimeout(() => { el.selectionStart = el.selectionEnd = s + em.length; el.focus(); }, 0);
                  }}
                />
              </div>
            </Field>
            <Field label="Тело (body)">
              <div className="flex items-start gap-1">
                <textarea
                  id="tpl-body"
                  className="input min-h-[240px] flex-1 font-mono"
                  value={form.body ?? ""}
                  onChange={(e) => upd({ body: e.target.value })}
                />
                <EmojiPickerButton
                  onPick={(em) => {
                    const el = document.getElementById("tpl-body") as HTMLTextAreaElement | null;
                    if (!el) { upd({ body: (form.body ?? "") + em }); return; }
                    const s = el.selectionStart, e2 = el.selectionEnd;
                    const next = (form.body ?? "").slice(0, s) + em + (form.body ?? "").slice(e2);
                    upd({ body: next });
                    setTimeout(() => { el.selectionStart = el.selectionEnd = s + em.length; el.focus(); }, 0);
                  }}
                />
              </div>
            </Field>
            <Field label="Футер (footer)">
              <div className="flex items-start gap-1">
                <textarea
                  id="tpl-footer"
                  className="input input-compact flex-1 font-mono"
                  value={form.footer ?? ""}
                  onChange={(e) => upd({ footer: e.target.value })}
                />
                <EmojiPickerButton
                  onPick={(em) => {
                    const el = document.getElementById("tpl-footer") as HTMLTextAreaElement | null;
                    if (!el) { upd({ footer: (form.footer ?? "") + em }); return; }
                    const s = el.selectionStart, e2 = el.selectionEnd;
                    const next = (form.footer ?? "").slice(0, s) + em + (form.footer ?? "").slice(e2);
                    upd({ footer: next });
                    setTimeout(() => { el.selectionStart = el.selectionEnd = s + em.length; el.focus(); }, 0);
                  }}
                />
              </div>
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

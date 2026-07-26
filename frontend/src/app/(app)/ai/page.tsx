"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { Page } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Modal, Field } from "@/components/Modal";

interface AIProfile {
  id: number;
  name: string;
  is_default: boolean;
  is_active: boolean;
  provider: string;
  model?: string | null;
  base_url?: string | null;
  embedding_model?: string | null;
  has_api_key?: boolean;
  api_key?: string;
  system_prompt: string;
  instructions?: string | null;
  tone?: string | null;
  style?: string | null;
  temperature: number;
  max_tokens: number;
  generate_embeddings: boolean;
}

const DEFAULT_PROMPT =
  'Ты — профессиональный редактор новостей. Перепиши текст, не искажая факты. ' +
  'Исправь ошибки, структурируй, сделай красивый заголовок. ' +
  'Верни JSON: {"title": "...", "text": "..."}.';

const EMPTY: Partial<AIProfile> = {
  name: "", provider: "anthropic", system_prompt: DEFAULT_PROMPT,
  temperature: 0.4, max_tokens: 2048, generate_embeddings: true,
  is_default: false, is_active: true,
};

const PROVIDER_HINTS: Record<string, { model: string; base?: string; keyUrl: string }> = {
  anthropic: { model: "claude-3-5-sonnet-latest", keyUrl: "console.anthropic.com" },
  openai: { model: "gpt-4o-mini", base: "https://api.openai.com/v1", keyUrl: "platform.openai.com" },
  gemini: { model: "gemini-1.5-flash", keyUrl: "aistudio.google.com" },
  local: { model: "llama3.1", base: "http://host.docker.internal:11434/v1", keyUrl: "локальный сервер" },
};

export default function AIPage() {
  const { data, mutate } = useSWR<Page<AIProfile>>("/ai?size=100", fetcher);
  const { data: providers } = useSWR<string[]>("/ai/providers", fetcher);
  const [form, setForm] = useState<Partial<AIProfile> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState("В горсовете обсудили ремонт дорог в центре города.");
  const [testProfile, setTestProfile] = useState<number | "">("");
  const [result, setResult] = useState<{ title: string; text: string; provider: string } | null>(null);
  const [testing, setTesting] = useState(false);

  const openNew = () => { setForm({ ...EMPTY }); setError(null); };
  const openEdit = (p: AIProfile) => { setForm({ ...p, api_key: "" }); setError(null); };
  const upd = (patch: Partial<AIProfile>) => setForm((f) => ({ ...f, ...patch }));

  const save = async () => {
    if (!form) return;
    setError(null);
    try {
      // Do not send empty api_key on edit (keeps stored secret).
      const body: Partial<AIProfile> = { ...form };
      if (form.id && !form.api_key) delete body.api_key;
      if (form.id) await api(`/ai/${form.id}`, { method: "PATCH", body: JSON.stringify(body) });
      else await api("/ai", { method: "POST", body: JSON.stringify(body) });
      setForm(null);
      mutate();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const remove = async (id: number) => {
    if (!confirm("Удалить профиль?")) return;
    await api(`/ai/${id}`, { method: "DELETE" });
    mutate();
  };

  const test = async () => {
    setTesting(true); setResult(null);
    try {
      setResult(await api("/ai/test", {
        method: "POST",
        body: JSON.stringify({ text, profile_id: testProfile || null }),
      }));
    } catch (e) {
      setResult({ title: "Ошибка", text: (e as Error).message, provider: "" });
    } finally {
      setTesting(false);
    }
  };

  const hint = form?.provider ? PROVIDER_HINTS[form.provider] : undefined;

  return (
    <div>
      <PageHeader
        title="AI-обработка"
        action={<button className="btn-primary" onClick={openNew}>Создать профиль</button>}
      />

      <div className="mb-5 space-y-3 rounded-lg border border-border bg-card p-5 text-sm">
        <h3 className="text-base font-semibold">Как работает AI-обработка</h3>
        <p className="text-muted-foreground">
          Каждая найденная (или предложенная) новость перед модерацией автоматически
          проходит через <b>профиль AI</b>: модель переписывает текст, исправляет ошибки,
          структурирует, формирует заголовок и HTML-разметку для Telegram. Профиль,
          отмеченный <b>«по умолчанию»</b>, применяется ко всем новостям. Можно создать
          несколько профилей под разные задачи и переключать активный.
        </p>
        <ul className="ml-4 list-disc space-y-1 text-muted-foreground">
          <li><b>Провайдер</b> — движок: Claude (Anthropic), OpenAI, Google Gemini или локальная LLM (OpenAI-совместимый эндпоинт: Ollama, vLLM, LM Studio).</li>
          <li><b>API-ключ</b> — задаётся прямо здесь (в БД), файл .env больше не нужен. Ключ хранится скрыто; при редактировании оставьте поле пустым, чтобы сохранить текущий.</li>
          <li><b>Base URL</b> — свой эндпоинт (прокси, локальный сервер). Пусто = стандартный.</li>
          <li><b>Модель</b> — например {`"claude-3-5-sonnet-latest"`}, {`"gpt-4o-mini"`}, {`"gemini-1.5-flash"`}, {`"llama3.1"`}.</li>
          <li><b>Температура</b> — 0 = строго по фактам, 2 = креативно. Для новостей 0.2–0.5.</li>
          <li><b>Макс. токенов</b> — предел длины ответа модели.</li>
          <li><b>Эмбеддинги</b> — генерировать векторы для семантического поиска дубликатов.</li>
          <li><b>Тон / Стиль</b> — дополнительные указания (нейтральный, официальный, краткий…).</li>
        </ul>
        <p className="text-muted-foreground">
          Проверить настройку можно в блоке <b>«Тест обработки»</b> справа: выберите профиль,
          вставьте текст и нажмите «Запустить» — увидите результат переписывания.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          {data?.items.map((p) => (
            <div key={p.id} className="card p-4">
              <div className="flex items-center justify-between">
                <span className="font-medium">{p.name}</span>
                <div className="flex gap-1">
                  {p.is_default && <span className="badge bg-emerald-100 text-emerald-700">default</span>}
                  {!p.is_active && <span className="badge bg-gray-100 text-gray-600">выключен</span>}
                  {p.has_api_key ? (
                    <span className="badge bg-green-100 text-green-700">ключ задан</span>
                  ) : (
                    <span className="badge bg-amber-100 text-amber-800">нет ключа</span>
                  )}
                </div>
              </div>
              <div className="mt-1 text-sm text-muted-foreground">
                {p.provider} · {p.model || "модель по умолчанию"} · t={p.temperature} · {p.max_tokens} tok
              </div>
              <div className="mt-3 flex gap-2">
                <button className="btn-outline py-1" onClick={() => openEdit(p)}>Редактировать</button>
                <button className="btn-danger py-1" onClick={() => remove(p.id)}>Удалить</button>
              </div>
            </div>
          ))}
          {data && data.items.length === 0 && (
            <p className="text-muted-foreground">Профилей нет. Создайте первый.</p>
          )}
        </div>

        <div className="card space-y-3 p-5">
          <h3 className="font-medium">Тест обработки</h3>
          <select className="input" value={testProfile} onChange={(e) => setTestProfile(e.target.value ? Number(e.target.value) : "")}>
            <option value="">Профиль по умолчанию</option>
            {data?.items.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <textarea className="input min-h-[120px]" value={text} onChange={(e) => setText(e.target.value)} />
          <button className="btn-primary" disabled={testing} onClick={test}>
            {testing ? "Обработка…" : "Запустить тест"}
          </button>
          {result && (
            <div className="rounded-md bg-muted p-3 text-sm">
              <div className="font-semibold">{result.title}</div>
              <div className="mt-1 whitespace-pre-wrap">{result.text}</div>
              {result.provider && <div className="mt-2 text-xs text-muted-foreground">Провайдер: {result.provider}</div>}
            </div>
          )}
        </div>
      </div>

      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "Редактировать профиль AI" : "Новый профиль AI"} wide>
        {form && (
          <div className="space-y-4">
            {error && <p className="rounded-md bg-red-50 p-2 text-sm text-red-600 dark:bg-red-950/40">{error}</p>}
            <div className="grid grid-cols-2 gap-4">
              <Field label="Название"><input className="input" value={form.name ?? ""} onChange={(e) => upd({ name: e.target.value })} /></Field>
              <Field label="Провайдер">
                <select className="input" value={form.provider} onChange={(e) => upd({ provider: e.target.value })}>
                  {(providers ?? ["anthropic", "openai", "gemini", "local"]).map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </Field>
            </div>
            <Field label="API-ключ" hint={form.id ? (form.has_api_key ? "Ключ уже задан. Оставьте пустым, чтобы не менять." : "Ключ ещё не задан.") : `Получить: ${hint?.keyUrl ?? ""}`}>
              <input className="input" type="password" placeholder={form.id && form.has_api_key ? "•••••••• (без изменений)" : "sk-..."} value={form.api_key ?? ""} onChange={(e) => upd({ api_key: e.target.value })} />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Модель" hint={hint ? `напр. ${hint.model}` : "напр. gpt-4o-mini"}>
                <input className="input" value={form.model ?? ""} onChange={(e) => upd({ model: e.target.value })} />
              </Field>
              <Field label="Base URL" hint={hint?.base ? `напр. ${hint.base}` : "пусто = стандартный"}>
                <input className="input" value={form.base_url ?? ""} onChange={(e) => upd({ base_url: e.target.value })} />
              </Field>
            </div>
            <Field label="Системный промпт" hint="Основная инструкция модели">
              <textarea className="input min-h-[120px]" value={form.system_prompt ?? ""} onChange={(e) => upd({ system_prompt: e.target.value })} />
            </Field>
            <Field label="Доп. инструкции" hint="Дополнения к промпту (опционально)">
              <textarea className="input" value={form.instructions ?? ""} onChange={(e) => upd({ instructions: e.target.value })} />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Тон" hint="напр. нейтральный, официальный"><input className="input" value={form.tone ?? ""} onChange={(e) => upd({ tone: e.target.value })} /></Field>
              <Field label="Стиль" hint="напр. краткий, подробный"><input className="input" value={form.style ?? ""} onChange={(e) => upd({ style: e.target.value })} /></Field>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <Field label={`Температура: ${form.temperature}`} hint="0 точно · 2 креативно">
                <input type="range" min={0} max={2} step={0.1} value={form.temperature ?? 0.4} onChange={(e) => upd({ temperature: Number(e.target.value) })} className="w-full" />
              </Field>
              <Field label="Макс. токенов">
                <input type="number" className="input" value={form.max_tokens ?? 2048} onChange={(e) => upd({ max_tokens: Number(e.target.value) })} />
              </Field>
              <Field label="Модель эмбеддингов" hint="опционально">
                <input className="input" value={form.embedding_model ?? ""} onChange={(e) => upd({ embedding_model: e.target.value })} />
              </Field>
            </div>
            <div className="flex flex-wrap gap-6">
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={!!form.generate_embeddings} onChange={(e) => upd({ generate_embeddings: e.target.checked })} /> Эмбеддинги (семантич. дедуп)
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={!!form.is_default} onChange={(e) => upd({ is_default: e.target.checked })} /> По умолчанию
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={form.is_active ?? true} onChange={(e) => upd({ is_active: e.target.checked })} /> Активен
              </label>
            </div>
            <div className="flex justify-end border-t border-border pt-4">
              <button className="btn-primary" onClick={save}>Сохранить</button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

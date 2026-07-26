"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";

// Human-readable labels/descriptions for known settings keys.
const META: Record<string, { label: string; hint: string; group: string }> = {
  "dedup.simhash_max_distance": {
    label: "SimHash: макс. расстояние",
    hint: "Порог близости для near-duplicate (меньше = строже). Обычно 3.",
    group: "Дедупликация",
  },
  "dedup.text_similarity_threshold": {
    label: "Порог схожести текста",
    hint: "Доля совпадения (0–1) для признания дубликатом по Левенштейну. Обычно 0.9.",
    group: "Дедупликация",
  },
  "dedup.embedding_threshold": {
    label: "Порог косинусной близости",
    hint: "Семантическое сходство эмбеддингов (0–1) для дубликата. Обычно 0.92.",
    group: "Дедупликация",
  },
  "dedup.lookback_days": {
    label: "Окно поиска дублей (дней)",
    hint: "За сколько последних дней искать дубликаты.",
    group: "Дедупликация",
  },
  "matching.min_score": {
    label: "Мин. релевантность города",
    hint: "Порог совпадения (0–1), ниже которого новость не привязывается к городу.",
    group: "Определение города",
  },
  "pipeline.auto_publish_on_approve": {
    label: "Автопубликация при одобрении",
    hint: "Публиковать сразу после нажатия «Одобрить».",
    group: "Пайплайн",
  },
  "pipeline.require_moderation": {
    label: "Требовать модерацию",
    hint: "Все новости проходят ручную модерацию перед публикацией.",
    group: "Пайплайн",
  },
  "notifications.email_enabled": {
    label: "Email-уведомления",
    hint: "Включить рассылку уведомлений на email.",
    group: "Уведомления",
  },
  "notifications.webhook_url": {
    label: "Webhook URL",
    hint: "URL для отправки событий (пусто — выключено).",
    group: "Уведомления",
  },
  "ui.default_language": {
    label: "Язык по умолчанию",
    hint: "Язык интерфейса и сообщений (ru/en).",
    group: "Интерфейс",
  },
  "site.favicon_url": {
    label: "Favicon",
    hint: "URL иконки сайта (favicon.ico или ссылка на изображение).",
    group: "Интерфейс",
  },
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [dirty, setDirty] = useState<Record<string, unknown>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedOk, setSavedOk] = useState(false);

  const load = async () => {
    try {
      const s = await api<Record<string, unknown>>("/settings");
      setSettings(s);
      setDirty(s);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  useEffect(() => { load(); }, []);

  const setValue = (key: string, value: unknown) => {
    setDirty((d) => ({ ...d, [key]: value }));
    setSavedOk(false);
  };

  const saveAll = async () => {
    setSaving(true);
    setError(null);
    try {
      const changed = Object.keys(dirty).filter((k) => dirty[k] !== settings[k]);
      for (const key of changed) {
        await api(`/settings/${encodeURIComponent(key)}`, {
          method: "PUT",
          body: JSON.stringify({ value: dirty[key] }),
        });
      }
      setSettings({ ...dirty });
      setSavedOk(true);
      setTimeout(() => setSavedOk(false), 2500);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = Object.keys(dirty).some((k) => dirty[k] !== settings[k]);

  // Group settings by their META group (fallback: "Прочее").
  const groups: Record<string, string[]> = {};
  for (const key of Object.keys(settings)) {
    const g = META[key]?.group ?? "Прочее";
    (groups[g] ??= []).push(key);
  }

  return (
    <div className="max-w-3xl">
      <PageHeader
        title="Настройки"
        action={
          <button className="btn-primary" disabled={saving || !hasChanges} onClick={saveAll}>
            {saving ? "Сохранение…" : "Сохранить"}
          </button>
        }
      />
      <p className="mb-5 text-sm text-muted-foreground">
        Параметры системы, редактируемые без изменения кода. Измените значения и нажмите
        «Сохранить».
      </p>
      {error && <p className="mb-4 text-red-600">{error}</p>}
      {savedOk && <p className="mb-4 rounded-md bg-green-50 p-2 text-sm text-green-700 dark:bg-green-950/40">Настройки сохранены</p>}

      <div className="space-y-6">
        {Object.entries(groups).map(([group, keys]) => (
          <div key={group} className="card">
            <div className="border-b border-border px-5 py-3 font-medium">{group}</div>
            <div className="divide-y divide-border">
              {keys.map((key) => {
                const meta = META[key];
                const value = dirty[key];
                const isBool = typeof settings[key] === "boolean";
                const isNum = typeof settings[key] === "number";
                return (
                  <div key={key} className="flex items-center gap-4 p-4">
                    <div className="flex-1">
                      <div className="text-sm font-medium">{meta?.label ?? key}</div>
                      <div className="text-xs text-muted-foreground">{meta?.hint ?? key}</div>
                    </div>
                    {isBool ? (
                      <input
                        type="checkbox"
                        checked={Boolean(value)}
                        onChange={(e) => setValue(key, e.target.checked)}
                        className="h-5 w-5"
                      />
                    ) : (
                      <input
                        className="input max-w-[220px]"
                        type={isNum ? "number" : "text"}
                        step="any"
                        value={value === null || value === undefined ? "" : String(value)}
                        onChange={(e) =>
                          setValue(key, isNum && e.target.value !== "" ? Number(e.target.value) : e.target.value)
                        }
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

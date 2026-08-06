"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Checkbox } from "@/components/Controls";
import { useToast } from "@/components/Toast";

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
  "dedup.title_similarity_threshold": {
    label: "Порог схожести заголовков",
    hint:
      "Ловит одну и ту же новость с разных источников: тексты отличаются, а заголовки близки. " +
      "Обычно 0.72; меньше — строже отсев дублей.",
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
  "pipeline.publish_interval_minutes": {
    label: "Интервал между публикациями (мин)",
    hint: "Если одобрить несколько новостей, они выйдут по очереди с этим интервалом. 0 — публиковать сразу.",
    group: "Пайплайн",
  },
  "pipeline.max_item_age_minutes": {
    label: "Максимальный возраст новости (мин)",
    hint: "Парсить только публикации свежее этого времени — режим реального времени. 0 — брать всё.",
    group: "Пайплайн",
  },
  "pipeline.keep_world_news": {
    label: "Собирать мировые новости",
    hint:
      "Новости, не относящиеся ни к одному городу из админки, попадают во вкладку «Мировые». " +
      "Выключено — такие новости отбрасываются.",
    group: "Пайплайн",
  },
  "notifications.email_enabled": {
    label: "Email-уведомления",
    hint: "Включить рассылку. Письма уходят на адрес из поля «Email получателя» ниже.",
    group: "Уведомления",
  },
  "notifications.email_to": {
    label: "Email получателя",
    hint: "Именно на этот адрес приходит рассылка. Пусто — письма не отправляются.",
    group: "Уведомления",
  },
  "notifications.smtp_host": {
    label: "SMTP-сервер",
    hint: "Например smtp.yandex.ru. Без него рассылка не работает.",
    group: "Уведомления",
  },
  "notifications.smtp_port": {
    label: "SMTP-порт",
    hint: "Обычно 587 (STARTTLS) или 465.",
    group: "Уведомления",
  },
  "notifications.smtp_user": {
    label: "SMTP-логин",
    hint: "Учётная запись для отправки писем.",
    group: "Уведомления",
  },
  "notifications.smtp_password": {
    label: "SMTP-пароль",
    hint: "Пароль приложения почтового сервиса.",
    group: "Уведомления",
  },
  "notifications.smtp_from": {
    label: "Адрес отправителя",
    hint: "Что показывается в поле «От». Пусто — берётся SMTP-логин.",
    group: "Уведомления",
  },
  "notifications.webhook_url": {
    label: "Webhook URL",
    hint: "URL для отправки событий (пусто — выключено).",
    group: "Уведомления",
  },
  "ui.timezone_offset_hours": {
    label: "Часовой пояс (смещение от UTC)",
    hint: "Во всех сообщениях модерации время показывается с этим сдвигом. Для Москвы 3.",
    group: "Интерфейс",
  },
  "site.favicon_url": {
    label: "Favicon",
    hint: "URL иконки сайта (favicon.ico или ссылка на изображение).",
    group: "Интерфейс",
  },
  "bot.username": {
    label: "Username бота",
    hint: "Без @, например snews_robot. Нужен для быстрых ссылок «Предложить новость».",
    group: "Telegram",
  },
};

/** Settings whose value is a multi-line template, not a short field. */
const MULTILINE = new Set<string>([]);

export default function SettingsPage() {
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [dirty, setDirty] = useState<Record<string, unknown>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedOk, setSavedOk] = useState(false);
  const toast = useToast();

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

  // Group settings by their META group. Keys not in META are hidden entirely
  // (they have no human-readable label and should not appear in the UI).
  const groups: Record<string, string[]> = {};
  for (const key of Object.keys(settings)) {
    if (!META[key]) continue; // skip unknown keys like moderation.card_template
    const g = META[key].group;
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
                const isLong = MULTILINE.has(key);
                return (
                  <div
                    key={key}
                    className={
                      isLong ? "space-y-2 p-4" : "flex items-center gap-4 p-4"
                    }
                  >
                    <div className="flex-1">
                      <div className="text-sm font-medium">{meta?.label ?? key}</div>
                      <div className="text-xs text-muted-foreground">{meta?.hint ?? key}</div>
                    </div>
                    {isBool ? (
                      <Checkbox
                        checked={Boolean(value)}
                        onChange={(v) => setValue(key, v)}
                      />
                    ) : isLong ? (
                      <textarea
                        className="input min-h-[220px] font-mono text-xs"
                        value={value === null || value === undefined ? "" : String(value)}
                        onChange={(e) => setValue(key, e.target.value)}
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

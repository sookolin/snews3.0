"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import {
  AreaChart, Area, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { BellRing, Pencil, Send as SendIcon } from "lucide-react";
import { api, fetcher } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Checkbox, Select, Switch } from "@/components/Controls";
import { Modal, Field } from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { useRoleLabels } from "@/lib/roles";
import { pushState, subscribePush, unsubscribePush } from "@/lib/push";
import type { Profile } from "@/lib/types";

const LANGUAGES = [
  { value: "ru", label: "Русский" },
  { value: "en", label: "English" },
];

/** Push event types a user can opt into, in the order they are shown. */
const PUSH_TYPES: { key: string; label: string; hint: string }[] = [
  { key: "news_pending", label: "Новость на модерации", hint: "Пришла новость, ожидающая решения." },
  { key: "news_published", label: "Новость опубликована", hint: "Пост ушёл в канал." },
  { key: "news_failed", label: "Ошибка публикации", hint: "Публикация не удалась." },
  { key: "bot_submission", label: "Заявка из бота", hint: "Читатель предложил новость." },
  { key: "system", label: "Системные события", hint: "Парсер, воркеры, интеграции." },
];

/** Telegram DM notifications, delivered by the bot to a linked account. */
const BOT_TYPES: { key: string; label: string; hint: string }[] = [
  { key: "login", label: "Вход в аккаунт", hint: "Сообщение при каждой авторизации в панели." },
  { key: "daily_stats", label: "Ежедневная статистика", hint: "Сводка за сутки в указанное время." },
];

function StatCard({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <div className="card p-4">
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className={`mt-1.5 text-2xl font-semibold ${tone ?? ""}`}>{value}</div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 px-5 py-3">
      <div className="text-sm">{label}</div>
      <div className="text-sm text-muted-foreground">{children}</div>
    </div>
  );
}

export default function ProfilePage() {
  // Super admins open someone else's cabinet with ?user_id=…
  const userId = useSearchParams().get("user_id");
  const query = userId ? `/profile?user_id=${userId}` : "/profile";
  const { data, error, mutate } = useSWR<Profile>(query, fetcher);
  const labels = useRoleLabels();
  const toast = useToast();

  const [prefs, setPrefs] = useState<{ push: Record<string, boolean>; bot: Record<string, unknown> }>({
    push: {},
    bot: {},
  });
  const [saving, setSaving] = useState(false);
  const [push, setPush] = useState({ supported: false, subscribed: false });
  const [editingProfile, setEditingProfile] = useState(false);
  const [profileForm, setProfileForm] = useState({ full_name: "", language: "" });

  useEffect(() => {
    if (!data) return;
    const p = (data.notify_prefs ?? {}) as Record<string, Record<string, unknown>>;
    setPrefs({
      push: (p.push ?? {}) as Record<string, boolean>,
      bot: (p.bot ?? {}) as Record<string, unknown>,
    });
  }, [data]);

  useEffect(() => { pushState().then(setPush); }, []);

  const save = async () => {
    setSaving(true);
    try {
      await api(`/profile/notifications${userId ? `?user_id=${userId}` : ""}`, {
        method: "PUT",
        body: JSON.stringify(prefs),
      });
      await mutate();
      toast.success("Настройки уведомлений сохранены");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  /** Ask the browser for permission, then register the device on the server. */
  const openEditProfile = () => {
    setProfileForm({ full_name: u.full_name ?? "", language: u.language ?? "ru" });
    setEditingProfile(true);
  };

  const saveProfile = async () => {
    setSaving(true);
    try {
      await api(`/profile${userId ? `?user_id=${userId}` : ""}`, {
        method: "PATCH",
        body: JSON.stringify(profileForm),
      });
      await mutate();
      setEditingProfile(false);
      toast.success("Профиль обновлён");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const toggleDevice = async (on: boolean) => {
    try {
      if (on) {
        await subscribePush();
        toast.success("Устройство подписано на уведомления");
      } else {
        await unsubscribePush();
        toast.info("Подписка отключена");
      }
      setPush(await pushState());
      await mutate();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  if (error) return <p className="text-red-600">Ошибка загрузки: {(error as Error).message}</p>;
  if (!data) return <p className="text-muted-foreground">Загрузка…</p>;

  const u = data.user;
  const s = data.stats;

  return (
    <div className="max-w-4xl">
      <PageHeader
        title={data.is_self ? "Личный кабинет" : `Кабинет: ${u.full_name || u.email}`}
        action={
          <button className="btn-primary" disabled={saving} onClick={save}>
            {saving ? "Сохранение…" : "Сохранить"}
          </button>
        }
      />
      {!data.is_self && (
        <p className="mb-5 rounded-md bg-amber-50 p-2 text-sm text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
          Вы открыли кабинет другого пользователя как супер-администратор. Изменения применятся к нему.
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card">
          <div className="flex items-center justify-between border-b border-border px-5 py-3">
            <span className="font-medium">Профиль</span>
            <button
              onClick={openEditProfile}
              className="rounded-md p-1.5 hover:bg-muted"
              title="Редактировать профиль"
            >
              <Pencil className="h-4 w-4" />
            </button>
          </div>
          <div className="divide-y divide-border">
            <Row label="Имя">{u.full_name || "—"}</Row>
            <Row label="Email">{u.email}</Row>
            <Row label="Язык">{LANGUAGES.find((l) => l.value === u.language)?.label ?? u.language}</Row>
            <Row label="Роль">{labels[u.role] ?? u.role}</Row>
            <Row label="Двухфакторная авторизация">{u.is_2fa_enabled ? "Включена" : "Выключена"}</Row>
            <Row label="Telegram">{u.telegram_id ? String(u.telegram_id) : "не привязан"}</Row>
            <Row label="Яндекс">{u.yandex_id || "не привязан"}</Row>
            <Row label="VK">{u.vk_id || "не привязан"}</Row>
            <Row label="Последний вход">
              {u.last_login_at ? new Date(u.last_login_at).toLocaleString("ru-RU") : "—"}
            </Row>
            <Row label="Устройств с push">{data.push_devices}</Row>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 content-start">
          <StatCard label="Обработано" value={s.moderated_total} />
          <StatCard label="Одобрено" value={s.approved} tone="text-green-600" />
          <StatCard label="Опубликовано" value={s.published} tone="text-blue-600" />
          <StatCard label="Отклонено" value={s.rejected} tone="text-red-600" />
          <StatCard label="Отредактировано" value={s.edited} />
        </div>
      </div>

      <div className="card mt-6 p-5">
        <h2 className="mb-4 text-lg font-medium">Активность за 7 дней</h2>
        <div className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={s.last_7_days}>
              <defs>
                <linearGradient id="gradProfile" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.7} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" fontSize={12} />
              <YAxis allowDecimals={false} fontSize={12} />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="count"
                name="Обработано"
                stroke="#6366f1"
                strokeWidth={2}
                fill="url(#gradProfile)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="card mt-6">
        <div className="flex items-center gap-2 border-b border-border px-5 py-3 font-medium">
          <BellRing className="h-4 w-4" /> Push-уведомления
        </div>
        <div className="space-y-3 px-5 py-4">
          {data.is_self ? (
            push.supported ? (
              <Switch
                checked={push.subscribed}
                onChange={toggleDevice}
                label="Присылать уведомления на это устройство"
              />
            ) : (
              <p className="text-sm text-muted-foreground">
                Браузер не поддерживает push. На iPhone откройте сайт в Safari и добавьте его на
                экран «Домой», затем включите уведомления здесь.
              </p>
            )
          ) : (
            <p className="text-sm text-muted-foreground">
              Устройства подключает сам пользователь. Здесь можно настроить только типы событий.
            </p>
          )}
          <div className="divide-y divide-border border-t border-border pt-1">
            {PUSH_TYPES.map((t) => (
              <div key={t.key} className="flex items-center justify-between gap-4 py-3">
                <div>
                  <div className="text-sm font-medium">{t.label}</div>
                  <div className="text-xs text-muted-foreground">{t.hint}</div>
                </div>
                <Checkbox
                  checked={Boolean(prefs.push[t.key])}
                  onChange={(v) =>
                    setPrefs((p) => ({ ...p, push: { ...p.push, [t.key]: v } }))
                  }
                />
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card mt-6">
        <div className="flex items-center gap-2 border-b border-border px-5 py-3 font-medium">
          <SendIcon className="h-4 w-4" /> Уведомления в Telegram
        </div>
        <div className="px-5 py-4">
          {!u.telegram_id && (
            <p className="mb-3 text-sm text-muted-foreground">
              Telegram не привязан — сообщения приходить не будут. ID задаётся в разделе
              «Пользователи».
            </p>
          )}
          <div className="divide-y divide-border">
            {BOT_TYPES.map((t) => (
              <div key={t.key} className="flex items-center justify-between gap-4 py-3">
                <div>
                  <div className="text-sm font-medium">{t.label}</div>
                  <div className="text-xs text-muted-foreground">{t.hint}</div>
                </div>
                <Checkbox
                  checked={Boolean(prefs.bot[t.key])}
                  onChange={(v) => setPrefs((p) => ({ ...p, bot: { ...p.bot, [t.key]: v } }))}
                />
              </div>
            ))}
            <div className="flex items-center justify-between gap-4 py-3">
              <div>
                <div className="text-sm font-medium">Время ежедневной сводки</div>
                <div className="text-xs text-muted-foreground">
                  Часовой пояс — как в настройках системы.
                </div>
              </div>
              <Select
                className="w-28"
                value={String(prefs.bot.daily_time ?? "09:00")}
                onChange={(v) => setPrefs((p) => ({ ...p, bot: { ...p.bot, daily_time: v } }))}
              >
                {Array.from({ length: 24 }, (_, h) => `${String(h).padStart(2, "0")}:00`).map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </Select>
            </div>
          </div>
        </div>
      </div>

      <Modal open={editingProfile} onClose={() => setEditingProfile(false)} title="Редактирование профиля">
        <div className="space-y-4">
          <Field label="Имя" hint="Отображается в интерфейсе">
            <input
              type="text"
              className="input w-full"
              value={profileForm.full_name}
              onChange={(e) => setProfileForm((f) => ({ ...f, full_name: e.target.value }))}
              placeholder="Введите имя"
            />
          </Field>
          <Field label="Язык интерфейса">
            <select
              className="input w-full"
              value={profileForm.language}
              onChange={(e) => setProfileForm((f) => ({ ...f, language: e.target.value }))}
            >
              {LANGUAGES.map((l) => (
                <option key={l.value} value={l.value}>
                  {l.label}
                </option>
              ))}
            </select>
          </Field>
          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary" onClick={() => setEditingProfile(false)}>
              Отмена
            </button>
            <button className="btn-primary" disabled={saving} onClick={saveProfile}>
              {saving ? "Сохранение…" : "Сохранить"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}


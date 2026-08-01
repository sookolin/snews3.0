"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import useSWR from "swr";
import {
  AreaChart, Area, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { BellRing, Bell, Pencil, Send as SendIcon, Camera } from "lucide-react";
import { api, fetcher } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Checkbox, Select, Switch } from "@/components/Controls";
import { Modal, Field } from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { useRoleLabels } from "@/lib/roles";
import { pushState, subscribePush, unsubscribePush, sendTestPush } from "@/lib/push";
import type { Profile } from "@/lib/types";

const LANGUAGES = [
  { value: "ru", label: "Русский" },
  { value: "en", label: "English" },
];

/** Push event types a user can opt into, in the order they are shown.
 *
 * These mirror the in-app bell events: the same events that raise a bell
 * notification also fire a Web Push when enabled here. The news-moderation
 * events come first (what a moderator cares about most), followed by the
 * account events shown in the bell section below. */
const PUSH_TYPES: { key: string; label: string; hint: string }[] = [
  { key: "news_pending", label: "Новость на модерации", hint: "Пришла новость, ожидающая решения." },
  { key: "news_published", label: "Новость опубликована", hint: "Пост ушёл в канал." },
  { key: "news_failed", label: "Ошибка публикации", hint: "Публикация не удалась." },
  { key: "role_changed", label: "Изменение роли", hint: "Когда администратор меняет вашу роль." },
  { key: "profile_updated", label: "Обновление профиля", hint: "Когда кто-то изменил ваши данные." },
  { key: "password_changed", label: "Смена пароля", hint: "Когда пароль изменён администратором." },
  { key: "account_deactivated", label: "Блокировка аккаунта", hint: "Уведомление о блокировке." },
  { key: "account_activated", label: "Разблокировка аккаунта", hint: "Уведомление о разблокировке." },
  { key: "2fa_reset", label: "Сброс 2FA", hint: "Когда администратор отключил вашу 2FA." },
];

/** In-app bell notification types a user can opt into. */
const INAPP_TYPES: { key: string; label: string; hint: string }[] = [
  { key: "role_changed",        label: "Изменение роли",              hint: "Когда администратор меняет вашу роль." },
  { key: "profile_updated",     label: "Обновление профиля",          hint: "Когда кто-то изменил ваши данные." },
  { key: "password_changed",    label: "Смена пароля",                hint: "Когда пароль изменён администратором." },
  { key: "account_deactivated", label: "Деактивация аккаунта",        hint: "Уведомление о блокировке." },
  { key: "account_activated",   label: "Активация аккаунта",          hint: "Уведомление о разблокировке." },
  { key: "2fa_reset",           label: "Сброс двухфакторной авторизации", hint: "Когда администратор отключил вашу 2FA." },
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

  const [prefs, setPrefs] = useState<{ push: Record<string, boolean>; bot: Record<string, unknown>; inapp: Record<string, boolean> }>({
    push: {},
    bot: {},
    inapp: {},
  });
  const [saving, setSaving] = useState(false);
  const [push, setPush] = useState({ supported: false, subscribed: false });
  const [editingProfile, setEditingProfile] = useState(false);
  const [profileForm, setProfileForm] = useState({
    full_name: "", email: "", password: "", password2: "",
    telegram_id: "", yandex_id: "", vk_id: "",
  });
  const [profileError, setProfileError] = useState<string | null>(null);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  // 2FA management
  const [twoFaStep, setTwoFaStep] = useState<"idle" | "setup" | "enable" | "disable">("idle");
  const [twoFaUri, setTwoFaUri]   = useState<string | null>(null);
  const [twoFaCode, setTwoFaCode] = useState("");

  useEffect(() => {
    if (!data) return;
    const p = (data.notify_prefs ?? {}) as Record<string, Record<string, unknown>>;
    setPrefs({
      push:   (p.push   ?? {}) as Record<string, boolean>,
      bot:    (p.bot    ?? {}) as Record<string, unknown>,
      inapp:  (p.inapp  ?? {}) as Record<string, boolean>,
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

  const uploadPhoto = async (file: File) => {
    setUploadingPhoto(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await api(`/profile/photo${userId ? `?user_id=${userId}` : ""}`, {
        method: "POST",
        body: fd,
      });
      await mutate();
      toast.success("Фото обновлено");
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setUploadingPhoto(false);
    }
  };

  const openEditProfile = () => {
    if (!data) return;
    const u = data.user;
    setProfileForm({
      full_name: u.full_name ?? "",
      email: u.email ?? "",
      password: "",
      password2: "",
      telegram_id: u.telegram_id ? String(u.telegram_id) : "",
      yandex_id: u.yandex_id ?? "",
      vk_id: u.vk_id ?? "",
    });
    setProfileError(null);
    setEditingProfile(true);
  };

  const saveProfile = async () => {
    if (profileForm.password && profileForm.password !== profileForm.password2) {
      setProfileError("Пароли не совпадают");
      return;
    }
    if (profileForm.password && profileForm.password.length < 8) {
      setProfileError("Пароль должен быть не менее 8 символов");
      return;
    }
    setSaving(true);
    setProfileError(null);
    try {
      const body: Record<string, string | number | null> = {
        full_name: profileForm.full_name,
      };
      if (profileForm.email && data && profileForm.email !== data.user.email) {
        body.email = profileForm.email;
      }
      if (profileForm.password) body.password = profileForm.password;
      // Social links — send current form values (null means "unlink")
      body.telegram_id = profileForm.telegram_id ? Number(profileForm.telegram_id) : null;
      body.yandex_id = profileForm.yandex_id || null;
      body.vk_id = profileForm.vk_id || null;
      await api(`/profile${userId ? `?user_id=${userId}` : ""}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      await mutate();
      setEditingProfile(false);
      toast.success("Профиль обновлён");
    } catch (e) {
      setProfileError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  // 2FA helpers
  const start2faSetup = async () => {
    try {
      // Backend returns { secret, provisioning_uri } (TwoFactorSetup schema)
      const res = await api<{ secret: string; provisioning_uri: string }>("/auth/2fa/setup", { method: "POST" });
      setTwoFaUri(res.provisioning_uri);
      setTwoFaStep("setup");
    } catch (e) { toast.error((e as Error).message); }
  };

  const enable2fa = async () => {
    try {
      // Backend TwoFactorVerify schema uses field name "totp_code"
      await api("/auth/2fa/enable", { method: "POST", body: JSON.stringify({ totp_code: twoFaCode }) });
      await mutate();
      setTwoFaStep("idle");
      setTwoFaCode("");
      toast.success("2FA включена");
    } catch (e) { toast.error((e as Error).message); }
  };

  const disable2fa = async () => {
    try {
      // Backend /auth/2fa/disable requires no code — just POST with empty body
      await api("/auth/2fa/disable", { method: "POST" });
      await mutate();
      setTwoFaStep("idle");
      setTwoFaCode("");
      toast.success("2FA отключена");
    } catch (e) { toast.error((e as Error).message); }
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

  const [testingPush, setTestingPush] = useState(false);
  const testPush = async () => {
    setTestingPush(true);
    try {
      const detail = await sendTestPush();
      toast.success(detail);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setTestingPush(false);
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

          {/* Avatar row */}
          <div className="flex items-center gap-4 px-5 py-4 border-b border-border">
            <div className="relative">
              {u.photo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={u.photo_url}
                  alt={u.full_name || u.email}
                  className="h-16 w-16 rounded-full object-cover ring-2 ring-border"
                  width={64}
                  height={64}
                />
              ) : (
                <span className="flex h-16 w-16 items-center justify-center rounded-full bg-sky-600/20 text-xl font-semibold text-sky-600 dark:text-sky-300">
                  {(u.full_name || u.email || "?").slice(0, 2).toUpperCase()}
                </span>
              )}
              <label
                className={`absolute -bottom-1 -right-1 flex h-6 w-6 cursor-pointer items-center justify-center rounded-full bg-card border border-border shadow hover:bg-muted transition-colors ${uploadingPhoto ? "opacity-50 pointer-events-none" : ""}`}
                title="Загрузить фото"
              >
                <Camera className="h-3.5 w-3.5 text-muted-foreground" />
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  className="sr-only"
                  disabled={uploadingPhoto}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) uploadPhoto(file);
                    e.target.value = "";
                  }}
                />
              </label>
            </div>
            <div className="min-w-0">
              <div className="font-medium truncate">{u.full_name || u.email}</div>
              {u.full_name && <div className="text-xs text-muted-foreground truncate">{u.email}</div>}
              <div className="mt-1 text-xs text-muted-foreground">
                {uploadingPhoto ? "Загрузка…" : "Нажмите на 📷 для замены фото"}
              </div>
            </div>
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
          <Bell className="h-4 w-4" /> Уведомления в панели (колокольчик)
        </div>
        <div className="space-y-3 px-5 py-4">
          <p className="text-xs text-muted-foreground">
            Выберите, о каких событиях показывать уведомления в колокольчике. По умолчанию все включены.
          </p>
          <div className="divide-y divide-border border-t border-border pt-1">
            {INAPP_TYPES.map((t) => (
              <div key={t.key} className="flex items-center justify-between gap-4 py-3">
                <div>
                  <div className="text-sm font-medium">{t.label}</div>
                  <div className="text-xs text-muted-foreground">{t.hint}</div>
                </div>
                <Checkbox
                  checked={prefs.inapp[t.key] !== false}
                  onChange={(v) =>
                    setPrefs((p) => ({ ...p, inapp: { ...p.inapp, [t.key]: v } }))
                  }
                />
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card mt-6">
        <div className="flex items-center gap-2 border-b border-border px-5 py-3 font-medium">
          <BellRing className="h-4 w-4" /> Push-уведомления
        </div>
        <div className="space-y-3 px-5 py-4">
          {data.is_self ? (
            push.supported ? (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <Switch
                  checked={push.subscribed}
                  onChange={toggleDevice}
                  label="Присылать уведомления на это устройство"
                />
                {push.subscribed && (
                  <button
                    className="btn-outline text-sm"
                    disabled={testingPush}
                    onClick={testPush}
                  >
                    {testingPush ? "Отправка…" : "Проверить"}
                  </button>
                )}
              </div>
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
          <p className="text-xs text-muted-foreground">
            Push дублирует уведомления из колокольчика: включённые здесь события
            приходят и в панель, и на устройство.
          </p>
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
          {profileError && (
            <p className="rounded-md bg-rose-50 p-2 text-sm text-rose-600 dark:bg-rose-950/40">{profileError}</p>
          )}
          <Field label="Имя" hint="Отображается в интерфейсе">
            <input
              type="text"
              className="input"
              value={profileForm.full_name}
              onChange={(e) => setProfileForm((f) => ({ ...f, full_name: e.target.value }))}
              placeholder="Введите имя"
            />
          </Field>
          <Field label="Email">
            <input
              type="email"
              className="input"
              value={profileForm.email}
              onChange={(e) => setProfileForm((f) => ({ ...f, email: e.target.value }))}
              placeholder="email@example.com"
            />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Новый пароль" hint="Минимум 8 символов; оставьте пустым, чтобы не менять">
              <input
                type="password"
                className="input"
                value={profileForm.password}
                onChange={(e) => setProfileForm((f) => ({ ...f, password: e.target.value }))}
                placeholder="••••••••"
              />
            </Field>
            <Field label="Повторите пароль">
              <input
                type="password"
                className="input"
                value={profileForm.password2}
                onChange={(e) => setProfileForm((f) => ({ ...f, password2: e.target.value }))}
                placeholder="••••••••"
              />
            </Field>
          </div>

          {/* Social accounts */}
          <div className="rounded-lg border border-border px-4 py-3">
            <div className="mb-3 text-sm font-medium">Привязка аккаунтов</div>
            <div className="grid grid-cols-3 gap-4">
              <Field label="Telegram ID" hint="Числовой ID, для DM-уведомлений">
                <input
                  type="number"
                  className="input"
                  value={profileForm.telegram_id}
                  onChange={(e) => setProfileForm((f) => ({ ...f, telegram_id: e.target.value }))}
                  placeholder="123456789"
                />
              </Field>
              <Field label="Яндекс ID" hint="Для входа через Яндекс">
                <input
                  type="text"
                  className="input"
                  value={profileForm.yandex_id}
                  onChange={(e) => setProfileForm((f) => ({ ...f, yandex_id: e.target.value }))}
                  placeholder="yandex_uid"
                />
              </Field>
              <Field label="VK ID" hint="Для входа через VK">
                <input
                  type="text"
                  className="input"
                  value={profileForm.vk_id}
                  onChange={(e) => setProfileForm((f) => ({ ...f, vk_id: e.target.value }))}
                  placeholder="vk_uid"
                />
              </Field>
            </div>
          </div>

          {/* 2FA section — only available for own profile, not super-admin editing another */}
          {data?.is_self && (
            <div className="rounded-lg border border-border px-4 py-3">
              <div className="mb-2 flex items-center justify-between">
                <div className="text-sm font-medium">Двухфакторная аутентификация</div>
                <span className={`badge text-xs ${u?.is_2fa_enabled ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-600"}`}>
                  {u?.is_2fa_enabled ? "включена" : "выключена"}
                </span>
              </div>

              {twoFaStep === "idle" && !u?.is_2fa_enabled && (
                <button className="btn-outline text-sm" onClick={start2faSetup}>
                  Настроить 2FA
                </button>
              )}
              {twoFaStep === "idle" && u?.is_2fa_enabled && (
                <button className="btn-outline text-sm" onClick={() => setTwoFaStep("disable")}>
                  Отключить 2FA
                </button>
              )}

              {twoFaStep === "setup" && twoFaUri && (
                <div className="space-y-3">
                  <p className="text-xs text-muted-foreground">
                    Отсканируйте QR-код в Google Authenticator / Яндекс Ключ, затем введите код.
                  </p>
                  {/* QR: show the URI as an img via a free QR API — no server-side dep */}
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(twoFaUri)}`}
                    alt="QR для 2FA"
                    className="rounded border border-border"
                    width={160}
                    height={160}
                  />
                  <div className="flex gap-2">
                    <input
                      className="input w-32 font-mono tracking-widest"
                      maxLength={6}
                      placeholder="000000"
                      value={twoFaCode}
                      onChange={(e) => setTwoFaCode(e.target.value.replace(/\D/g, ""))}
                    />
                    <button className="btn-primary" onClick={enable2fa}>Включить</button>
                    <button className="btn-outline" onClick={() => { setTwoFaStep("idle"); setTwoFaCode(""); }}>Отмена</button>
                  </div>
                </div>
              )}

              {twoFaStep === "disable" && (
                <div className="space-y-2">
                  <p className="text-xs text-muted-foreground">Введите текущий код из приложения для подтверждения.</p>
                  <div className="flex gap-2">
                    <input
                      className="input w-32 font-mono tracking-widest"
                      maxLength={6}
                      placeholder="000000"
                      value={twoFaCode}
                      onChange={(e) => setTwoFaCode(e.target.value.replace(/\D/g, ""))}
                    />
                    <button className="btn-danger text-sm" onClick={disable2fa}>Отключить</button>
                    <button className="btn-outline" onClick={() => { setTwoFaStep("idle"); setTwoFaCode(""); }}>Отмена</button>
                  </div>
                </div>
              )}
            </div>
          )}

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


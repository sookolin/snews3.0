"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { Eye, Pencil, Settings2, Tags, Trash2, UserCircle, ShieldOff, Ban } from "lucide-react";
import { api, fetcher } from "@/lib/api";
import type { City, Page, User } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Modal, Field } from "@/components/Modal";
import { Checkbox, Select } from "@/components/Controls";
import { confirm } from "@/components/ConfirmDialog";
import { useToast } from "@/components/Toast";
import { ROLE_ORDER, getPreviewRole, setPreviewRole } from "@/lib/roles";

const DEFAULT_ROLE_COLORS: Record<string, string> = {
  super_admin: "#6366f1",
  admin:       "#0ea5e9",
  moderator:   "#f59e0b",
  editor:      "#10b981",
  reviewer:    "#94a3b8",
};

interface PermissionInfo { value: string; label: string; group: string; city_scoped?: boolean }
interface PermissionCatalog {
  permissions: PermissionInfo[];
  roles: Record<string, string[]>;
  all_roles: string[];
}

type CityScopeMode = "role" | "grant" | "grant_selected" | "deny" | "deny_selected";
/** Mirrors shared.enums.CITY_SCOPE_REQUIRES_VIEW: edit-style perms need the matching view perm. */
const CITY_SCOPE_REQUIRES_VIEW: Record<string, string> = {
  "city:manage": "city:view",
  "source:manage": "source:view",
  "news:edit": "news:view",
  "news:moderate": "news:view",
  "news:publish": "news:view",
  "news:delete": "news:view",
};
interface RolePermEntry {
  grant: string[];
  deny: string[];
  city_scoped: Record<string, { mode: CityScopeMode; cities: number[] }>;
}
const BUILT_IN_ROLE_KEYS = ["super_admin", "admin", "moderator", "editor", "reviewer"];

interface UserForm {
  id?: number;
  email: string;
  full_name?: string;
  role: string;
  is_active: boolean;
  language: string;
  telegram_id?: number | null;
  telegram_username?: string | null;
  permissions: { grant?: string[]; deny?: string[] };
  city_access: number[];
  password?: string;
}

const FALLBACK_ROLE_LABELS: Record<string, string> = {
  super_admin: "Супер-админ",
  admin: "Администратор",
  moderator: "Модератор",
  editor: "Редактор",
  reviewer: "Наблюдатель",
};

const EMPTY: UserForm = {
  email: "", full_name: "", role: "reviewer", is_active: true, language: "ru",
  telegram_id: null, telegram_username: "", permissions: {}, city_access: [], password: "",
};

export default function UsersPage() {
  const { data, mutate } = useSWR<Page<User>>("/users?size=100", fetcher);
  const { data: cities } = useSWR<Page<City>>("/cities?size=200", fetcher);
  const { data: catalog, mutate: mutateCatalog } = useSWR<PermissionCatalog>("/users/permissions", fetcher);
  const { data: roleLabels, mutate: mutateLabels } =
    useSWR<Record<string, string>>("/users/role-labels", fetcher);
  const { data: roleColorsData, mutate: mutateColors } =
    useSWR<Record<string, string>>("/users/role-colors", fetcher);
  const { data: rolePermsData, mutate: mutateRolePerms } =
    useSWR<Record<string, RolePermEntry>>("/users/role-permissions", fetcher);
  const { data: me } = useSWR<User>("/auth/me", fetcher, { revalidateOnFocus: false });
  const isSuperAdmin = me?.role === "super_admin";
  const [form, setForm] = useState<UserForm | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Rename-roles dialog: labels + colors together.
  const [renaming, setRenaming] = useState<Record<string, string> | null>(null);
  const [renamingColors, setRenamingColors] = useState<Record<string, string>>({});
  // Role permissions management dialog
  const [rolePermsModal, setRolePermsModal] = useState<Record<string, RolePermEntry> | null>(null);
  // Add-role dialog
  const [newRole, setNewRole] = useState<{ key: string; label: string; color: string } | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const toast = useToast();

  const ROLE_COLORS = { ...DEFAULT_ROLE_COLORS, ...(roleColorsData ?? {}) };

  useEffect(() => setPreview(getPreviewRole()), []);

  const ROLE_LABELS = { ...FALLBACK_ROLE_LABELS, ...(roleLabels ?? {}) };

  const saveNames = async () => {
    if (!renaming) return;
    try {
      await Promise.all([
        api("/users/role-labels", { method: "PUT", body: JSON.stringify(renaming) }),
        api("/users/role-colors", { method: "PUT", body: JSON.stringify(renamingColors) }),
      ]);
      await Promise.all([mutateLabels(), mutateColors()]);
      setRenaming(null);
      toast.success("Роли обновлены");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const saveRolePerms = async () => {
    if (!rolePermsModal) return;
    try {
      await api("/users/role-permissions", { method: "PUT", body: JSON.stringify(rolePermsModal) });
      await mutateRolePerms();
      setRolePermsModal(null);
      toast.success("Права ролей сохранены");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const openRolePermsModal = () => {
    // Clone existing or start empty
    const base: Record<string, RolePermEntry> = {};
    for (const r of catalog?.all_roles ?? []) {
      if (r === "super_admin") continue;
      base[r] = {
        grant: [...(rolePermsData?.[r]?.grant ?? [])],
        deny: [...(rolePermsData?.[r]?.deny ?? [])],
        city_scoped: { ...(rolePermsData?.[r]?.city_scoped ?? {}) },
      };
    }
    setRolePermsModal(base);
  };

  const setRolePermState = (
    role: string,
    perm: string,
    next: "grant" | "deny" | "role"
  ) => {
    if (!rolePermsModal) return;
    const cur = rolePermsModal[role] ?? { grant: [], deny: [], city_scoped: {} };
    const g = new Set(cur.grant);
    const d = new Set(cur.deny);
    g.delete(perm); d.delete(perm);
    if (next === "grant") g.add(perm);
    if (next === "deny") d.add(perm);
    setRolePermsModal({ ...rolePermsModal, [role]: { ...cur, grant: [...g], deny: [...d] } });
  };

  const rolePermStateOf = (role: string, perm: string): "grant" | "deny" | "role" => {
    if (!rolePermsModal) return "role";
    const cur = rolePermsModal[role];
    if (cur?.deny?.includes(perm)) return "deny";
    if (cur?.grant?.includes(perm)) return "grant";
    return "role";
  };

  /** City-scope mode for a permission in the role permissions modal. */
  const cityScopeOf = (role: string, perm: string): { mode: CityScopeMode; cities: number[] } => {
    const cur = rolePermsModal?.[role]?.city_scoped?.[perm];
    return cur ?? { mode: "role", cities: [] };
  };

  const setCityScopeMode = (role: string, perm: string, mode: CityScopeMode) => {
    if (!rolePermsModal) return;
    const cur = rolePermsModal[role] ?? { grant: [], deny: [], city_scoped: {} };
    const prevCities = cur.city_scoped?.[perm]?.cities ?? [];
    const nextScoped = { ...cur.city_scoped, [perm]: { mode, cities: mode.endsWith("selected") ? prevCities : [] } };
    if (mode === "role") delete nextScoped[perm];
    setRolePermsModal({ ...rolePermsModal, [role]: { ...cur, city_scoped: nextScoped } });
  };

  const toggleCityScopeCity = (role: string, perm: string, cityId: number) => {
    if (!rolePermsModal) return;
    const cur = rolePermsModal[role] ?? { grant: [], deny: [], city_scoped: {} };
    const entry = cur.city_scoped?.[perm] ?? { mode: "grant_selected" as CityScopeMode, cities: [] };
    const cities = entry.cities.includes(cityId)
      ? entry.cities.filter((c) => c !== cityId)
      : [...entry.cities, cityId];
    setRolePermsModal({
      ...rolePermsModal,
      [role]: { ...cur, city_scoped: { ...cur.city_scoped, [perm]: { ...entry, cities } } },
    });
  };

  const addRole = async () => {
    if (!newRole) return;
    try {
      await api("/users/roles", { method: "POST", body: JSON.stringify(newRole) });
      await Promise.all([mutateCatalog(), mutateLabels(), mutateColors(), mutateRolePerms()]);
      setNewRole(null);
      toast.success("Роль создана");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const deleteRole = async (roleKey: string) => {
    if (!(await confirm({ message: `Удалить роль «${ROLE_LABELS[roleKey] ?? roleKey}»? Пользователи с этой ролью не будут переназначены автоматически.`, danger: true }))) return;
    try {
      await api(`/users/roles/${roleKey}`, { method: "DELETE" });
      await Promise.all([mutateCatalog(), mutateLabels(), mutateColors(), mutateRolePerms()]);
      setRolePermsModal((prev) => {
        if (!prev) return prev;
        const next = { ...prev };
        delete next[roleKey];
        return next;
      });
      toast.success("Роль удалена");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const applyPreview = (role: string | null) => {
    setPreviewRole(role);
    setPreview(role);
    toast.info(role ? `Просмотр от лица: ${ROLE_LABELS[role] ?? role}` : "Просмотр от своей роли");
  };

  const openNew = () => { setForm({ ...EMPTY }); setError(null); };
  const openEdit = (u: User) => {
    setForm({
      id: u.id, email: u.email, full_name: u.full_name ?? "", role: u.role,
      is_active: u.is_active, language: u.language, telegram_id: u.telegram_id ?? null,
      telegram_username: (u as { telegram_username?: string }).telegram_username ?? "",
      permissions: (u.permissions ?? {}) as UserForm["permissions"],
      city_access: u.city_access ?? [],
      password: "",
    });
    setError(null);
  };
  const upd = (patch: Partial<UserForm>) => setForm((f) => (f ? { ...f, ...patch } : f));

  const rolePerms = form ? (catalog?.roles[form.role] ?? []) : [];
  const grant = form?.permissions?.grant ?? [];
  const deny = form?.permissions?.deny ?? [];

  /** Effective state of a permission: from role, granted, or denied. */
  const stateOf = (p: string): "grant" | "deny" | "role" => {
    if (deny.includes(p)) return "deny";
    if (grant.includes(p)) return "grant";
    return "role";
  };

  const toggleCityAccess = (cityId: number) => {
    if (!form) return;
    const ids = form.city_access ?? [];
    const next = ids.includes(cityId) ? ids.filter((c) => c !== cityId) : [...ids, cityId];
    upd({ city_access: next });
  };

  const setPermState = (p: string, next: "grant" | "deny" | "role") => {
    if (!form) return;
    const g = new Set(grant);
    const d = new Set(deny);
    g.delete(p); d.delete(p);
    if (next === "grant") g.add(p);
    if (next === "deny") d.add(p);
    upd({ permissions: { grant: [...g], deny: [...d] } });
  };

  const save = async () => {
    if (!form) return;
    setError(null);
    if (!form.id && !form.telegram_id) {
      setError("Укажите Telegram ID — без привязки Telegram пользователя создать нельзя.");
      return;
    }
    const body: Record<string, unknown> = {
      role: form.role,
      is_active: form.is_active,
      language: form.language,
      telegram_id: form.telegram_id ?? null,
      telegram_username: form.telegram_username || null,
      permissions: form.permissions ?? {},
      city_access: form.city_access ?? [],
    };
    if (form.id) {
      body.email = form.email;
      body.full_name = form.full_name || null;
      if (form.password) body.password = form.password;
    }
    try {
      if (form.id) await api(`/users/${form.id}`, { method: "PATCH", body: JSON.stringify(body) });
      else await api("/users", { method: "POST", body: JSON.stringify(body) });
      setForm(null);
      mutate();
    } catch (e) { setError((e as Error).message); }
  };

  const reset2fa = async (userId: number, email: string) => {
    if (!(await confirm({ message: `Сбросить 2FA для ${email}? Пользователь должен будет настроить её заново.`, danger: true }))) return;
    try {
      await api(`/users/${userId}/reset-2fa`, { method: "POST" });
      mutate();
      toast.success("2FA сброшена");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const remove = async (id: number) => {
    if (!(await confirm({ message: "Удалить пользователя?", danger: true }))) return;
    await api(`/users/${id}`, { method: "DELETE" });
    mutate();
  };

  const toggleBan = async (id: number, isBanned: boolean) => {
    const action = isBanned ? "разблокировать" : "заблокировать";
    if (!(await confirm({ message: `${isBanned ? "Разблокировать" : "Заблокировать"} этого пользователя?`, danger: !isBanned }))) return;
    try {
      await api(`/users/${id}/${isBanned ? "unban" : "ban"}`, { method: "POST" });
      mutate();
      toast.success(isBanned ? "Пользователь разблокирован" : "Пользователь заблокирован");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  // Group permissions for display.
  const groups: Record<string, PermissionInfo[]> = {};
  for (const p of catalog?.permissions ?? []) {
    (groups[p.group] ??= []).push(p);
  }

  return (
    <div>
      <PageHeader
        title="Пользователи"
        action={
          <div className="flex gap-2">
            <button className="btn-outline" onClick={openRolePermsModal}>
              <Settings2 className="h-4 w-4" /> Права ролей
            </button>
            <button className="btn-outline" onClick={() => setNewRole({ key: "", label: "", color: "#0ea5e9" })}>
              <Tags className="h-4 w-4" /> Добавить роль
            </button>
            <button className="btn-outline" onClick={() => { setRenaming({ ...ROLE_LABELS }); setRenamingColors({ ...ROLE_COLORS }); }}>
              <Tags className="h-4 w-4" /> Названия ролей
            </button>
            <button className="btn-primary" onClick={openNew}>Добавить</button>
          </div>
        }
      />

      <div className="card mb-4 flex flex-wrap items-center gap-3 p-4">
        <Eye className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">Просмотр сайта от лица роли</span>
        <div className="w-56">
          <Select value={preview ?? ""} onChange={(v) => applyPreview(v || null)}>
            <option value="">Своя роль (без ограничений)</option>
            {(catalog?.all_roles ?? ROLE_ORDER).map((r) => (
              <option key={r} value={r}>{ROLE_LABELS[r] ?? r}</option>
            ))}
          </Select>
        </div>
        <span className="text-xs text-muted-foreground">
          Интерфейс скрывает разделы, недоступные выбранной роли. Права на сервере не меняются.
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {data?.items.map((u) => {
          const ux = u as User & { photo_url?: string | null };
          return (
            <div key={u.id} className="card flex flex-col">
              {/* Header: avatar + identity */}
              <div className="flex items-start gap-3 p-4">
                {ux.photo_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={ux.photo_url}
                    alt={u.full_name || u.email}
                    className="h-10 w-10 shrink-0 rounded-full object-cover"
                    width={40}
                    height={40}
                  />
                ) : (
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-sky-600/20 text-sm font-semibold text-sky-600 dark:text-sky-300">
                    {(u.full_name || u.email || "?").slice(0, 2).toUpperCase()}
                  </span>
                )}
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium text-foreground">
                    {u.full_name || u.email}
                  </div>
                  {u.full_name && (
                    <div className="truncate text-xs text-muted-foreground">{u.email}</div>
                  )}
                  <div className="mt-1.5">
                    <span
                      className="badge"
                      style={{
                        backgroundColor: `${ROLE_COLORS[u.role] ?? "#94a3b8"}22`,
                        color: ROLE_COLORS[u.role] ?? "#94a3b8",
                        boxShadow: `0 0 0 1px ${ROLE_COLORS[u.role] ?? "#94a3b8"}55 inset`,
                      }}
                    >
                      {ROLE_LABELS[u.role] ?? u.role}
                    </span>
                  </div>
                </div>
              </div>

              {/* Social accounts row */}
              <div className="flex flex-wrap gap-x-3 gap-y-1 border-t border-border px-4 py-2.5 text-xs text-muted-foreground">
                {u.telegram_id && (
                  <span className="flex items-center gap-1">
                    <svg viewBox="0 0 24 24" className="h-3 w-3 shrink-0 fill-[#229ED9]" aria-hidden="true">
                      <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
                    </svg>
                    {u.telegram_id}
                  </span>
                )}
                {!u.telegram_id && (
                  <span className="italic opacity-60">нет привязок</span>
                )}
              </div>

              {/* Status flags */}
              <div className="flex flex-wrap gap-1.5 px-4 py-2">
                {u.is_2fa_enabled && (
                  <span className="badge bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:ring-emerald-900">
                    2FA ✓
                  </span>
                )}
                {u.is_banned && (
                  <span className="badge bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:ring-rose-900">
                    🚫 Заблокирован
                  </span>
                )}
                {!u.is_active && !u.is_banned && (
                  <span className="badge bg-orange-50 text-orange-600 ring-orange-200 dark:bg-orange-950/40 dark:text-orange-400 dark:ring-orange-900">
                    Неактивен
                  </span>
                )}
                {u.role !== "super_admin" && (u.city_access?.length ?? 0) > 0 && (
                  <span
                    className="badge bg-indigo-50 text-indigo-700 ring-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-300 dark:ring-indigo-900"
                    title={(u.city_access ?? [])
                      .map((id) => cities?.items.find((c) => c.id === id)?.name ?? `#${id}`)
                      .join(", ")}
                  >
                    🏙 {u.city_access?.length} город{u.city_access?.length === 1 ? "" : "а"}
                  </span>
                )}
                {u.is_active && !u.is_banned && !u.is_2fa_enabled && (
                  <span className="text-xs italic text-muted-foreground/60">активен</span>
                )}
              </div>

              {/* Actions */}
              <div className="mt-auto flex items-center gap-1.5 border-t border-border px-4 py-3">
                <Link
                  className="btn-icon"
                  title="Открыть личный кабинет"
                  href={`/profile?user_id=${u.id}`}
                >
                  <UserCircle className="h-4 w-4" />
                </Link>
                <button className="btn-icon" title="Редактировать" onClick={() => openEdit(u)}>
                  <Pencil className="h-4 w-4" />
                </button>
                {u.is_2fa_enabled && (
                  <button
                    className="btn-icon"
                    title="Сбросить 2FA"
                    onClick={() => reset2fa(u.id, u.email)}
                  >
                    <ShieldOff className="h-4 w-4" />
                  </button>
                )}
                <button
                  className={`btn-icon ${u.is_banned ? "text-amber-500 hover:text-amber-700" : "text-rose-500 hover:text-rose-700"}`}
                  title={u.is_banned ? "Разблокировать аккаунт" : "Заблокировать аккаунт"}
                  onClick={() => toggleBan(u.id, u.is_banned)}
                >
                  <Ban className="h-4 w-4" />
                </button>
                <button className="btn-icon-danger ml-auto" title="Удалить" onClick={() => remove(u.id)}>
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "Редактировать пользователя" : "Новый пользователь"} wide>
        {form && (
          <div className="space-y-4">
            {error && <p className="rounded-md bg-rose-50 p-2 text-sm text-rose-600 dark:bg-rose-950/40">{error}</p>}
            {!form.id && (
              <p className="rounded-md bg-sky-50 p-2 text-xs text-sky-700 dark:bg-sky-950/40 dark:text-sky-300">
                Новый пользователь создаётся привязкой Telegram и ника. Email, пароль и остальные
                данные пользователь настроит сам после входа через Telegram.
              </p>
            )}
            {form.id && (
              <div className="grid grid-cols-2 gap-4">
                <Field label="Email"><input className="input" value={form.email} onChange={(e) => upd({ email: e.target.value })} /></Field>
                <Field label="Имя"><input className="input" value={form.full_name ?? ""} onChange={(e) => upd({ full_name: e.target.value })} /></Field>
              </div>
            )}
            <div className="grid grid-cols-2 gap-4">
              <Field label="Роль" hint="Задаёт базовый набор прав">
                <Select value={form.role} onChange={(v) => upd({ role: v })}>
                  {(catalog?.all_roles ?? Object.keys(ROLE_LABELS))
                    .filter((r) => isSuperAdmin || r !== "super_admin")
                    .map((r) => (
                      <option key={r} value={r}>{ROLE_LABELS[r] ?? r}</option>
                    ))}
                </Select>
              </Field>
              {form.id && (
                <Field label="Новый пароль" hint="Оставьте пустым, чтобы не менять">
                  <input className="input" type="password" value={form.password ?? ""} onChange={(e) => upd({ password: e.target.value })} />
                </Field>
              )}
            </div>
            <div className="rounded-lg border border-border px-4 py-3">
              <div className="mb-3 text-sm font-medium">Привязка Telegram</div>
              <div className="grid grid-cols-2 gap-4">
                <Field label="Telegram ID" hint="Числовой ID — обязателен">
                  <input className="input" type="number" value={form.telegram_id ?? ""} onChange={(e) => upd({ telegram_id: e.target.value ? Number(e.target.value) : null })} placeholder="123456789" />
                </Field>
                <Field label="Ник (username)" hint="Без @">
                  <input className="input" value={form.telegram_username ?? ""} onChange={(e) => upd({ telegram_username: e.target.value.replace(/^@/, "") })} placeholder="username" />
                </Field>
              </div>
            </div>
            <Checkbox checked={form.is_active} onChange={(v) => upd({ is_active: v })} label="Активен" />

            {/* City access restriction */}
            {form.role !== "super_admin" && (
              <div className="rounded-lg border border-border p-4">
                <div className="mb-1 text-sm font-medium">Доступ по городам</div>
                <p className="mb-2 text-xs text-muted-foreground">
                  Если выбраны города, пользователь видит и модерирует новости только для них.
                  Если ничего не выбрано — доступ без ограничений (все города).
                </p>
                <div className="flex max-h-40 flex-wrap gap-1.5 overflow-y-auto rounded-lg border border-border p-2">
                  {(cities?.items ?? [])
                    .filter((c) => c.kind === "city" || !c.kind)
                    .sort((a, b) => a.name.localeCompare(b.name, "ru"))
                    .map((c) => {
                      const active = (form.city_access ?? []).includes(c.id);
                      return (
                        <button
                          key={c.id}
                          type="button"
                          onClick={() => toggleCityAccess(c.id)}
                          className={`rounded-md border px-2.5 py-0.5 text-xs font-medium transition-colors ${
                            active
                              ? "border-primary bg-primary text-primary-foreground"
                              : "border-border bg-card text-muted-foreground hover:border-primary/50 hover:text-foreground"
                          }`}
                        >
                          {c.name}
                        </button>
                      );
                    })}
                  {(cities?.items ?? []).length === 0 && (
                    <span className="text-xs text-muted-foreground">Нет городов</span>
                  )}
                </div>
              </div>
            )}

            {/* Granular permissions */}
            <div className="rounded-lg border border-border">
              <div className="border-b border-border px-4 py-3">
                <div className="text-sm font-semibold">Детальные права</div>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  <b>По роли</b> — как задано ролью. <b>Разрешить</b> — добавить право сверх роли.
                  <b> Запретить</b> — отобрать право, даже если роль его даёт.
                </p>
              </div>
              <div className="max-h-80 overflow-y-auto p-4">
                <div className="space-y-5">
                  {Object.entries(groups).map(([group, perms]) => (
                    <div key={group}>
                      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                        {group}
                      </div>
                      <div className="space-y-2">
                        {perms.map((p) => {
                          const st = stateOf(p.value);
                          const fromRole = rolePerms.includes(p.value);
                          return (
                            <div
                              key={p.value}
                              className="grid grid-cols-1 items-center gap-2 rounded-lg border border-border/70 p-2.5 sm:grid-cols-[1fr_150px]"
                            >
                              <div className="min-w-0">
                                <div className="text-sm leading-tight">{p.label}</div>
                                <div className="mt-0.5 truncate font-mono text-[10px] text-muted-foreground">
                                  {p.value}
                                  {fromRole && (
                                    <span className="ml-1 rounded bg-emerald-50 px-1 py-px text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300">
                                      по роли
                                    </span>
                                  )}
                                </div>
                              </div>
                              <Select
                                value={st}
                                onChange={(v) => setPermState(p.value, v as "grant" | "deny" | "role")}
                              >
                                <option value="role">По роли</option>
                                <option value="grant">Разрешить</option>
                                <option value="deny">Запретить</option>
                              </Select>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex justify-end border-t border-border pt-4">
              <button className="btn-primary" onClick={save}>Сохранить</button>
            </div>
          </div>
        )}
      </Modal>

      <Modal open={!!renaming} onClose={() => setRenaming(null)} title="Роли: названия и цвета">
        {renaming && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Отображаемые названия и цвет бейджа роли. Набор прав у роли не меняется.
            </p>
            {(catalog?.all_roles ?? ROLE_ORDER).map((r) => (
              <div key={r} className="flex items-end gap-3">
                <div className="flex-1">
                  <Field label={FALLBACK_ROLE_LABELS[r] ?? r} hint={r}>
                    <input
                      className="input"
                      value={renaming[r] ?? ""}
                      onChange={(e) => setRenaming({ ...renaming, [r]: e.target.value })}
                    />
                  </Field>
                </div>
                <div className="flex flex-col items-center gap-1 pb-0.5">
                  <span className="text-xs text-muted-foreground">Цвет</span>
                  <input
                    type="color"
                    className="h-9 w-11 cursor-pointer rounded border border-border bg-transparent p-0.5"
                    value={renamingColors[r] ?? DEFAULT_ROLE_COLORS[r] ?? "#94a3b8"}
                    onChange={(e) => setRenamingColors({ ...renamingColors, [r]: e.target.value })}
                    title={`Цвет бейджа: ${FALLBACK_ROLE_LABELS[r] ?? r}`}
                  />
                </div>
                <div className="pb-1.5">
                  <span
                    className="badge"
                    style={{
                      backgroundColor: `${renamingColors[r] ?? DEFAULT_ROLE_COLORS[r] ?? "#94a3b8"}22`,
                      color: renamingColors[r] ?? DEFAULT_ROLE_COLORS[r] ?? "#94a3b8",
                      boxShadow: `0 0 0 1px ${renamingColors[r] ?? DEFAULT_ROLE_COLORS[r] ?? "#94a3b8"}55 inset`,
                    }}
                  >
                    {renaming[r] || FALLBACK_ROLE_LABELS[r] || r}
                  </span>
                </div>
              </div>
            ))}
            <div className="flex justify-end border-t border-border pt-4">
              <button className="btn-primary" onClick={saveNames}>Сохранить</button>
            </div>
          </div>
        )}
      </Modal>

      {/* Add custom role modal */}
      <Modal open={!!newRole} onClose={() => setNewRole(null)} title="Новая роль">
        {newRole && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Новая роль изначально не даёт никаких прав — настройте их после создания в «Права ролей».
            </p>
            <Field label="Ключ роли" hint="Латиница в нижнем регистре, цифры и _, 2-32 символа">
              <input
                className="input"
                value={newRole.key}
                onChange={(e) => setNewRole({ ...newRole, key: e.target.value.trim().toLowerCase() })}
                placeholder="curator"
              />
            </Field>
            <Field label="Название">
              <input
                className="input"
                value={newRole.label}
                onChange={(e) => setNewRole({ ...newRole, label: e.target.value })}
                placeholder="Куратор"
              />
            </Field>
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium">Цвет</span>
              <input
                type="color"
                className="h-9 w-11 cursor-pointer rounded border border-border bg-transparent p-0.5"
                value={newRole.color}
                onChange={(e) => setNewRole({ ...newRole, color: e.target.value })}
              />
            </div>
            <div className="flex justify-end border-t border-border pt-4">
              <button className="btn-primary" onClick={addRole} disabled={!newRole.key}>Создать</button>
            </div>
          </div>
        )}
      </Modal>

      {/* Role permissions modal */}
      <Modal
        open={!!rolePermsModal}
        onClose={() => setRolePermsModal(null)}
        title="Права ролей"
        wide
      >
        {rolePermsModal && catalog && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Настройте базовый набор прав каждой роли. <b>По умолчанию</b> — стандартный набор роли.{" "}
              <b>Разрешить</b> — добавить право сверх стандарта. <b>Запретить</b> — убрать право из роли.
              Индивидуальные переопределения для конкретного пользователя всегда имеют приоритет.
            </p>
            {/* Tabs by role */}
            {Object.keys(rolePermsModal).map((role) => (
              <div key={role} className="rounded-lg border border-border">
                <div className="flex items-center justify-between border-b border-border bg-muted/40 px-4 py-2.5">
                  <div>
                    <span className="font-semibold" style={{ color: ROLE_COLORS[role] }}>
                      {ROLE_LABELS[role] ?? role}
                    </span>
                    <span className="ml-2 text-xs text-muted-foreground">({role})</span>
                  </div>
                  {!BUILT_IN_ROLE_KEYS.includes(role) && (
                    <button
                      type="button"
                      className="btn-icon-danger"
                      title="Удалить роль"
                      onClick={() => deleteRole(role)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
                <div className="max-h-64 overflow-y-auto p-4">
                  <div className="space-y-4">
                    {Object.entries(
                      catalog.permissions.reduce<Record<string, typeof catalog.permissions>>(
                        (acc, p) => { (acc[p.group] ??= []).push(p); return acc; },
                        {}
                      )
                    ).map(([group, perms]) => (
                      <div key={group}>
                        <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                          {group}
                        </div>
                        <div className="space-y-1.5">
                          {perms.map((p) => {
                            const st = rolePermStateOf(role, p.value);
                            const defaultHas = (catalog.roles[role] ?? []).includes(p.value);
                            const scope = cityScopeOf(role, p.value);
                            const requiredView = CITY_SCOPE_REQUIRES_VIEW[p.value];
                            const viewScope = requiredView ? cityScopeOf(role, requiredView) : null;
                            const viewDeniesAll = requiredView ? viewScope?.mode === "deny" : false;
                            return (
                              <div
                                key={p.value}
                                className="rounded border border-border/60 p-2"
                              >
                                <div className="grid grid-cols-1 items-center gap-2 sm:grid-cols-[1fr_150px]">
                                  <div className="min-w-0">
                                    <div className="text-sm leading-tight">{p.label}</div>
                                    <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">
                                      {p.value}
                                      {defaultHas && (
                                        <span className="ml-1 rounded bg-emerald-50 px-1 py-px text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300">
                                          по умолч.
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                  <Select
                                    value={st}
                                    onChange={(v) => setRolePermState(role, p.value, v as "grant" | "deny" | "role")}
                                  >
                                    <option value="role">По умолчанию</option>
                                    <option value="grant">Разрешить</option>
                                    <option value="deny">Запретить</option>
                                  </Select>
                                </div>
                                {p.city_scoped && st !== "deny" && (
                                  <div className="mt-2 border-t border-dashed border-border/60 pt-2">
                                    <div className="flex items-center gap-2">
                                      <span className="text-xs text-muted-foreground">По городам:</span>
                                      <div className="w-48">
                                        <Select
                                          value={scope.mode}
                                          onChange={(v) => setCityScopeMode(role, p.value, v as CityScopeMode)}
                                          disabled={viewDeniesAll}
                                        >
                                          <option value="role">По умолчанию</option>
                                          <option value="grant">Разрешить</option>
                                          <option value="grant_selected">Разрешить (выбранные)</option>
                                          <option value="deny">Запретить</option>
                                          <option value="deny_selected">Запретить (выбранные)</option>
                                        </Select>
                                      </div>
                                      {viewDeniesAll && (
                                        <span className="text-[11px] text-rose-500">
                                          Нет прав на просмотр — редактирование недоступно
                                        </span>
                                      )}
                                    </div>
                                    {(scope.mode === "grant_selected" || scope.mode === "deny_selected") && !viewDeniesAll && (
                                      <div className="mt-2 flex max-h-32 flex-wrap gap-1 overflow-y-auto rounded-md border border-border p-1.5">
                                        {(cities?.items ?? [])
                                          .filter((c) => c.kind === "city" || !c.kind)
                                          .filter((c) => {
                                            // For edit-style perms, city choices are limited to cities
                                            // allowed by the matching view permission's scope.
                                            if (!requiredView || !viewScope) return true;
                                            if (viewScope.mode === "role" || viewScope.mode === "grant") return true;
                                            if (viewScope.mode === "grant_selected") return viewScope.cities.includes(c.id);
                                            if (viewScope.mode === "deny_selected") return !viewScope.cities.includes(c.id);
                                            return true;
                                          })
                                          .sort((a, b) => a.name.localeCompare(b.name, "ru"))
                                          .map((c) => {
                                            const active = scope.cities.includes(c.id);
                                            return (
                                              <button
                                                key={c.id}
                                                type="button"
                                                onClick={() => toggleCityScopeCity(role, p.value, c.id)}
                                                className={`rounded-md border px-2 py-0.5 text-[11px] font-medium transition-colors ${
                                                  active
                                                    ? "border-primary bg-primary text-primary-foreground"
                                                    : "border-border bg-card text-muted-foreground hover:border-primary/50 hover:text-foreground"
                                                }`}
                                              >
                                                {c.name}
                                              </button>
                                            );
                                          })}
                                        {(cities?.items ?? []).length === 0 && (
                                          <span className="text-xs text-muted-foreground">Нет городов</span>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))}
            <div className="flex justify-end border-t border-border pt-4">
              <button className="btn-primary" onClick={saveRolePerms}>Сохранить</button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

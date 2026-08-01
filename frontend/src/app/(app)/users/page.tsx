"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { Eye, Pencil, Settings2, Tags, Trash2, UserCircle, ShieldOff, Ban } from "lucide-react";
import { api, fetcher } from "@/lib/api";
import type { Page, User } from "@/lib/types";
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

interface PermissionInfo { value: string; label: string; group: string }
interface PermissionCatalog {
  permissions: PermissionInfo[];
  roles: Record<string, string[]>;
  all_roles: string[];
}

interface UserForm {
  id?: number;
  email: string;
  full_name?: string;
  role: string;
  is_active: boolean;
  language: string;
  telegram_id?: number | null;
  yandex_id?: string | null;
  vk_id?: string | null;
  permissions: { grant?: string[]; deny?: string[] };
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
  telegram_id: null, yandex_id: "", vk_id: "", permissions: {}, password: "",
};

export default function UsersPage() {
  const { data, mutate } = useSWR<Page<User>>("/users?size=100", fetcher);
  const { data: catalog } = useSWR<PermissionCatalog>("/users/permissions", fetcher);
  const { data: roleLabels, mutate: mutateLabels } =
    useSWR<Record<string, string>>("/users/role-labels", fetcher);
  const { data: roleColorsData, mutate: mutateColors } =
    useSWR<Record<string, string>>("/users/role-colors", fetcher);
  const { data: rolePermsData, mutate: mutateRolePerms } =
    useSWR<Record<string, { grant: string[]; deny: string[] }>>("/users/role-permissions", fetcher);
  const { data: me } = useSWR<User>("/auth/me", fetcher, { revalidateOnFocus: false });
  const isSuperAdmin = me?.role === "super_admin";
  const [form, setForm] = useState<UserForm | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Rename-roles dialog: labels + colors together.
  const [renaming, setRenaming] = useState<Record<string, string> | null>(null);
  const [renamingColors, setRenamingColors] = useState<Record<string, string>>({});
  // Role permissions management dialog
  const [rolePermsModal, setRolePermsModal] = useState<
    Record<string, { grant: string[]; deny: string[] }> | null
  >(null);
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
    const base: Record<string, { grant: string[]; deny: string[] }> = {};
    for (const r of catalog?.all_roles ?? []) {
      if (r === "super_admin") continue;
      base[r] = {
        grant: [...(rolePermsData?.[r]?.grant ?? [])],
        deny: [...(rolePermsData?.[r]?.deny ?? [])],
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
    const cur = rolePermsModal[role] ?? { grant: [], deny: [] };
    const g = new Set(cur.grant);
    const d = new Set(cur.deny);
    g.delete(perm); d.delete(perm);
    if (next === "grant") g.add(perm);
    if (next === "deny") d.add(perm);
    setRolePermsModal({ ...rolePermsModal, [role]: { grant: [...g], deny: [...d] } });
  };

  const rolePermStateOf = (role: string, perm: string): "grant" | "deny" | "role" => {
    if (!rolePermsModal) return "role";
    const cur = rolePermsModal[role];
    if (cur?.deny?.includes(perm)) return "deny";
    if (cur?.grant?.includes(perm)) return "grant";
    return "role";
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
      yandex_id: u.yandex_id ?? "",
      vk_id: u.vk_id ?? "",
      permissions: (u.permissions ?? {}) as UserForm["permissions"],
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
    const body: Record<string, unknown> = {
      email: form.email,
      full_name: form.full_name || null,
      role: form.role,
      is_active: form.is_active,
      language: form.language,
      telegram_id: form.telegram_id ?? null,
      yandex_id: form.yandex_id || null,
      vk_id: form.vk_id || null,
      permissions: form.permissions ?? {},
    };
    if (form.password) body.password = form.password;
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
          const ux = u as User & { photo_url?: string | null; yandex_id?: string; vk_id?: string };
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
                {ux.yandex_id && (
                  <span className="flex items-center gap-1">
                    <span className="text-[10px] font-bold">Я</span> {ux.yandex_id}
                  </span>
                )}
                {ux.vk_id && (
                  <span className="flex items-center gap-1">
                    <svg viewBox="0 0 24 24" className="h-3 w-3 shrink-0 fill-[#4680C2]" aria-hidden="true">
                      <path d="M15.684 0H8.316C1.592 0 0 1.592 0 8.316v7.368C0 22.408 1.592 24 8.316 24h7.368C22.408 24 24 22.408 24 15.684V8.316C24 1.592 22.408 0 15.684 0zm3.692 17.123h-1.744c-.66 0-.862-.523-2.049-1.714-1.033-1.01-1.49-1.135-1.744-1.135-.356 0-.458.102-.458.597v1.563c0 .424-.135.678-1.253.678-1.846 0-3.896-1.118-5.335-3.202C4.624 10.857 4.03 8.57 4.03 8.096c0-.254.102-.491.597-.491h1.744c.444 0 .613.204.786.681.863 2.49 2.303 4.675 2.896 4.675.22 0 .322-.102.322-.66V9.948c-.068-1.186-.695-1.287-.695-1.71 0-.204.17-.407.44-.407h2.743c.373 0 .508.204.508.643v3.473c0 .372.17.508.271.508.22 0 .407-.136.813-.542 1.253-1.405 2.151-3.574 2.151-3.574.119-.254.322-.491.764-.491h1.744c.525 0 .643.27.525.643-.22 1.017-2.354 4.031-2.354 4.031-.186.305-.254.440 0 .779.186.254.796.779 1.203 1.253.745.847 1.32 1.558 1.473 2.049.17.49-.085.744-.576.744z"/>
                    </svg>
                    {ux.vk_id}
                  </span>
                )}
                {!u.telegram_id && !ux.yandex_id && !ux.vk_id && (
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
            <div className="grid grid-cols-2 gap-4">
              <Field label="Email"><input className="input" value={form.email} onChange={(e) => upd({ email: e.target.value })} /></Field>
              <Field label="Имя"><input className="input" value={form.full_name ?? ""} onChange={(e) => upd({ full_name: e.target.value })} /></Field>
            </div>
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
              <Field label={form.id ? "Новый пароль" : "Пароль"} hint={form.id ? "Оставьте пустым, чтобы не менять" : "Минимум 8 символов"}>
                <input className="input" type="password" value={form.password ?? ""} onChange={(e) => upd({ password: e.target.value })} />
              </Field>
            </div>
            <div className="rounded-lg border border-border px-4 py-3">
              <div className="mb-3 text-sm font-medium">Привязка аккаунтов</div>
              <div className="grid grid-cols-3 gap-4">
                <Field label="Telegram ID" hint="Числовой ID, для DM">
                  <input className="input" type="number" value={form.telegram_id ?? ""} onChange={(e) => upd({ telegram_id: e.target.value ? Number(e.target.value) : null })} placeholder="123456789" />
                </Field>
                <Field label="Яндекс ID" hint="Для входа через Яндекс">
                  <input className="input" value={form.yandex_id ?? ""} onChange={(e) => upd({ yandex_id: e.target.value })} placeholder="yandex_uid" />
                </Field>
                <Field label="VK ID" hint="Для входа через VK">
                  <input className="input" value={(form as UserForm & { vk_id?: string }).vk_id ?? ""} onChange={(e) => upd({ vk_id: e.target.value } as Partial<UserForm>)} placeholder="vk_uid" />
                </Field>
              </div>
            </div>
            <Checkbox checked={form.is_active} onChange={(v) => upd({ is_active: v })} label="Активен" />

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
                <div className="border-b border-border bg-muted/40 px-4 py-2.5">
                  <span className="font-semibold" style={{ color: ROLE_COLORS[role] }}>
                    {ROLE_LABELS[role] ?? role}
                  </span>
                  <span className="ml-2 text-xs text-muted-foreground">({role})</span>
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
                            return (
                              <div
                                key={p.value}
                                className="grid grid-cols-1 items-center gap-2 rounded border border-border/60 p-2 sm:grid-cols-[1fr_150px]"
                              >
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

"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { Eye, Pencil, Tags, Trash2, UserCircle } from "lucide-react";
import { api, fetcher } from "@/lib/api";
import type { Page, User } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Modal, Field } from "@/components/Modal";
import { Checkbox, Select } from "@/components/Controls";
import { ResizableTable } from "@/components/ResizableTable";
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
  telegram_id: null, yandex_id: "", permissions: {}, password: "",
};

export default function UsersPage() {
  const { data, mutate } = useSWR<Page<User>>("/users?size=100", fetcher);
  const { data: catalog } = useSWR<PermissionCatalog>("/users/permissions", fetcher);
  const { data: roleLabels, mutate: mutateLabels } =
    useSWR<Record<string, string>>("/users/role-labels", fetcher);
  const { data: roleColorsData, mutate: mutateColors } =
    useSWR<Record<string, string>>("/users/role-colors", fetcher);
  const [form, setForm] = useState<UserForm | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Rename-roles dialog: labels + colors together.
  const [renaming, setRenaming] = useState<Record<string, string> | null>(null);
  const [renamingColors, setRenamingColors] = useState<Record<string, string>>({});
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
      yandex_id: (u as User & { yandex_id?: string }).yandex_id ?? "",
      permissions: ((u as User & { permissions?: object }).permissions ?? {}) as UserForm["permissions"],
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

  const remove = async (id: number) => {
    if (!(await confirm({ message: "Удалить пользователя?", danger: true }))) return;
    await api(`/users/${id}`, { method: "DELETE" });
    mutate();
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

      <div className="card overflow-hidden">
        <div className="table-wrap">
        <ResizableTable
          id="users"
          columns={["Email", "Имя", "Роль", "Telegram", "Яндекс", "2FA", "Активен", "Действия"]}
        >
            {data?.items.map((u) => (
              <tr key={u.id} className="border-t border-border">
                <td className="px-4 py-3 font-medium">{u.email}</td>
                <td className="px-4 py-3">{u.full_name ?? "—"}</td>
                <td className="px-4 py-3">
                  <span
                    className="badge"
                    style={{
                      backgroundColor: `${ROLE_COLORS[u.role] ?? "#94a3b8"}22`,
                      color: ROLE_COLORS[u.role] ?? "#94a3b8",
                      borderColor: `${ROLE_COLORS[u.role] ?? "#94a3b8"}55`,
                    }}
                  >
                    {ROLE_LABELS[u.role] ?? u.role}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted-foreground">{u.telegram_id ?? "—"}</td>
                <td className="px-4 py-3 text-muted-foreground">{(u as User & { yandex_id?: string }).yandex_id || "—"}</td>
                <td className="px-4 py-3">{u.is_2fa_enabled ? "✓" : "—"}</td>
                <td className="px-4 py-3">{u.is_active ? "Да" : "Нет"}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-center gap-1.5">
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
                    <button className="btn-icon-danger" title="Удалить" onClick={() => remove(u.id)}>
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
        </ResizableTable>
        </div>
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
                  {(catalog?.all_roles ?? Object.keys(ROLE_LABELS)).map((r) => (
                    <option key={r} value={r}>{ROLE_LABELS[r] ?? r}</option>
                  ))}
                </Select>
              </Field>
              <Field label={form.id ? "Новый пароль" : "Пароль"} hint={form.id ? "Оставьте пустым, чтобы не менять" : "Минимум 8 символов"}>
                <input className="input" type="password" value={form.password ?? ""} onChange={(e) => upd({ password: e.target.value })} />
              </Field>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <Field label="Telegram ID" hint="Для модерации из бота">
                <input className="input" type="number" value={form.telegram_id ?? ""} onChange={(e) => upd({ telegram_id: e.target.value ? Number(e.target.value) : null })} />
              </Field>
              <Field label="Яндекс ID" hint="Для входа через Яндекс">
                <input className="input" value={form.yandex_id ?? ""} onChange={(e) => upd({ yandex_id: e.target.value })} />
              </Field>
              <Field label="Язык">
                <Select value={form.language} onChange={(v) => upd({ language: v })}>
                  <option value="ru">ru</option>
                  <option value="en">en</option>
                </Select>
              </Field>
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
                      borderColor: `${renamingColors[r] ?? DEFAULT_ROLE_COLORS[r] ?? "#94a3b8"}55`,
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
    </div>
  );
}

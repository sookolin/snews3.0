"use client";

import { useState } from "react";
import useSWR from "swr";
import { Pencil, Trash2 } from "lucide-react";
import { api, fetcher } from "@/lib/api";
import type { Page, User } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Modal, Field } from "@/components/Modal";
import { Checkbox, Select } from "@/components/Controls";

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

const ROLE_LABELS: Record<string, string> = {
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
  const [form, setForm] = useState<UserForm | null>(null);
  const [error, setError] = useState<string | null>(null);

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
    if (!confirm("Удалить пользователя?")) return;
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
      <PageHeader title="Пользователи" action={<button className="btn-primary" onClick={openNew}>Добавить</button>} />

      <div className="card overflow-hidden">
        <div className="table-wrap">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-muted-foreground">
            <tr>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Имя</th>
              <th className="px-4 py-3">Роль</th>
              <th className="px-4 py-3">Telegram</th>
              <th className="px-4 py-3">Яндекс</th>
              <th className="px-4 py-3">2FA</th>
              <th className="px-4 py-3">Активен</th>
              <th className="px-4 py-3 text-right">Действия</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((u) => (
              <tr key={u.id} className="border-t border-border">
                <td className="px-4 py-3 font-medium">{u.email}</td>
                <td className="px-4 py-3">{u.full_name ?? "—"}</td>
                <td className="px-4 py-3">
                  <span className="badge bg-slate-50 text-slate-700 ring-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700">
                    {ROLE_LABELS[u.role] ?? u.role}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted-foreground">{u.telegram_id ?? "—"}</td>
                <td className="px-4 py-3 text-muted-foreground">{(u as User & { yandex_id?: string }).yandex_id || "—"}</td>
                <td className="px-4 py-3">{u.is_2fa_enabled ? "✓" : "—"}</td>
                <td className="px-4 py-3">{u.is_active ? "Да" : "Нет"}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-1.5">
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
          </tbody>
        </table>
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
                <select className="input" value={form.language} onChange={(e) => upd({ language: e.target.value })}>
                  <option value="ru">ru</option>
                  <option value="en">en</option>
                </select>
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
    </div>
  );
}

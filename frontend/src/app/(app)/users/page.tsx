"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { Page, User } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";

const ROLES = ["super_admin", "admin", "moderator", "editor", "reviewer"];

export default function UsersPage() {
  const { data, mutate } = useSWR<Page<User>>("/users?size=100", fetcher);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ email: "", full_name: "", password: "", role: "reviewer" });
  const [error, setError] = useState<string | null>(null);

  const create = async () => {
    setError(null);
    try {
      await api("/users", { method: "POST", body: JSON.stringify(form) });
      setForm({ email: "", full_name: "", password: "", role: "reviewer" });
      setOpen(false);
      mutate();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const remove = async (id: number) => {
    if (!confirm("Удалить пользователя?")) return;
    await api(`/users/${id}`, { method: "DELETE" });
    mutate();
  };

  return (
    <div>
      <PageHeader
        title="Пользователи"
        action={<button className="btn-primary" onClick={() => setOpen(!open)}>Добавить</button>}
      />
      {open && (
        <div className="card mb-5 space-y-3 p-5">
          {error && <p className="text-sm text-red-600">{error}</p>}
          <input className="input" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <input className="input" placeholder="Имя" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
          <input className="input" type="password" placeholder="Пароль (мин. 8)" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <select className="input max-w-[200px]" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <button className="btn-primary" onClick={create}>Создать</button>
        </div>
      )}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-muted-foreground">
            <tr>
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Имя</th>
              <th className="px-4 py-3">Роль</th>
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
                <td className="px-4 py-3"><span className="badge bg-slate-100 text-slate-700">{u.role}</span></td>
                <td className="px-4 py-3">{u.is_2fa_enabled ? "✓" : "—"}</td>
                <td className="px-4 py-3">{u.is_active ? "Да" : "Нет"}</td>
                <td className="px-4 py-3 text-right">
                  <button className="btn-danger py-1" onClick={() => remove(u.id)}>Удалить</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

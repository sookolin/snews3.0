"use client";

import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { City, Page } from "@/lib/types";
import { Pencil, RefreshCw, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Modal, Field } from "@/components/Modal";
import { Checkbox, Select } from "@/components/Controls";
import { ResizableTable } from "@/components/ResizableTable";
import { useToast } from "@/components/Toast";
import { confirm } from "@/components/ConfirmDialog";

interface Channel {
  id: number;
  city_id: number;
  title: string;
  chat_id: string;
  username?: string | null;
  avatar_url?: string | null;
  topic_id?: number | null;
  publish_mode: string;
  is_active: boolean;
  min_interval_seconds: number;
  template_id?: number | null;
  watermark_id?: number | null;
}

interface Template { id: number; name: string }
interface Watermark { id: number; name: string }

/** Fields Telegram owns — never sent back on save, always parsed. */
const PARSED_FIELDS = ["username", "avatar_url"] as const;

const MODES = [
  { value: "immediate", label: "Сразу после одобрения" },
  { value: "draft", label: "Черновик" },
  { value: "scheduled", label: "Отложенная публикация" },
  { value: "manual", label: "Только вручную" },
];

const EMPTY: Partial<Channel> = {
  title: "", chat_id: "", publish_mode: "immediate", is_active: true, min_interval_seconds: 0,
};

export default function ChannelsPage() {
  const { data, mutate } = useSWR<Page<Channel>>("/channels?size=100", fetcher);
  const { data: cities } = useSWR<Page<City>>("/cities?size=100", fetcher);
  const { data: templates } = useSWR<Page<Template>>("/templates?size=100", fetcher);
  const { data: watermarks } = useSWR<Page<Watermark>>("/watermarks?size=100", fetcher);
  const [form, setForm] = useState<Partial<Channel> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();
  //: Guards the one-shot identity refresh below against SWR re-renders.
  const syncedRef = useRef(false);

  const cityName = (id: number) => cities?.items.find((c) => c.id === id)?.name ?? `#${id}`;

  const openNew = () => {
    setForm({ ...EMPTY, city_id: cities?.items[0]?.id });
    setError(null);
  };
  const openEdit = (c: Channel) => { setForm({ ...c }); setError(null); };
  const upd = (patch: Partial<Channel>) => setForm((f) => ({ ...f, ...patch }));

  const save = async () => {
    if (!form) return;
    setError(null);
    if (!form.city_id) { setError("Выберите город"); return; }
    try {
      const payload: Partial<Channel> = { ...form };
      for (const field of PARSED_FIELDS) delete payload[field];
      if (form.id) {
        await api(`/channels/${form.id}`, { method: "PATCH", body: JSON.stringify(payload) });
      } else {
        await api("/channels", { method: "POST", body: JSON.stringify(payload) });
      }
      setForm(null);
      mutate();
      toast.success(form.id ? "Канал обновлён" : "Канал привязан");
    } catch (e) {
      setError((e as Error).message);
      toast.error((e as Error).message);
    }
  };

  const remove = async (id: number) => {
    if (!(await confirm({ message: "Удалить канал?", danger: true }))) return;
    try {
      await api(`/channels/${id}`, { method: "DELETE" });
      mutate();
      toast.success("Канал удалён");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  /**
   * Pull the real title/@username/avatar from Telegram, so previews show the
   * actual channel identity instead of hand-typed values.
   */
  const sync = async (id: number) => {
    try {
      await api(`/channels/${id}/sync`, { method: "POST" });
      mutate();
      toast.success("Название и аватарка обновлены из Telegram");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  /**
   * Refresh the parsed identity of every channel once the page opens, so the
   * removed manual fields stay accurate without any user action.
   */
  useEffect(() => {
    if (!data?.items.length || syncedRef.current) return;
    syncedRef.current = true;
    (async () => {
      let changed = false;
      for (const c of data.items) {
        if (c.username && c.avatar_url) continue;
        try {
          await api(`/channels/${c.id}/sync`, { method: "POST" });
          changed = true;
        } catch {
          // A single unreachable channel must not block the rest.
        }
      }
      if (changed) mutate();
    })();
  }, [data, mutate]);

  return (
    <div>
      <PageHeader
        title="Telegram каналы"
        action={<button className="btn-primary" onClick={openNew}>Привязать канал</button>}
      />

      {cities && cities.items.length === 0 && (
        <p className="mb-4 rounded-md bg-amber-50 p-3 text-sm text-amber-800">
          Сначала создайте хотя бы один город на вкладке «Города».
        </p>
      )}

      <div className="card overflow-hidden">
        <div className="table-wrap">
        <ResizableTable
          id="channels"
          columns={["Название", "Chat ID", "Раздел", "Режим", "Активен", "Действия"]}
        >
            {data?.items.map((c) => (
              <tr key={c.id} className="border-t border-border">
                <td className="px-4 py-3 font-medium">{c.title}</td>
                <td className="px-4 py-3 font-mono text-xs">{c.chat_id}{c.topic_id ? ` / ${c.topic_id}` : ""}</td>
                <td className="px-4 py-3">{cityName(c.city_id)}</td>
                <td className="px-4 py-3">{MODES.find((m) => m.value === c.publish_mode)?.label ?? c.publish_mode}</td>
                <td className="px-4 py-3">{c.is_active ? "Да" : "Нет"}</td>
                <td className="px-4 py-3">
                  <div className="flex justify-center gap-2">
                    <button className="btn-icon" title="Изменить" onClick={() => openEdit(c)}>
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button
                      className="btn-icon-primary"
                      title="Обновить название и аватарку из Telegram"
                      onClick={() => sync(c.id)}
                    >
                      <RefreshCw className="h-4 w-4" />
                    </button>
                    <button className="btn-icon-danger" title="Удалить" onClick={() => remove(c.id)}>
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">Нет привязанных каналов</td></tr>
            )}
        </ResizableTable>
        </div>
      </div>

      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "Изменить канал" : "Привязать канал к городу"}>
        {form && (
          <div className="space-y-4">
            {error && <p className="rounded-md bg-red-50 p-2 text-sm text-red-600">{error}</p>}
            <Field label="Город" hint="Новости этого города публикуются в канал">
              <Select value={form.city_id ?? ""} onChange={(v) => upd({ city_id: Number(v) })}>
                <option value="" disabled>Выберите город</option>
                {cities?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </Select>
            </Field>
            <Field label="Название канала"><input className="input" value={form.title ?? ""} onChange={(e) => upd({ title: e.target.value })} /></Field>
            <Field label="Chat ID / @username" hint="Например -1001234567890 или @mychannel. Бот должен быть админом канала.">
              <input className="input font-mono" value={form.chat_id ?? ""} onChange={(e) => upd({ chat_id: e.target.value })} />
            </Field>
            {/* @username and the avatar are parsed from Telegram automatically
                (on page load and via the refresh button), so they are not
                editable here. */}
            <div className="grid grid-cols-2 gap-4">
              <Field label="Topic ID" hint="Только для форум-групп (опционально)">
                <input type="number" className="input" value={form.topic_id ?? ""} onChange={(e) => upd({ topic_id: e.target.value ? Number(e.target.value) : null })} />
              </Field>
              <Field label="Мин. интервал (сек)" hint="Пауза между постами">
                <input type="number" className="input" value={form.min_interval_seconds ?? 0} onChange={(e) => upd({ min_interval_seconds: Number(e.target.value) })} />
              </Field>
            </div>
            <Field label="Режим публикации">
              <Select value={form.publish_mode ?? "immediate"} onChange={(v) => upd({ publish_mode: v })}>
                {MODES.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
              </Select>
            </Field>
            <Field label="Шаблон" hint="Переопределяет шаблон города для этого канала">
              <Select
                value={form.template_id ?? ""}
                onChange={(v) => upd({ template_id: v ? Number(v) : null })}
              >
                <option value="">По умолчанию</option>
                {templates?.items.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </Select>
            </Field>
            <Field label="Водяной знак" hint="Накладывается на медиа при публикации в этот канал">
              <Select
                value={form.watermark_id ?? ""}
                onChange={(v) => upd({ watermark_id: v ? Number(v) : null })}
              >
                <option value="">По умолчанию</option>
                {watermarks?.items.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </Select>
            </Field>
            <Checkbox
              checked={form.is_active ?? true}
              onChange={(v) => upd({ is_active: v })}
              label="Активен"
            />
            <div className="flex justify-end border-t border-border pt-4">
              <button className="btn-primary" onClick={save}>Сохранить</button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

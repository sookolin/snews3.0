"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { Page } from "@/lib/types";
import { Pencil, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Modal, Field } from "@/components/Modal";
import { Checkbox, Select } from "@/components/Controls";
import { confirm } from "@/components/ConfirmDialog";

interface Watermark {
  id: number;
  name: string;
  is_default: boolean;
  is_active: boolean;
  logo_path?: string | null;
  text?: string | null;
  position: string;
  margin_x: number;
  margin_y: number;
  scale: number;
  opacity: number;
  font_size: number;
  color: string;
  shadow: boolean;
  shadow_color: string;
}

const POSITIONS = [
  { value: "top-left", label: "Сверху слева" },
  { value: "top-right", label: "Сверху справа" },
  { value: "bottom-left", label: "Снизу слева" },
  { value: "bottom-right", label: "Снизу справа" },
  { value: "center", label: "По центру" },
];

const EMPTY: Partial<Watermark> = {
  name: "", text: "", position: "bottom-right", margin_x: 20, margin_y: 20,
  scale: 0.18, opacity: 0.75, font_size: 32, color: "#FFFFFF", shadow: true,
  shadow_color: "#000000", is_default: false, is_active: true,
};

export default function WatermarksPage() {
  const { data, mutate } = useSWR<Page<Watermark>>("/watermarks?size=100", fetcher);
  const [form, setForm] = useState<Partial<Watermark> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [logoFile, setLogoFile] = useState<File | null>(null);

  const openNew = () => { setForm({ ...EMPTY }); setLogoFile(null); setError(null); };
  const openEdit = (w: Watermark) => { setForm({ ...w }); setLogoFile(null); setError(null); };
  const upd = (patch: Partial<Watermark>) => setForm((f) => ({ ...f, ...patch }));

  const save = async () => {
    if (!form) return;
    setError(null);
    try {
      let saved: Watermark;
      if (form.id) {
        saved = await api<Watermark>(`/watermarks/${form.id}`, { method: "PATCH", body: JSON.stringify(form) });
      } else {
        saved = await api<Watermark>("/watermarks", { method: "POST", body: JSON.stringify(form) });
      }
      if (logoFile) {
        const fd = new FormData();
        fd.append("file", logoFile);
        await api(`/watermarks/${saved.id}/logo`, { method: "POST", body: fd });
      }
      setForm(null);
      mutate();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const remove = async (id: number) => {
    if (!(await confirm({ message: "Удалить водяной знак?", danger: true }))) return;
    await api(`/watermarks/${id}`, { method: "DELETE" });
    mutate();
  };

  return (
    <div>
      <PageHeader
        title="Водяной знак"
        action={<button className="btn-primary" onClick={openNew}>Создать профиль</button>}
      />
      <p className="mb-4 text-sm text-muted-foreground">
        Водяной знак автоматически накладывается на фото и видео перед публикацией.
        Профиль «по умолчанию» применяется ко всем новостям (если не отключено в редакторе).
      </p>

      <div className="grid gap-4 md:grid-cols-3">
        {data?.items.map((w) => (
          <div key={w.id} className="card p-5">
            <div className="flex items-center justify-between">
              <h3 className="font-medium">{w.name}</h3>
              {w.is_default && (
                <span className="badge bg-emerald-100 text-emerald-700">по умолчанию</span>
              )}
            </div>
            <dl className="mt-3 space-y-1 text-sm text-muted-foreground">
              <div>Текст: {w.text || "—"}</div>
              <div>Позиция: {POSITIONS.find((p) => p.value === w.position)?.label}</div>
              <div>Прозрачность: {Math.round(w.opacity * 100)}%</div>
              <div>Масштаб: {Math.round(w.scale * 100)}%</div>
              <div>Логотип: {w.logo_path ? "загружен" : "нет"}</div>
            </dl>
            <div className="mt-3 flex gap-2">
              <button className="btn-icon" title="Редактировать" onClick={() => openEdit(w)}>
                <Pencil className="h-4 w-4" />
              </button>
              <button className="btn-icon-danger" title="Удалить" onClick={() => remove(w.id)}>
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
      </div>

      <Modal open={!!form} onClose={() => setForm(null)} title={form?.id ? "Редактировать водяной знак" : "Новый водяной знак"} wide>
        {form && (
          <div className="space-y-4">
            {error && <p className="rounded-md bg-red-50 p-2 text-sm text-red-600">{error}</p>}
            <div className="grid grid-cols-2 gap-4">
              <Field label="Название"><input className="input" value={form.name ?? ""} onChange={(e) => upd({ name: e.target.value })} /></Field>
              <Field label="Позиция">
                <Select value={form.position ?? "bottom_right"} onChange={(v) => upd({ position: v })}>
                  {POSITIONS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                </Select>
              </Field>
            </div>
            <Field label="Текст" hint="Если задан логотип — используется логотип">
              <input className="input" value={form.text ?? ""} onChange={(e) => upd({ text: e.target.value })} />
            </Field>
            <Field label="Логотип (PNG/SVG)" hint="Загрузите файл — он переопределит текст">
              <input type="file" accept="image/*,.svg" className="input" onChange={(e) => setLogoFile(e.target.files?.[0] ?? null)} />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label={`Прозрачность: ${Math.round((form.opacity ?? 0.75) * 100)}%`}>
                <input type="range" min={0} max={1} step={0.05} value={form.opacity ?? 0.75} onChange={(e) => upd({ opacity: Number(e.target.value) })} className="w-full" />
              </Field>
              <Field label={`Масштаб: ${Math.round((form.scale ?? 0.18) * 100)}%`}>
                <input type="range" min={0.02} max={1} step={0.02} value={form.scale ?? 0.18} onChange={(e) => upd({ scale: Number(e.target.value) })} className="w-full" />
              </Field>
            </div>
            <div className="grid grid-cols-3 gap-4">
              <Field label="Отступ X"><input type="number" className="input" value={form.margin_x ?? 20} onChange={(e) => upd({ margin_x: Number(e.target.value) })} /></Field>
              <Field label="Отступ Y"><input type="number" className="input" value={form.margin_y ?? 20} onChange={(e) => upd({ margin_y: Number(e.target.value) })} /></Field>
              <Field label="Размер шрифта"><input type="number" className="input" value={form.font_size ?? 32} onChange={(e) => upd({ font_size: Number(e.target.value) })} /></Field>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Цвет текста">
                <input type="color" className="input h-10" value={form.color ?? "#FFFFFF"} onChange={(e) => upd({ color: e.target.value })} />
              </Field>
              <Field label="Цвет тени">
                <input type="color" className="input h-10" value={form.shadow_color ?? "#000000"} onChange={(e) => upd({ shadow_color: e.target.value })} />
              </Field>
            </div>
            <div className="flex gap-6">
              <Checkbox checked={!!form.shadow} onChange={(v) => upd({ shadow: v })} label="Тень" />
              <Checkbox
                checked={!!form.is_default}
                onChange={(v) => upd({ is_default: v })}
                label="По умолчанию"
              />
              <Checkbox
                checked={form.is_active ?? true}
                onChange={(v) => upd({ is_active: v })}
                label="Активен"
              />
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

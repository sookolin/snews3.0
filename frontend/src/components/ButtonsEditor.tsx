"use client";

import { Plus, Trash2 } from "lucide-react";
import type { PreviewButton } from "./TelegramPreview";
import { Select } from "./Controls";

interface Props {
  value: PreviewButton[][];
  onChange: (rows: PreviewButton[][]) => void;
}

// Telegram Bot API 9.4 only supports these button styles.
const COLORS: { value: string; label: string; className: string }[] = [
  { value: "", label: "Стандарт", className: "bg-sky-100 text-sky-700" },
  { value: "primary", label: "Синяя (primary)", className: "bg-blue-600 text-white" },
  { value: "success", label: "Зелёная (success)", className: "bg-green-600 text-white" },
  { value: "danger", label: "Красная (danger)", className: "bg-red-600 text-white" },
];

/** Editor for Telegram inline keyboard buttons (rows of {text, url, color}). */
export function ButtonsEditor({ value, onChange }: Props) {
  const rows = value ?? [];

  const addRow = () => onChange([...rows, [{ text: "", url: "", color: "" }]]);
  const removeRow = (ri: number) => onChange(rows.filter((_, i) => i !== ri));
  const addCell = (ri: number) =>
    onChange(rows.map((r, i) => (i === ri ? [...r, { text: "", url: "", color: "" }] : r)));
  const removeCell = (ri: number, ci: number) =>
    onChange(rows.map((r, i) => (i === ri ? r.filter((_, j) => j !== ci) : r)));
  const setCell = (ri: number, ci: number, patch: Partial<PreviewButton>) =>
    onChange(
      rows.map((r, i) =>
        i === ri ? r.map((c, j) => (j === ci ? { ...c, ...patch } : c)) : r
      )
    );

  return (
    <div className="space-y-3">
      {rows.map((row, ri) => (
        <div key={ri} className="rounded-md border border-border p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs text-muted-foreground">Ряд {ri + 1}</span>
            <button type="button" className="text-red-600" onClick={() => removeRow(ri)}>
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
          <div className="space-y-2">
            {row.map((cell, ci) => (
              <div key={ci} className="flex flex-wrap gap-2">
                <input
                  className="input flex-1"
                  placeholder="Текст кнопки"
                  value={cell.text}
                  onChange={(e) => setCell(ri, ci, { text: e.target.value })}
                />
                <input
                  className="input flex-1"
                  placeholder="https://ссылка"
                  value={cell.url}
                  onChange={(e) => setCell(ri, ci, { url: e.target.value })}
                />
                <div className="w-32">
                  <Select
                    value={cell.color ?? ""}
                    onChange={(v) => setCell(ri, ci, { color: v })}
                  >
                    {COLORS.map((c) => (
                      <option key={c.value} value={c.value}>{c.label}</option>
                    ))}
                  </Select>
                </div>
                <button type="button" className="btn-outline px-2" onClick={() => removeCell(ri, ci)}>
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
          <button type="button" className="btn-outline mt-2 py-1 text-xs" onClick={() => addCell(ri)}>
            <Plus className="h-3 w-3" /> Кнопка в ряд
          </button>
        </div>
      ))}
      <button type="button" className="btn-outline py-1" onClick={addRow}>
        <Plus className="h-4 w-4" /> Добавить ряд кнопок
      </button>
    </div>
  );
}

export { COLORS as BUTTON_COLORS };

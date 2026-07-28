"use client";

import { useState } from "react";
import useSWR from "swr";
import { useRouter } from "next/navigation";
import { PlusCircle } from "lucide-react";
import { api, fetcher } from "@/lib/api";
import type { City, Page } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Field } from "@/components/Modal";
import { Select } from "@/components/Controls";

/**
 * Manual post creation.
 *
 * Only the minimum needed to create the draft is asked here; the user is then
 * redirected into the full news editor, so creating a post has exactly the same
 * capabilities as editing one (media, buttons, emoji, geo, template, source,
 * author, scheduling…).
 */
export default function ComposePage() {
  const router = useRouter();
  const { data: cities } = useSWR<Page<City>>("/cities?size=100", fetcher);
  const [cityId, setCityId] = useState("");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const create = async () => {
    setError(null);
    if (!text.trim()) {
      setError("Введите текст новости");
      return;
    }
    setSaving(true);
    try {
      const created = await api<{ id: number }>("/news", {
        method: "POST",
        body: JSON.stringify({
          original_title: title,
          original_text: text,
          city_id: cityId ? Number(cityId) : null,
          origin: "user",
        }),
      });
      // Continue in the full editor.
      router.push(`/news/${created.id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-2xl">
      <PageHeader title="Создать пост" />

      <div className="card space-y-4 p-5">
        {error && (
          <p className="rounded-md bg-rose-50 p-2 text-sm text-rose-600 dark:bg-rose-950/40">
            {error}
          </p>
        )}

        <p className="text-sm text-muted-foreground">
          Заполните основу — дальше откроется полный редактор: вложения, кнопки,
          эмодзи, геолокация, шаблон, источник, автор и публикация.
        </p>

        <Field label="Город" hint="Определяет каналы публикации и топик модерации">
          <Select value={cityId} onChange={setCityId}>
            <option value="">— выберите город —</option>
            {cities?.items.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </Select>
        </Field>

        <Field label="Заголовок">
          <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>

        <Field label="Текст" hint="Разметку и оформление можно будет добавить в редакторе">
          <textarea
            className="input min-h-[160px]"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </Field>

        <div className="flex justify-end border-t border-border pt-4">
          <button className="btn-primary" disabled={saving} onClick={create}>
            <PlusCircle className="h-4 w-4" />
            {saving ? "Создание…" : "Создать и открыть редактор"}
          </button>
        </div>
      </div>
    </div>
  );
}

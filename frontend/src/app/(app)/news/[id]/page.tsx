"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { NewsItem } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";

interface NewsDetail extends NewsItem {
  text?: string;
  original_text: string;
  original_url?: string;
  is_spoiler: boolean;
  apply_watermark: boolean;
  media: {
    id: number; type: string; caption?: string; is_spoiler: boolean;
    is_enabled: boolean; remote_url?: string; processed_path?: string;
  }[];
}

export default function NewsEditorPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [news, setNews] = useState<NewsDetail | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setNews(await api<NewsDetail>(`/news/${id}`));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => { load(); /* eslint-disable-line */ }, [id]);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!news) return <p className="text-muted-foreground">Загрузка…</p>;

  const update = (patch: Partial<NewsDetail>) => setNews({ ...news, ...patch });

  const save = async () => {
    setSaving(true);
    try {
      await api(`/news/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: news.title,
          text: news.text,
          is_spoiler: news.is_spoiler,
          apply_watermark: news.apply_watermark,
          edit_comment: "Edited via admin editor",
        }),
      });
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const publish = async () => {
    setSaving(true);
    try {
      await api(`/news/${id}/publish`, { method: "POST" });
      router.push("/news");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-3xl">
      <PageHeader
        title={`Новость #${news.id}`}
        action={<StatusBadge status={news.status} />}
      />

      <div className="card space-y-4 p-5">
        <label className="block">
          <span className="text-sm text-muted-foreground">Заголовок</span>
          <input className="input mt-1" value={news.title ?? ""} onChange={(e) => update({ title: e.target.value })} />
        </label>

        <label className="block">
          <span className="text-sm text-muted-foreground">Текст</span>
          <textarea
            className="input mt-1 min-h-[220px] font-mono"
            value={news.text ?? ""}
            onChange={(e) => update({ text: e.target.value })}
          />
        </label>

        <div className="flex gap-6">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={news.is_spoiler} onChange={(e) => update({ is_spoiler: e.target.checked })} />
            Спойлер
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={news.apply_watermark} onChange={(e) => update({ apply_watermark: e.target.checked })} />
            Водяной знак
          </label>
        </div>

        {news.media.length > 0 && (
          <div>
            <div className="mb-2 text-sm text-muted-foreground">Вложения ({news.media.length})</div>
            <div className="flex flex-wrap gap-3">
              {news.media.map((m) => (
                <div key={m.id} className="rounded-md border border-border p-2 text-xs">
                  <div className="font-medium">{m.type}</div>
                  {m.remote_url && <div className="max-w-[160px] truncate text-muted-foreground">{m.remote_url}</div>}
                </div>
              ))}
            </div>
          </div>
        )}

        {news.original_url && (
          <a href={news.original_url} target="_blank" rel="noreferrer" className="text-sm text-primary underline">
            Открыть оригинал
          </a>
        )}

        <div className="flex gap-3 border-t border-border pt-4">
          <button className="btn-outline" disabled={saving} onClick={save}>Сохранить</button>
          <button className="btn-primary" disabled={saving} onClick={publish}>Опубликовать</button>
        </div>
      </div>
    </div>
  );
}

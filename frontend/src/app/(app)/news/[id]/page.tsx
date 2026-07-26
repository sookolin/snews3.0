"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { NewsItem } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { TelegramPreview, type PreviewButton } from "@/components/TelegramPreview";
import { ButtonsEditor } from "@/components/ButtonsEditor";
import { MediaManager, mediaUrl, type MediaAsset } from "@/components/MediaManager";
import { YandexMapPicker } from "@/components/YandexMapPicker";

interface NewsDetail extends NewsItem {
  text?: string;
  original_text: string;
  original_url?: string;
  is_spoiler: boolean;
  apply_watermark: boolean;
  latitude?: number | null;
  longitude?: number | null;
  location_title?: string | null;
  location_address?: string | null;
  buttons?: PreviewButton[][];
  media: MediaAsset[];
}

interface City { id: number; name: string }
interface Channel { id: number; city_id: number; title: string; username?: string; avatar_url?: string }

export default function NewsEditorPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [news, setNews] = useState<NewsDetail | null>(null);
  const [city, setCity] = useState<City | null>(null);
  const [channel, setChannel] = useState<Channel | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showMap, setShowMap] = useState(false);

  const load = async () => {
    try {
      const n = await api<NewsDetail>(`/news/${id}`);
      setNews(n);
      if (n.city_id) {
        try { setCity(await api<City>(`/cities/${n.city_id}`)); } catch {}
        try {
          const ch = await api<{ items: Channel[] }>(`/channels?city_id=${n.city_id}`);
          setChannel(ch.items[0] ?? null);
        } catch {}
      }
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => { load(); /* eslint-disable-line */ }, [id]);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!news) return <p className="text-muted-foreground">Загрузка…</p>;

  const update = (patch: Partial<NewsDetail>) => setNews((n) => (n ? { ...n, ...patch } : n));

  const save = async () => {
    setSaving(true);
    try {
      await api(`/news/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: news.title,
          text: news.text,
          apply_watermark: news.apply_watermark,
          latitude: news.latitude ?? null,
          longitude: news.longitude ?? null,
          location_title: news.location_title ?? null,
          location_address: news.location_address ?? null,
          buttons: news.buttons ?? [],
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
    <div className="grid gap-6 lg:grid-cols-[1fr_400px]">
      <div>
        <PageHeader title={`Новость #${news.id}`} action={<StatusBadge status={news.status} />} />

        <div className="card space-y-4 p-5">
          {city && (
            <div className="rounded-md bg-muted px-3 py-2 text-sm">
              Публикуется в город: <span className="font-medium">{city.name}</span>
              {channel && <> · канал <span className="font-medium">{channel.title}</span></>}
            </div>
          )}
          {news.origin === "user" && (
            <div className="rounded-md bg-sky-50 px-3 py-2 text-sm dark:bg-sky-950/30">
              Предложено пользователем ·{" "}
              <span className="font-medium">
                {news.submitted_anonymously ? "Аноним" : (news.author_name || "Пользователь")}
              </span>
            </div>
          )}

          <label className="block">
            <span className="text-sm text-muted-foreground">Заголовок</span>
            <input className="input mt-1" value={news.title ?? ""} onChange={(e) => update({ title: e.target.value })} />
          </label>

          <label className="block">
            <span className="text-sm text-muted-foreground">Текст (HTML Telegram)</span>
            <textarea
              className="input mt-1 min-h-[200px] font-mono"
              value={news.text ?? ""}
              onChange={(e) => update({ text: e.target.value })}
            />
          </label>

          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={news.apply_watermark} onChange={(e) => update({ apply_watermark: e.target.checked })} />
            Водяной знак
          </label>

          {/* Media */}
          <div>
            <div className="mb-2 text-sm font-medium">Вложения ({news.media.length})</div>
            <MediaManager newsId={news.id} media={news.media} onChange={load} />
          </div>

          {/* Buttons */}
          <div>
            <div className="mb-2 text-sm font-medium">Кнопки под постом</div>
            <ButtonsEditor value={news.buttons ?? []} onChange={(b) => update({ buttons: b })} />
          </div>

          {/* Geolocation */}
          <div className="rounded-md border border-border p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-medium">Геолокация</span>
              <button className="btn-outline py-1 text-xs" onClick={() => setShowMap((v) => !v)}>
                {showMap ? "Скрыть карту" : "Выбрать на Яндекс.Картах"}
              </button>
            </div>
            {showMap && (
              <div className="mb-3">
                <YandexMapPicker
                  latitude={news.latitude}
                  longitude={news.longitude}
                  onPick={(lat, lon, addr) =>
                    update({ latitude: lat, longitude: lon, location_address: addr ?? news.location_address })
                  }
                />
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <input className="input" type="number" step="any" placeholder="Широта" value={news.latitude ?? ""} onChange={(e) => update({ latitude: e.target.value === "" ? null : Number(e.target.value) })} />
              <input className="input" type="number" step="any" placeholder="Долгота" value={news.longitude ?? ""} onChange={(e) => update({ longitude: e.target.value === "" ? null : Number(e.target.value) })} />
              <input className="input" placeholder="Название места" value={news.location_title ?? ""} onChange={(e) => update({ location_title: e.target.value })} />
              <input className="input" placeholder="Адрес" value={news.location_address ?? ""} onChange={(e) => update({ location_address: e.target.value })} />
            </div>
          </div>

          <div className="flex gap-3 border-t border-border pt-4">
            <button className="btn-outline" disabled={saving} onClick={save}>Сохранить</button>
            <button className="btn-primary" disabled={saving} onClick={publish}>Опубликовать</button>
          </div>
        </div>
      </div>

      {/* Live Telegram preview */}
      <div className="lg:sticky lg:top-6 lg:self-start">
        <div className="mb-2 text-sm font-medium">Предпросмотр</div>
        <TelegramPreview
          channelName={channel?.title || city?.name || "Канал"}
          channelAvatar={channel?.avatar_url}
          title={news.title ?? news.original_title ?? ""}
          text={news.text ?? news.original_text ?? ""}
          media={news.media.filter((m) => m.is_enabled).map((m) => ({ url: mediaUrl(m), type: m.type, spoiler: m.is_spoiler }))}
          buttons={news.buttons ?? []}
          locationTitle={news.location_title}
        />
      </div>
    </div>
  );
}

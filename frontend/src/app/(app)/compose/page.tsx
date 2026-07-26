"use client";

import { useState } from "react";
import useSWR from "swr";
import { useRouter } from "next/navigation";
import { api, fetcher } from "@/lib/api";
import type { City, Page } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { TelegramPreview, type PreviewButton } from "@/components/TelegramPreview";
import { ButtonsEditor } from "@/components/ButtonsEditor";
import { MediaManager, mediaUrl, type MediaAsset } from "@/components/MediaManager";
import { YandexMapPicker } from "@/components/YandexMapPicker";

interface Channel { id: number; city_id: number; title: string; username?: string; avatar_url?: string }

export default function ComposePage() {
  const router = useRouter();
  const { data: cities } = useSWR<Page<City>>("/cities?size=100", fetcher);

  // Local form state; the draft news row is created lazily on first need.
  const [draftId, setDraftId] = useState<number | null>(null);
  const [cityId, setCityId] = useState<number | "">("");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [buttons, setButtons] = useState<PreviewButton[][]>([]);
  const [media, setMedia] = useState<MediaAsset[]>([]);
  const [lat, setLat] = useState<number | "">("");
  const [lon, setLon] = useState<number | "">("");
  const [locTitle, setLocTitle] = useState("");
  const [locAddr, setLocAddr] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [showMap, setShowMap] = useState(false);

  const { data: channels } = useSWR<Page<Channel>>(cityId ? `/channels?city_id=${cityId}` : null, fetcher);
  const channel = channels?.items[0];

  // Ensure a draft news row exists; returns its id.
  const ensureDraft = async (): Promise<number> => {
    if (draftId) return draftId;
    const created = await api<{ id: number }>("/news", {
      method: "POST",
      body: JSON.stringify({ original_text: text || " ", original_title: title, origin: "user" }),
    });
    setDraftId(created.id);
    return created.id;
  };

  const reloadMedia = async () => {
    if (!draftId) return;
    const fresh = await api<{ media: MediaAsset[] }>(`/news/${draftId}`);
    setMedia(fresh.media ?? []);
  };

  const onAttachRequest = async () => {
    // MediaManager needs an id up front; create the draft first if needed.
    await ensureDraft();
  };

  const persist = async (id: number) => {
    await api(`/news/${id}`, {
      method: "PATCH",
      body: JSON.stringify({
        title,
        text,
        city_id: cityId || null,
        buttons,
        latitude: lat === "" ? null : Number(lat),
        longitude: lon === "" ? null : Number(lon),
        location_title: locTitle || null,
        location_address: locAddr || null,
      }),
    });
  };

  const saveDraft = async () => {
    setSaving(true);
    try {
      const id = await ensureDraft();
      await persist(id);
      router.push(`/news/${id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const publish = async () => {
    if (!cityId) { setError("Выберите город"); return; }
    setSaving(true);
    try {
      const id = await ensureDraft();
      await persist(id);
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
        <PageHeader title="Создать пост вручную" />
        <div className="card space-y-4 p-5">
          {error && <p className="rounded-md bg-red-50 p-2 text-sm text-red-600 dark:bg-red-950/40">{error}</p>}

          <label className="block">
            <span className="text-sm text-muted-foreground">Город / канал</span>
            <select className="input mt-1" value={cityId} onChange={(e) => setCityId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">— выберите город —</option>
              {cities?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>

          <label className="block">
            <span className="text-sm text-muted-foreground">Заголовок</span>
            <input className="input mt-1" value={title} onChange={(e) => setTitle(e.target.value)} />
          </label>

          <label className="block">
            <span className="text-sm text-muted-foreground">Текст (HTML Telegram)</span>
            <textarea className="input mt-1 min-h-[180px] font-mono" value={text} onChange={(e) => setText(e.target.value)} />
          </label>

          <div>
            <div className="mb-2 text-sm font-medium">Вложения ({media.length})</div>
            {draftId ? (
              <MediaManager newsId={draftId} media={media} onChange={reloadMedia} />
            ) : (
              <button className="btn-outline" onClick={onAttachRequest}>Добавить вложения</button>
            )}
          </div>

          <div>
            <div className="mb-2 text-sm font-medium">Кнопки под постом</div>
            <ButtonsEditor value={buttons} onChange={setButtons} />
          </div>

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
                  latitude={lat === "" ? null : Number(lat)}
                  longitude={lon === "" ? null : Number(lon)}
                  onPick={(la, lo, addr) => { setLat(la); setLon(lo); if (addr) setLocAddr(addr); }}
                />
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <input className="input" type="number" step="any" placeholder="Широта" value={lat} onChange={(e) => setLat(e.target.value ? Number(e.target.value) : "")} />
              <input className="input" type="number" step="any" placeholder="Долгота" value={lon} onChange={(e) => setLon(e.target.value ? Number(e.target.value) : "")} />
              <input className="input" placeholder="Название места" value={locTitle} onChange={(e) => setLocTitle(e.target.value)} />
              <input className="input" placeholder="Адрес" value={locAddr} onChange={(e) => setLocAddr(e.target.value)} />
            </div>
          </div>

          <div className="flex gap-3 border-t border-border pt-4">
            <button className="btn-outline" disabled={saving || !text} onClick={saveDraft}>Сохранить черновик</button>
            <button className="btn-primary" disabled={saving || !text || !cityId} onClick={publish}>Опубликовать</button>
          </div>
        </div>
      </div>

      <div className="lg:sticky lg:top-6 lg:self-start">
        <div className="mb-2 text-sm font-medium">Предпросмотр</div>
        <TelegramPreview
          channelName={channel?.title || "Канал"}
          channelAvatar={channel?.avatar_url}
          title={title}
          text={text}
          media={media.filter((m) => m.is_enabled).map((m) => ({ url: mediaUrl(m), type: m.type, spoiler: m.is_spoiler }))}
          buttons={buttons}
          locationTitle={locTitle}
        />
      </div>
    </div>
  );
}

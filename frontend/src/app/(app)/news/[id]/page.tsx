"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { Copy, Globe, Save, Send, Trash2, Undo2 } from "lucide-react";
import { api, fetcher } from "@/lib/api";
import type { NewsItem, Page } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge, StateTag } from "@/components/StatusBadge";
import { TelegramPreview, type PreviewButton } from "@/components/TelegramPreview";
import { ButtonsEditor } from "@/components/ButtonsEditor";
import { MediaManager, mediaUrl, type MediaAsset } from "@/components/MediaManager";
import { YandexMapPicker } from "@/components/YandexMapPicker";
import { RichTextEditor } from "@/components/RichTextEditor";
import { EmojiPickerButton } from "@/components/EmojiPickerButton";
import { Checkbox, Select } from "@/components/Controls";
import { Modal, Field } from "@/components/Modal";
import { useToast } from "@/components/Toast";
import { confirm } from "@/components/ConfirmDialog";

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
  emoji?: string | null;
  template_id?: number | null;
  ai_profile_id?: number | null;
  author_name?: string | null;
  submitted_anonymously?: boolean;
  source_name?: string | null;
  hide_source?: boolean;
  source_url_override?: string | null;
  source_published_at?: string | null;
  processed_at?: string | null;
  ai_processed_at?: string | null;
  publish_immediately?: boolean;
  is_world_news?: boolean;
  reply_to_news_id?: number | null;
  published_message_ids?: Record<string, number[]>;
  target_city_ids?: number[];
  media: MediaAsset[];
}

interface City { id: number; name: string }
interface Channel { id: number; city_id: number; title: string; username?: string; avatar_url?: string }
interface Template { id: number; name: string }
interface UserRef { id: number; email: string; full_name?: string }

export default function NewsEditorPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [news, setNews] = useState<NewsDetail | null>(null);
  const [city, setCity] = useState<City | null>(null);
  const [channel, setChannel] = useState<Channel | null>(null);
  const [rendered, setRendered] = useState<string>("");
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showMap, setShowMap] = useState(false);
  const [copyModal, setCopyModal] = useState(false);
  const [copyCity, setCopyCity] = useState<string>("");
  const [copyPublish, setCopyPublish] = useState(false);
  const [copying, setCopying] = useState(false);
  const toast = useToast();

  const { data: templates } = useSWR<Page<Template>>("/templates?size=100", fetcher);
  const { data: users } = useSWR<Page<UserRef>>("/users?size=200", fetcher);
  const { data: allCities } = useSWR<Page<City>>("/cities?size=200", fetcher);
  const { data: sources } = useSWR<Page<{ id: number; name: string }>>(
    "/sources?size=200",
    fetcher
  );
  const moderator = news?.moderated_by
    ? users?.items.find((u) => u.id === news.moderated_by)
    : undefined;

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

  // Re-render preview through the selected template whenever content changes.
  useEffect(() => {
    if (!news) return;
    const t = setTimeout(async () => {
      try {
        // POST unsaved editor values so the preview matches exactly.
        const r = await api<{ detail: string }>(`/news/${news.id}/render`, {
          method: "POST",
          body: JSON.stringify({
            template_id: news.template_id ?? null,
            title: news.title ?? "",
            text: news.text ?? "",
            emoji: news.emoji ?? "",
            author_name: news.author_name ?? "",
            submitted_anonymously: news.submitted_anonymously ?? false,
            source_name: news.source_name ?? "",
            hide_source: news.hide_source ?? false,
          }),
        });
        setRendered(r.detail);
      } catch { /* ignore */ }
    }, 400);
    return () => clearTimeout(t);
  }, [
    news?.template_id, news?.title, news?.text, news?.emoji,
    news?.author_name, news?.submitted_anonymously,
    news?.source_name, news?.hide_source, news?.id,
  ]);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!news) return <p className="text-muted-foreground">Загрузка…</p>;

  const update = (patch: Partial<NewsDetail>) => setNews((n) => (n ? { ...n, ...patch } : n));

  const isPublished = Object.keys(news.published_message_ids ?? {}).length > 0;
  const fmtTime = (value?: string | null) =>
    value ? new Date(value).toLocaleString("ru-RU") : "—";

  // Name of the source this news came from (used as a hint/placeholder).
  const linkedSource = news.source_id
    ? sources?.items.find((s) => s.id === news.source_id)?.name
    : undefined;
  const sourceLabel = linkedSource ?? "не задан";
  const sourcePlaceholder = linkedSource
    ? `Название источника (сейчас: ${linkedSource})`
    : "Название источника (Источник: …)";

  const save = async () => {
    setSaving(true);
    try {
      await api(`/news/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: news.title,
          text: news.text,
          emoji: news.emoji ?? null,
          template_id: news.template_id ?? null,
          apply_watermark: news.apply_watermark,
          latitude: news.latitude ?? null,
          longitude: news.longitude ?? null,
          location_title: news.location_title ?? null,
          location_address: news.location_address ?? null,
          buttons: news.buttons ?? [],
          author_name: news.author_name ?? null,
          submitted_anonymously: news.submitted_anonymously ?? false,
          source_name: news.source_name ?? null,
          hide_source: news.hide_source ?? false,
          source_url_override: news.source_url_override ?? null,
          publish_immediately: news.publish_immediately ?? false,
          target_city_ids: news.target_city_ids ?? [],
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

  const regenerate = async () => {
    setRegenerating(true);
    setError(null);
    try {
      const n = await api<NewsDetail>(`/news/${id}/regenerate`, { method: "POST" });
      setNews((prev) => (prev ? { ...prev, title: n.title, text: n.text, emoji: n.emoji } : n));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRegenerating(false);
    }
  };

  const publish = async () => {
    setSaving(true);
    try {
      await save();
      await api(`/news/${id}/publish`, { method: "POST" });
      router.push("/news");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  /** Publish this single item to the channels of every active city. */
  const publishAllCities = async () => {
    if (!(await confirm({ message: "Опубликовать эту новость во все каналы всех городов?", danger: true }))) return;
    setSaving(true);
    try {
      await save();
      const r = await api<{ detail: string }>(`/news/${id}/publish-all-cities`, {
        method: "POST",
      });
      toast.success(r.detail);
      await load();
    } catch (e) {
      setError((e as Error).message);
      toast.error((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  /** Delete everywhere: channels, moderation topic and the admin panel. */
  const removeCompletely = async () => {
    if (!(await confirm({ message: "Удалить полностью — из каналов, топика и админки?", danger: true }))) return;
    setSaving(true);
    try {
      await api(`/news/${id}`, { method: "DELETE" });
      router.push("/news");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  /** Withdraw an already published post so it can be edited/republished. */
  const unpublish = async () => {
    if (!(await confirm({ message: "Снять публикацию? Сообщение будет удалено из Telegram-канала.", danger: true }))) return;
    setSaving(true);
    try {
      await api(`/news/${id}/unpublish`, { method: "POST" });
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const copyToCity = async () => {
    if (!copyCity) return;
    setCopying(true);
    try {
      const copied = await api<{ id: number }>(`/news/${id}/copy-to-city`, {
        method: "POST",
        body: JSON.stringify({ city_id: Number(copyCity), publish_immediately: copyPublish }),
      });
      setCopyModal(false);
      if (copyPublish) {
        toast.success(`Скопировано и опубликовано: новость #${copied.id}`);
      } else {
        // Open the editor for the copied news so the user can review/edit before publishing.
        router.push(`/news/${copied.id}`);
      }
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setCopying(false);
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_400px]">
      <div>
        <PageHeader
          title={`Новость #${news.id}`}
          action={
            <div className="flex flex-wrap items-center gap-1.5">
              <StatusBadge status={news.status} />
              {news.is_edited && <StateTag kind="edited" />}
            </div>
          }
        />

        <div className="card space-y-4 p-5">
          {/* Moderator-only meta: never published to the channel */}
          <div className="rounded-lg bg-muted px-3 py-2 text-sm">
            {city && (
              <div>
                Город: <span className="font-medium">{city.name}</span>
                {channel && <> · канал <span className="font-medium">{channel.title}</span></>}
              </div>
            )}
            <div className="mt-1 grid gap-x-4 gap-y-0.5 text-xs text-muted-foreground sm:grid-cols-2">
              <div>🕐 В источнике: {fmtTime(news.source_published_at)}</div>
              <div>🤖 Обработано AI: {fmtTime(news.ai_processed_at)}</div>
              <div>
                👤 Обработал:{" "}
                {moderator ? (moderator.full_name || moderator.email) : "—"}
                {" · "}
                {fmtTime(news.processed_at)}
              </div>
              <div>📤 Опубликовано: {fmtTime(news.published_at)}</div>
              {news.scheduled_at && <div>🕒 Запланировано: {fmtTime(news.scheduled_at)}</div>}
              {news.is_world_news && <div>🌍 Мировая новость</div>}
              {news.reply_to_news_id && (
                <div>↩️ Дополнение к новости #{news.reply_to_news_id}</div>
              )}
            </div>
          </div>

          {/* Original (pre-AI) text, read-only */}
          <label className="block">
            <span className="text-sm text-muted-foreground">Исходный текст (до AI)</span>
            <textarea className="input mt-1 min-h-[220px] bg-muted/50 font-mono text-xs" value={news.original_text ?? ""} readOnly />
          </label>

          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Обработанный контент</span>
            <button className="btn-outline py-1 text-xs" disabled={regenerating} onClick={regenerate}>
              {regenerating ? "Генерация…" : "🔄 Перегенерировать AI"}
            </button>
          </div>

          {/* Emoji sits right next to the title */}
          <div className="flex items-end gap-3">
            <div className="w-[132px] shrink-0">
              <span className="text-sm text-muted-foreground">Эмодзи</span>
              {/* Input and picker share one row and the same height */}
              <div className="mt-1 flex items-stretch gap-1">
                <input
                  className="input h-9 w-full px-1 text-center text-lg leading-none"
                  value={news.emoji ?? ""}
                  maxLength={8}
                  onChange={(e) => update({ emoji: e.target.value })}
                />
                <EmojiPickerButton
                  onPick={(em) => update({ emoji: em })}
                  className="h-9 w-9 shrink-0"
                />
              </div>
            </div>
            <label className="block flex-1">
              <span className="text-sm text-muted-foreground">Заголовок</span>
              <input
                className="input mt-1"
                value={news.title ?? ""}
                onChange={(e) => update({ title: e.target.value })}
              />
            </label>
          </div>

          <div>
            <span className="text-sm text-muted-foreground">Текст (выделите фрагмент и примените разметку)</span>
            <div className="mt-1">
              <RichTextEditor value={news.text ?? ""} onChange={(html) => update({ text: html })} />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <span className="text-sm text-muted-foreground">Шаблон</span>
              <div className="mt-1">
                <Select
                  value={news.template_id ?? ""}
                  onChange={(v) => update({ template_id: v ? Number(v) : null })}
                >
                  <option value="">По умолчанию</option>
                  {templates?.items.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </Select>
              </div>
            </div>
            <div className="flex items-end pb-2">
              <Checkbox
                checked={news.apply_watermark}
                onChange={(v) => update({ apply_watermark: v })}
                label="Водяной знак"
              />
            </div>
          </div>

          {/* Target cities (channels this single news publishes to) */}
          <div className="rounded-lg border border-border p-4">
            <div className="mb-2 text-sm font-medium">
              Каналы публикации ({(news.target_city_ids ?? []).length || (news.city_id ? 1 : 0)})
            </div>
            <p className="mb-2 text-xs text-muted-foreground">
              Одна новость публикуется одной кнопкой во все выбранные города с применением
              шаблона каждого города.
            </p>
            <div className="flex flex-wrap gap-2">
              {allCities?.items.map((c) => {
                const current = news.target_city_ids ?? (news.city_id ? [news.city_id] : []);
                const on = current.includes(c.id);
                return (
                  <button
                    key={c.id}
                    type="button"
                    className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${
                      on
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-card text-muted-foreground hover:border-primary/50"
                    }`}
                    onClick={() => {
                      const set = new Set(current);
                      if (set.has(c.id)) set.delete(c.id);
                      else set.add(c.id);
                      update({ target_city_ids: Array.from(set) });
                    }}
                  >
                    {c.name}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Author */}
          <div className="rounded-lg border border-border p-4">
            <div className="mb-2 text-sm font-medium">Автор</div>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <input className="input" placeholder="Имя автора (Автор: …)" value={news.author_name ?? ""} disabled={news.submitted_anonymously} onChange={(e) => update({ author_name: e.target.value })} />
              <Checkbox
                checked={!!news.submitted_anonymously}
                onChange={(v) => update({ submitted_anonymously: v })}
                label="Скрыть автора"
              />
            </div>
          </div>

          {/* Source: name + link (rendered as a hyperlink inside the post) */}
          <div className="rounded-lg border border-border p-4">
            <div className="mb-2 text-sm font-medium">Источник</div>
            <div className="grid gap-3 sm:grid-cols-2">
              <input
                className="input"
                placeholder={sourcePlaceholder}
                value={news.source_name ?? ""}
                disabled={news.hide_source}
                onChange={(e) => update({ source_name: e.target.value })}
              />
              <input
                className="input"
                placeholder="Ссылка на оригинал (https://…)"
                value={news.source_url_override ?? news.original_url ?? ""}
                disabled={news.hide_source}
                onChange={(e) => update({ source_url_override: e.target.value })}
              />
            </div>
            <div className="mt-3">
              <Checkbox
                checked={!!news.hide_source}
                onChange={(v) => update({ hide_source: v })}
                label="Скрыть источник в публикации"
              />
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Название станет гиперссылкой на оригинал прямо в тексте поста. Если название
              пустое — берётся имя привязанного источника ({sourceLabel}). Пустая строка
              «Источник:» в пост не попадает.
            </p>
          </div>

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
                <YandexMapPicker latitude={news.latitude} longitude={news.longitude}
                  onPick={(lat, lon, addr) => update({ latitude: lat, longitude: lon, location_address: addr ?? news.location_address })} />
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <input className="input" type="number" step="any" placeholder="Широта" value={news.latitude ?? ""} onChange={(e) => update({ latitude: e.target.value === "" ? null : Number(e.target.value) })} />
              <input className="input" type="number" step="any" placeholder="Долгота" value={news.longitude ?? ""} onChange={(e) => update({ longitude: e.target.value === "" ? null : Number(e.target.value) })} />
              <input className="input" placeholder="Название места" value={news.location_title ?? ""} onChange={(e) => update({ location_title: e.target.value })} />
              <input className="input" placeholder="Адрес" value={news.location_address ?? ""} onChange={(e) => update({ location_address: e.target.value })} />
            </div>
          </div>

          <div className="border-t border-border pt-4">
            <div className="mb-3">
              <Checkbox
                checked={!!news.publish_immediately}
                onChange={(v) => update({ publish_immediately: v })}
                label="Опубликовать немедленно (вне очереди)"
              />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button className="btn-outline" disabled={saving} onClick={save}>
                <Save className="h-4 w-4" /> Сохранить
              </button>

              {isPublished ? (
                <>
                  <button
                    className="btn-icon-danger h-9 w-9"
                    title="Снять публикацию (удалить из канала, оставить в админке)"
                    disabled={saving}
                    onClick={unpublish}
                  >
                    <Undo2 className="h-4 w-4" />
                  </button>
                  <span className="text-xs text-muted-foreground">
                    Опубликовано. Правки уходят в Telegram; для повторной публикации сначала
                    снимите её.
                  </span>
                </>
              ) : (
                <>
                  <button
                    className="btn-icon-success h-9 w-9"
                    title="Опубликовать в каналы города"
                    disabled={saving}
                    onClick={publish}
                  >
                    <Send className="h-4 w-4" />
                  </button>
                  <button
                    className="btn-icon-primary h-9 w-9"
                    title="Опубликовать во все каналы всех городов"
                    disabled={saving}
                    onClick={publishAllCities}
                  >
                    <Globe className="h-4 w-4" />
                  </button>
                </>
              )}

              <button
                className="btn-icon-danger h-9 w-9"
                title="Удалить полностью (из каналов, топика и админки)"
                disabled={saving}
                onClick={removeCompletely}
              >
                <Trash2 className="h-4 w-4" />
              </button>
              <button
                className="btn-icon h-9 w-9"
                title="Копировать в другой город"
                disabled={saving}
                onClick={() => { setCopyCity(""); setCopyPublish(false); setCopyModal(true); }}
              >
                <Copy className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Copy-to-city modal */}
      <Modal open={copyModal} onClose={() => setCopyModal(false)} title="Копировать в другой город">
        <div className="space-y-4">
          <Field label="Город назначения">
            <Select value={copyCity} onChange={setCopyCity}>
              <option value="">— выберите город —</option>
              {allCities?.items
                .filter((c) => c.id !== news.city_id)
                .map((c) => <option key={c.id} value={c.id}>{c.name}</option>)
              }
            </Select>
          </Field>
          <Checkbox
            checked={copyPublish}
            onChange={setCopyPublish}
            label="Опубликовать сразу"
          />
          <div className="flex justify-end gap-2 pt-2">
            <button className="btn-outline" onClick={() => setCopyModal(false)}>Отмена</button>
            <button className="btn-primary" disabled={!copyCity || copying} onClick={copyToCity}>
              {copying ? "Копирование…" : "Копировать"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Live Telegram preview (rendered via template) */}
      <div className="lg:sticky lg:top-6 lg:self-start">
        <div className="mb-2 text-sm font-medium">Предпросмотр (по шаблону)</div>
        <TelegramPreview
          channelName={channel?.title || city?.name || "Канал"}
          channelAvatar={channel?.avatar_url}
          text={rendered || news.text || news.original_text || ""}
          media={news.media.filter((m) => m.is_enabled).map((m) => ({ url: mediaUrl(m), type: m.type, spoiler: m.is_spoiler }))}
          buttons={news.buttons ?? []}
          locationTitle={news.location_title}
        />
      </div>
    </div>
  );
}

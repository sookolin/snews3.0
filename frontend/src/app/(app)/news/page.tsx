"use client";

import { useState } from "react";
import useSWR from "swr";
import { CalendarClock, Check, Pencil, Trash2, Undo2, X } from "lucide-react";
import { api, fetcher } from "@/lib/api";
import type { City, NewsItem, Page, Source, User } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge, StateTag, STATUS_LABELS, STATUS_ORDER } from "@/components/StatusBadge";
import { RoleTag } from "@/components/RoleTag";
import { MediaHoverPreview } from "@/components/MediaHoverPreview";
import { Pagination } from "@/components/Pagination";
import { Modal, Field } from "@/components/Modal";
import { Select } from "@/components/Controls";

/** Top-level tabs: city news vs. news that belong to no monitored city. */
const TABS = [
  { key: "city", label: "По городам" },
  { key: "world", label: "🌍 Мировые" },
  { key: "", label: "Все" },
] as const;

/** Local datetime string (yyyy-MM-ddTHH:mm) for the schedule input. */
function toLocalInput(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}`;
}

export default function NewsPage() {
  const [scope, setScope] = useState<string>("city");
  const [status, setStatus] = useState("");
  const [cityId, setCityId] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<number[]>([]);
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(50);
  const [scheduling, setScheduling] = useState<NewsItem | null>(null);
  const [scheduleAt, setScheduleAt] = useState("");
  const [error, setError] = useState<string | null>(null);

  const query = new URLSearchParams();
  if (scope) query.set("scope", scope);
  if (status) query.set("status", status);
  if (cityId) query.set("city_id", cityId);
  if (search) query.set("search", search);
  query.set("page", String(page));
  query.set("size", String(size));

  const { data, mutate, isLoading } = useSWR<Page<NewsItem>>(`/news?${query.toString()}`, fetcher);
  const { data: cities } = useSWR<Page<City>>("/cities?size=200", fetcher);
  const { data: users } = useSWR<Page<User>>("/users?size=200", fetcher);
  const { data: sources } = useSWR<Page<Source>>("/sources?size=200", fetcher);

  const cityName = (id?: number) =>
    id ? cities?.items.find((c) => c.id === id)?.name ?? `#${id}` : "—";

  /**
   * Origin of the item: a reader who submitted it through the bot, the source
   * it was parsed from, or the admin who created it by hand.
   */
  const origin = (n: NewsItem) => {
    if (n.origin === "user") {
      if (n.submitted_by_telegram_id) {
        const who = n.submitted_anonymously ? "Аноним" : n.author_name || "Пользователь";
        return (
          <span
            className="badge bg-teal-50 text-teal-700 ring-teal-200 dark:bg-teal-950/50 dark:text-teal-300 dark:ring-teal-900"
            title="Предложено через бота"
          >
            {who}
          </span>
        );
      }
      // Created inside the panel — tag it as an admin post.
      return (
        <span
          className="badge bg-fuchsia-50 text-fuchsia-700 ring-fuchsia-200 dark:bg-fuchsia-950/50 dark:text-fuchsia-300 dark:ring-fuchsia-900"
          title="Создано в админке"
        >
          Админ{n.author_name ? ` · ${n.author_name}` : ""}
        </span>
      );
    }
    const src = n.source_id
      ? sources?.items.find((s) => s.id === n.source_id)?.name ?? `#${n.source_id}`
      : null;
    return src ? (
      <span
        className="badge bg-slate-50 text-slate-700 ring-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700"
        title="Источник"
      >
        {src}
      </span>
    ) : (
      <span className="text-muted-foreground">—</span>
    );
  };

  /** Who processed the item, coloured by their access level. */
  const processedBy = (n: NewsItem) => {
    if (!n.moderated_by) return <span className="text-muted-foreground">—</span>;
    const u = users?.items.find((x) => x.id === n.moderated_by);
    if (!u) return <RoleTag name={`#${n.moderated_by}`} />;
    return <RoleTag name={u.full_name || u.email} role={u.role} />;
  };

  const isLive = (n: NewsItem) => Object.keys(n.published_message_ids ?? {}).length > 0;

  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
      await mutate();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const act = (id: number, action: "approve" | "reject" | "unpublish") =>
    run(() => api(`/news/${id}/${action}`, { method: "POST" }));

  const remove = (id: number) => {
    if (!confirm("Удалить новость безвозвратно?")) return;
    return run(async () => {
      await api(`/news/${id}`, { method: "DELETE" });
      setSelected((s) => s.filter((x) => x !== id));
    });
  };

  const bulkDelete = () => {
    if (!selected.length) return;
    if (!confirm(`Удалить выбранные новости (${selected.length})?`)) return;
    return run(async () => {
      await api("/news/bulk-delete", { method: "POST", body: JSON.stringify({ ids: selected }) });
      setSelected([]);
    });
  };

  const openSchedule = (n: NewsItem) => {
    const base = n.scheduled_at ? new Date(n.scheduled_at) : new Date(Date.now() + 30 * 60_000);
    setScheduleAt(toLocalInput(base));
    setScheduling(n);
  };

  const saveSchedule = (clear = false) => {
    if (!scheduling) return;
    const id = scheduling.id;
    return run(async () => {
      await api(`/news/${id}/schedule`, {
        method: "POST",
        body: JSON.stringify({
          // Local input → absolute instant, so the backend gets an unambiguous time.
          scheduled_at: clear ? null : new Date(scheduleAt).toISOString(),
        }),
      });
      setScheduling(null);
    });
  };

  const toggle = (id: number) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const items = data?.items ?? [];
  const allSelected = items.length > 0 && selected.length === items.length;
  const toggleAll = () => setSelected(allSelected ? [] : items.map((n) => n.id));

  const switchTab = (key: string) => {
    setScope(key);
    setPage(1);
    setSelected([]);
  };

  return (
    <div>
      <PageHeader
        title="Новости"
        action={
          selected.length > 0 ? (
            <button className="btn-danger" onClick={bulkDelete}>
              <Trash2 className="h-4 w-4" /> Удалить выбранные ({selected.length})
            </button>
          ) : undefined
        }
      />

      {/* Scope tabs */}
      <div className="mb-4 flex gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
              scope === t.key
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
            onClick={() => switchTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && (
        <p className="mb-4 rounded-md bg-rose-50 p-2 text-sm text-rose-600 dark:bg-rose-950/40">
          {error}
        </p>
      )}

      <div className="mb-4 flex flex-wrap gap-3">
        <Select
          className="max-w-[220px]"
          value={status}
          onChange={(v) => {
            setStatus(v);
            setPage(1);
          }}
        >
          <option value="">Все статусы</option>
          {STATUS_ORDER.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s] ?? s}
            </option>
          ))}
        </Select>
        {scope !== "world" && (
          <Select
            className="max-w-[220px]"
            value={cityId}
            onChange={(v) => {
              setCityId(v);
              setPage(1);
            }}
          >
            <option value="">Все города</option>
            {cities?.items.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        )}
        <input
          className="input max-w-xs"
          placeholder="Поиск…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
        />
      </div>

      <div className="card overflow-hidden">
        <div className="table-wrap">
          <table className="w-full text-sm">
            <thead className="bg-muted text-left text-muted-foreground">
              <tr>
                <th className="px-3 py-3">
                  <input type="checkbox" checked={allSelected} onChange={toggleAll} />
                </th>
                <th className="px-3 py-3">ID</th>
                <th className="px-4 py-3">Заголовок</th>
                <th className="px-4 py-3">Город</th>
                <th className="px-4 py-3">Автор / источник</th>
                <th className="px-4 py-3">Обработал</th>
                <th className="px-4 py-3">Статус</th>
                <th className="px-4 py-3">В источнике</th>
                <th className="px-4 py-3 text-right">Действия</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={9} className="px-4 py-6 text-center text-muted-foreground">
                    Загрузка…
                  </td>
                </tr>
              )}
              {items.map((n) => (
                <tr key={n.id} className="border-t border-border">
                  <td className="px-3 py-3">
                    <input
                      type="checkbox"
                      checked={selected.includes(n.id)}
                      onChange={() => toggle(n.id)}
                    />
                  </td>
                  <td className="px-3 py-3 text-muted-foreground">{n.id}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <a className="hover:text-primary hover:underline" href={`/news/${n.id}`}>
                        {n.emoji ? `${n.emoji} ` : ""}
                        {n.title || n.original_title || "—"}
                      </a>
                      <MediaHoverPreview media={n.media ?? []} />
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {n.is_world_news ? (
                      <span className="badge bg-cyan-50 text-cyan-700 ring-cyan-200 dark:bg-cyan-950/50 dark:text-cyan-300 dark:ring-cyan-900">
                        🌍 Мировые
                      </span>
                    ) : (
                      <span className="badge bg-indigo-50 text-indigo-700 ring-indigo-200 dark:bg-indigo-950/50 dark:text-indigo-300 dark:ring-indigo-900">
                        {cityName(n.city_id)}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">{origin(n)}</td>
                  <td className="px-4 py-3">{processedBy(n)}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col items-start gap-1">
                      <StatusBadge status={n.status} />
                      {n.is_edited && <StateTag kind="edited" />}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {n.source_published_at
                      ? new Date(n.source_published_at).toLocaleString("ru-RU")
                      : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1.5">
                      {n.status === "pending" && (
                        <>
                          <button
                            className="btn-icon-success"
                            title="Одобрить"
                            onClick={() => act(n.id, "approve")}
                          >
                            <Check className="h-4 w-4" />
                          </button>
                          <button
                            className="btn-icon-danger"
                            title="Отклонить"
                            onClick={() => act(n.id, "reject")}
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </>
                      )}
                      {!isLive(n) && (
                        <button
                          className="btn-icon"
                          title="Запланировать публикацию"
                          onClick={() => openSchedule(n)}
                        >
                          <CalendarClock className="h-4 w-4" />
                        </button>
                      )}
                      {isLive(n) && (
                        <button
                          className="btn-icon-danger"
                          title="Снять с публикации (удалить из канала)"
                          onClick={() => act(n.id, "unpublish")}
                        >
                          <Undo2 className="h-4 w-4" />
                        </button>
                      )}
                      <a className="btn-icon" title="Открыть / редактировать" href={`/news/${n.id}`}>
                        <Pencil className="h-4 w-4" />
                      </a>
                      <button
                        className="btn-icon-danger"
                        title="Удалить"
                        onClick={() => remove(n.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {data && items.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-6 text-center text-muted-foreground">
                    Нет новостей
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {data && (
        <Pagination
          page={page}
          size={size}
          total={data.total}
          onPage={setPage}
          onSize={setSize}
        />
      )}

      <Modal
        open={!!scheduling}
        onClose={() => setScheduling(null)}
        title={`Запланировать новость #${scheduling?.id ?? ""}`}
      >
        <div className="space-y-4">
          <Field
            label="Дата и время публикации"
            hint="Пост выйдет в канал точно в это время (по времени вашего устройства)."
          >
            <input
              className="input"
              type="datetime-local"
              value={scheduleAt}
              onChange={(e) => setScheduleAt(e.target.value)}
            />
          </Field>
          <div className="flex justify-end gap-2 border-t border-border pt-4">
            {scheduling?.scheduled_at && (
              <button className="btn-outline" onClick={() => saveSchedule(true)}>
                Отменить планирование
              </button>
            )}
            <button className="btn-primary" onClick={() => saveSchedule()}>
              Запланировать
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

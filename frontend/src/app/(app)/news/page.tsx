"use client";

import { Fragment, useState, useEffect } from "react";
import useSWR from "swr";
import { CalendarClock, Check, ChevronDown, ChevronRight, Pencil, RefreshCw, Trash2, Undo2, X } from "lucide-react";
import { api, fetcher } from "@/lib/api";
import type { City, NewsItem, Page, Source, User } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge, StateTag, STATUS_LABELS, STATUS_ORDER } from "@/components/StatusBadge";
import { RoleTag } from "@/components/RoleTag";
import { MediaHoverPreview } from "@/components/MediaHoverPreview";
import { Pagination } from "@/components/Pagination";
import { ResizableTable } from "@/components/ResizableTable";
import { Modal, Field } from "@/components/Modal";
import { Checkbox, Select } from "@/components/Controls";
import { confirm } from "@/components/ConfirmDialog";

interface Tab {
  key: string;
  label: string;
  /** Backend `scope` filter; empty means "no scope filter". */
  scope: string;
  /** Set for section tabs built from a non-geographic entry. */
  cityId?: number;
}

/** Fixed tabs; the non-geographic sections are appended from /cities. */
const BASE_TABS: Tab[] = [
  { key: "city", label: "По городам", scope: "city" },
  { key: "all", label: "Все", scope: "" },
];

/** Local datetime string (yyyy-MM-ddTHH:mm) for the schedule input. */
function toLocalInput(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}`;
}

export default function NewsPage() {
  const [tabKey, setTabKey] = useState<string>("");
  const [status, setStatus] = useState("");
  const [cityId, setCityId] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<number[]>([]);
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(50);
  const [scheduling, setScheduling] = useState<NewsItem | null>(null);
  const [scheduleAt, setScheduleAt] = useState("");
  const [error, setError] = useState<string | null>(null);
  //: Ids of rows expanded to preview their main text inline.
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  //: Lazily-loaded main text per news id (fetched when a row is expanded).
  const [previews, setPreviews] = useState<Record<number, string>>({});
  const toggleExpanded = async (id: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
    if (previews[id] === undefined) {
      try {
        const n = await api<{ text?: string; original_text?: string }>(`/news/${id}`);
        const raw = n.text || n.original_text || "—";
        // Strip HTML tags for a plain-text preview.
        const plain = raw.replace(/<[^>]*>/g, "").trim() || "—";
        setPreviews((p) => ({ ...p, [id]: plain }));
      } catch {
        setPreviews((p) => ({ ...p, [id]: "Не удалось загрузить текст" }));
      }
    }
  };

  const { data: cities } = useSWR<Page<City>>("/cities?size=200", fetcher);

  // Sections the user created themselves ("другое": мир, интернет…) become tabs,
  // so nothing about the news layout is hardcoded here.
  const sectionTabs: Tab[] = (cities?.items ?? [])
    .filter((c) => c.kind === "other")
    .map((c) => ({
      key: `section-${c.id}`,
      label: c.is_world_bucket ? `🌍 ${c.name}` : c.name,
      scope: "",
      cityId: c.id,
    }));
  const tabs: Tab[] = [BASE_TABS[0], ...sectionTabs, BASE_TABS[1]];

  // Restore the last active tab from localStorage on mount.
  useEffect(() => {
    const saved = localStorage.getItem("snews.news.active_tab");
    const exists = saved && tabs.some((t) => t.key === saved);
    setTabKey(exists ? saved : tabs[0]?.key ?? "city");
  }, [cities]);

  const activeTab = tabs.find((t) => t.key === tabKey) ?? tabs[0];

  const query = new URLSearchParams();
  if (activeTab.scope) query.set("scope", activeTab.scope);
  if (status) query.set("status", status);
  // A section tab pins the city; the dropdown only applies to the city tab.
  if (activeTab.cityId) query.set("city_id", String(activeTab.cityId));
  else if (cityId) query.set("city_id", cityId);
  if (search) query.set("search", search);
  query.set("page", String(page));
  query.set("size", String(size));

  const { data, mutate, isLoading } = useSWR<Page<NewsItem>>(`/news?${query.toString()}`, fetcher);
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

  const remove = async (id: number) => {
    if (!(await confirm({ message: "Удалить новость безвозвратно?", danger: true }))) return;
    return run(async () => {
      await api(`/news/${id}`, { method: "DELETE" });
      setSelected((s) => s.filter((x) => x !== id));
    });
  };

  const bulkDelete = async () => {
    if (!selected.length) return;
    if (!(await confirm({ message: `Удалить выбранные новости (${selected.length})?`, danger: true }))) return;
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
    setTabKey(key);
    localStorage.setItem("snews.news.active_tab", key);
    setCityId("");
    setPage(1);
    setSelected([]);
  };

  return (
    <div>
      <PageHeader
        title="Новости"
        action={
          <div className="flex items-center gap-2">
            {selected.length > 0 && (
              <button className="btn-danger" onClick={bulkDelete}>
                <Trash2 className="h-4 w-4" /> Удалить выбранные ({selected.length})
              </button>
            )}
            <button
              className="btn-outline"
              onClick={() => mutate()}
              disabled={isLoading}
              title="Обновить список новостей"
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} /> Обновить
            </button>
          </div>
        }
      />

      {/* Scope tabs */}
      <div className="mb-4 flex gap-1 border-b border-border">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
              activeTab.key === t.key
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
        {!activeTab.cityId && (
          <div className="flex flex-wrap gap-1.5">
            <button
              className={`rounded-md border px-3 py-1 text-sm font-medium transition-colors ${
                cityId === ""
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-card text-muted-foreground hover:border-primary/50 hover:text-foreground"
              }`}
              onClick={() => { setCityId(""); setPage(1); }}
            >
              Все
            </button>
            {cities?.items
              .filter((c) => c.kind === "city")
              .map((c) => (
                <button
                  key={c.id}
                  className={`rounded-md border px-3 py-1 text-sm font-medium transition-colors ${
                    cityId === String(c.id)
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-card text-muted-foreground hover:border-primary/50 hover:text-foreground"
                  }`}
                  onClick={() => { setCityId(String(c.id)); setPage(1); }}
                >
                  {c.name}
                </button>
              ))}
          </div>
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

      {data && (
        <Pagination
          position="top"
          page={page}
          size={size}
          total={data.total}
          onPage={setPage}
          onSize={setSize}
        />
      )}

      <div className="card overflow-hidden">
        <div className="table-wrap">
          <ResizableTable
            id="news"
            rawColumns={[0, 1, 8]}
            defaultWidths={{ 0: 50, 1: 50 }}
            columns={[
              <Checkbox key="all" checked={allSelected} onChange={() => toggleAll()} />,
              "ID",
              "Заголовок",
              "Канал",
              "Автор / источник",
              "Обработал",
              "Статус",
              "В источнике",
              "Действия",
            ]}
          >
              {isLoading && (
                <tr>
                  <td colSpan={9} className="px-4 py-6 text-center text-muted-foreground">
                    Загрузка…
                  </td>
                </tr>
              )}
              {items.map((n) => (
                <Fragment key={n.id}>
                <tr className="border-t border-border">
                  <td className="px-3 py-3">
                    <Checkbox
                      checked={selected.includes(n.id)}
                      onChange={() => toggle(n.id)}
                    />
                  </td>
                  <td className="px-3 py-3 text-muted-foreground">{n.id}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        title={expanded.has(n.id) ? "Свернуть текст" : "Показать текст"}
                        className="shrink-0 text-muted-foreground hover:text-foreground"
                        onClick={() => toggleExpanded(n.id)}
                      >
                        {expanded.has(n.id) ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                      </button>
                      <a className="hover:text-primary hover:underline" href={`/news/${n.id}`}>
                        {n.emoji ? `${n.emoji} ` : ""}
                        {n.title || n.original_title || "—"}
                      </a>
                      <MediaHoverPreview media={n.media ?? []} />
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {n.is_world_news && !n.city_id ? (
                      <span className="badge bg-cyan-50 text-cyan-700 ring-cyan-200 dark:bg-cyan-950/50 dark:text-cyan-300 dark:ring-cyan-900">
                        🌍 Мировые
                      </span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {((n.target_city_ids && n.target_city_ids.length > 0)
                          ? n.target_city_ids
                          : (n.city_id ? [n.city_id] : [])
                        ).map((cid) => (
                          <span
                            key={cid}
                            className="badge bg-indigo-50 text-indigo-700 ring-indigo-200 dark:bg-indigo-950/50 dark:text-indigo-300 dark:ring-indigo-900"
                          >
                            {cityName(cid)}
                          </span>
                        ))}
                      </div>
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
                {expanded.has(n.id) && (
                  <tr className="border-t border-border bg-muted/30">
                    <td />
                    <td colSpan={8} className="px-4 py-3">
                      <div className="whitespace-pre-wrap text-sm text-muted-foreground">
                        {previews[n.id] ?? "Загрузка…"}
                      </div>
                    </td>
                  </tr>
                )}
                </Fragment>
              ))}
              {data && items.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-6 text-center text-muted-foreground">
                    Нет новостей
                  </td>
                </tr>
              )}
          </ResizableTable>
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

"use client";

import { useState } from "react";
import useSWR from "swr";
import { Pencil, RefreshCw, Trash2 } from "lucide-react";
import { api, fetcher } from "@/lib/api";
import type { Page, Source } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Modal, Field } from "@/components/Modal";
import { Checkbox, Select } from "@/components/Controls";
import { Pagination } from "@/components/Pagination";

const TYPES = ["rss", "telegram", "website", "html", "api"];
const ENGINES = ["auto", "beautifulsoup", "lxml", "playwright"];

export default function SourcesPage() {
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(50);
  const { data, mutate } = useSWR<Page<Source>>(`/sources?page=${page}&size=${size}`, fetcher);
  const [form, setForm] = useState<Partial<Source> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showHelp, setShowHelp] = useState(false);

  const openNew = () =>
    setForm({
      name: "", url: "", type: "rss", parser_engine: "auto",
      check_interval_seconds: 300, is_active: true,
    });
  const openEdit = (s: Source) => setForm({ ...s });
  const upd = (patch: Partial<Source>) => setForm((f) => ({ ...f!, ...patch }));

  const save = async () => {
    if (!form) return;
    setError(null);
    try {
      if (form.id) await api(`/sources/${form.id}`, { method: "PATCH", body: JSON.stringify(form) });
      else await api("/sources", { method: "POST", body: JSON.stringify(form) });
      setForm(null);
      mutate();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const remove = async (id: number) => {
    if (!confirm("Удалить источник?")) return;
    await api(`/sources/${id}`, { method: "DELETE" });
    mutate();
  };

  const check = async (id: number) => {
    await api(`/sources/${id}/check`, { method: "POST" });
    alert("Проверка источника поставлена в очередь");
  };

  return (
    <div>
      <PageHeader
        title="Источники"
        action={
          <div className="flex gap-2">
            <button className="btn-outline" onClick={() => setShowHelp((v) => !v)}>
              {showHelp ? "Скрыть справку" : "Справка"}
            </button>
            <button className="btn-primary" onClick={openNew}>Добавить источник</button>
          </div>
        }
      />

      {showHelp && (
        <div className="card mb-5 space-y-2 p-5 text-sm">
          <h3 className="text-base font-semibold">Как настроить источник</h3>
          <p className="text-muted-foreground">
            <b>Тип</b> определяет парсер: <code>rss</code> для фида,
            <code> telegram</code> для публичного канала (<code>@name</code>),
            <code> website</code> или <code>html</code> для страницы сайта,
            <code> api</code> для JSON.
          </p>
          <p className="text-muted-foreground">
            <b>Парсер:</b> <code>auto</code> сначала пробует обычный запрос, затем браузер;
            <code> playwright</code> нужен для сайтов на JavaScript;
            <code> beautifulsoup</code> и <code>lxml</code> читают обычный HTML.
          </p>
          <p className="text-muted-foreground">
            <b>Cookies</b> нужны, когда новости видны только авторизованным. Получить: F12,
            вкладка Application, раздел Cookies. Скопируйте пары в JSON:
            <code className="ml-1">{'{"sessionid":"abc123"}'}</code>. Со временем сессия
            истекает, тогда значения нужно обновить.
          </p>
          <p className="text-muted-foreground">
            <b>Auth:</b> <code>{'{"type":"basic","username":"u","password":"p"}'}</code> либо
            <code className="ml-1">{'{"type":"bearer","token":"..."}'}</code>. Bearer
            превращается в заголовок Authorization.
          </p>
          <p className="text-muted-foreground">
            <b>Headers</b> помогают при ошибке 403: обычно достаточно своего
            <code> User-Agent</code>.
          </p>
          <p className="text-muted-foreground">
            <b>Селекторы</b> показывают, где на странице новости:
            <code className="ml-1">
              {'{"item":"article.card","title":"h2","text":".sum","link":"a@href"}'}
            </code>
            . Здесь <code>item</code> это блок одной новости, остальные ищутся внутри него,
            а <code>a@href</code> означает взять атрибут href. Для API:
            <code className="ml-1">{'{"root":"data.items","title":"title","text":"body"}'}</code>.
          </p>
          <p className="text-muted-foreground">
            <b>Города:</b> если привязать источник к городу, все его новости пойдут в этот
            город без проверки ключевых слов. Если не привязывать, ищется совпадение по
            ключевым словам всех городов.
          </p>
          <p className="text-muted-foreground">
            Кнопка проверки запускает опрос сразу. В колонке ошибок наведите курсор, чтобы
            увидеть текст последней ошибки. Подробное описание есть в файле docs/SOURCES.md.
          </p>
        </div>
      )}

      <Modal
        open={!!form}
        onClose={() => setForm(null)}
        title={form?.id ? "Редактировать источник" : "Новый источник"}
        wide
      >
        {form && (
          <div className="space-y-4">
            {error && (
              <p className="rounded-md bg-rose-50 p-2 text-sm text-rose-600 dark:bg-rose-950/40">
                {error}
              </p>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Название" hint="Показывается в списке и подставляется как {source}">
                <input className="input" value={form.name ?? ""} onChange={(e) => upd({ name: e.target.value })} />
              </Field>
              <Field label="Тип" hint="Способ чтения источника">
                <Select value={form.type ?? "rss"} onChange={(v) => upd({ type: v })}>
                  {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </Select>
              </Field>
            </div>
            <Field
              label="URL"
              hint="RSS: ссылка на фид. Telegram: @канал или t.me/канал. Website и HTML: адрес страницы. API: JSON-эндпоинт."
            >
              <input className="input" value={form.url ?? ""} onChange={(e) => upd({ url: e.target.value })} />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Парсер" hint="auto подбирает сам, playwright для JS-сайтов">
                <Select value={form.parser_engine ?? "auto"} onChange={(v) => upd({ parser_engine: v })}>
                  {ENGINES.map((e) => <option key={e} value={e}>{e}</option>)}
                </Select>
              </Field>
              <Field label="Интервал проверки (сек)" hint="Как часто опрашивать, минимум 30">
                <input
                  type="number"
                  className="input"
                  value={form.check_interval_seconds ?? 300}
                  onChange={(e) => upd({ check_interval_seconds: Number(e.target.value) })}
                />
              </Field>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Приоритет" hint="Меньше число значит раньше в очереди">
                <input
                  type="number"
                  className="input"
                  value={form.priority ?? 100}
                  onChange={(e) => upd({ priority: Number(e.target.value) })}
                />
              </Field>
              <Field label="Таймаут (сек)" hint="Максимальное время ожидания ответа">
                <input
                  type="number"
                  className="input"
                  value={form.timeout_seconds ?? 30}
                  onChange={(e) => upd({ timeout_seconds: Number(e.target.value) })}
                />
              </Field>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Прокси" hint="Использовать прокси-сервер для запросов">
                <div className="pt-2">
                  <Checkbox
                    checked={!!form.use_proxy}
                    onChange={(v) => upd({ use_proxy: v })}
                    label="Включить прокси"
                  />
                </div>
              </Field>
              <Field label="URL прокси" hint="http://user:pass@host:port">
                <input className="input" value={form.proxy_url ?? ""} onChange={(e) => upd({ proxy_url: e.target.value })} />
              </Field>
            </div>
            <Field label="Заголовки (JSON)" hint="HTTP-заголовки, например User-Agent">
              <textarea
                className="input min-h-[70px] font-mono text-xs"
                value={JSON.stringify(form.headers ?? {}, null, 2)}
                onChange={(e) => { try { upd({ headers: JSON.parse(e.target.value) }); } catch { /* ignore */ } }}
              />
            </Field>
            <Field label="Cookies (JSON)" hint="Для источников, где нужна авторизация">
              <textarea
                className="input min-h-[60px] font-mono text-xs"
                value={JSON.stringify(form.cookies ?? {}, null, 2)}
                onChange={(e) => { try { upd({ cookies: JSON.parse(e.target.value) }); } catch { /* ignore */ } }}
              />
            </Field>
            <Field label="Auth (JSON)" hint='{"type":"basic","username":"u","password":"p"} или {"type":"bearer","token":"..."}'>
              <textarea
                className="input min-h-[60px] font-mono text-xs"
                value={JSON.stringify(form.auth ?? {}, null, 2)}
                onChange={(e) => { try { upd({ auth: JSON.parse(e.target.value) }); } catch { /* ignore */ } }}
              />
            </Field>
            <Field
              label="Селекторы (JSON)"
              hint='website и html: {"item":".card","title":"h2","text":".sum","link":"a@href"}. API: {"root":"data","title":"title","text":"body"}'
            >
              <textarea
                className="input min-h-[80px] font-mono text-xs"
                value={JSON.stringify(form.selectors ?? {}, null, 2)}
                onChange={(e) => { try { upd({ selectors: JSON.parse(e.target.value) }); } catch { /* ignore */ } }}
              />
            </Field>
            <Checkbox
              checked={form.is_active ?? true}
              onChange={(v) => upd({ is_active: v })}
              label="Активен (опрашивать источник)"
            />
            <div className="flex justify-end border-t border-border pt-4">
              <button className="btn-primary" onClick={save}>Сохранить</button>
            </div>
          </div>
        )}
      </Modal>

      <div className="card overflow-hidden">
        <div className="table-wrap">
          <table className="w-full text-sm">
            <thead className="bg-muted text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3">Название</th>
                <th className="px-4 py-3">Тип</th>
                <th className="px-4 py-3">Интервал</th>
                <th className="px-4 py-3">Ошибки</th>
                <th className="px-4 py-3 text-right">Действия</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((s) => (
                <tr key={s.id} className="border-t border-border">
                  <td className="px-4 py-3">
                    <div className="font-medium">{s.name}</div>
                    <div className="max-w-xs truncate text-xs text-muted-foreground">{s.url}</div>
                  </td>
                  <td className="px-4 py-3">{s.type}</td>
                  <td className="px-4 py-3">{s.check_interval_seconds}s</td>
                  <td className="px-4 py-3">
                    {s.error_count > 0 ? (
                      <span className="text-rose-600" title={s.last_error}>{s.error_count}</span>
                    ) : (
                      "0"
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1.5">
                      <button className="btn-icon" title="Редактировать" onClick={() => openEdit(s)}>
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button className="btn-icon-primary" title="Проверить сейчас" onClick={() => check(s.id)}>
                        <RefreshCw className="h-4 w-4" />
                      </button>
                      <button className="btn-icon-danger" title="Удалить" onClick={() => remove(s.id)}>
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {data && data.items.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-muted-foreground">
                    Источников нет
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {data && (
        <Pagination page={page} size={size} total={data.total} onPage={setPage} onSize={setSize} />
      )}
    </div>
  );
}

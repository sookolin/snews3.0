"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { Page } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";

interface Template {
  id: number; name: string; is_default: boolean; format: string;
  header: string; body: string; footer: string;
}

export default function TemplatesPage() {
  const { data } = useSWR<Page<Template>>("/templates?size=100", fetcher);

  return (
    <div>
      <PageHeader title="Шаблоны" />
      <div className="grid gap-4 md:grid-cols-2">
        {data?.items.map((t) => (
          <div key={t.id} className="card p-5">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="font-medium">{t.name}</h3>
              {t.is_default && <span className="badge bg-emerald-100 text-emerald-700">по умолчанию</span>}
            </div>
            <div className="space-y-1 rounded-md bg-muted p-3 text-xs font-mono">
              <div>{t.header}</div>
              <div className="text-muted-foreground">{t.body}</div>
              <div>{t.footer}</div>
            </div>
            <div className="mt-2 text-xs text-muted-foreground">Формат: {t.format}</div>
          </div>
        ))}
        {data && data.items.length === 0 && (
          <p className="text-muted-foreground">Шаблоны не найдены. Запустите seed для создания шаблона по умолчанию.</p>
        )}
      </div>
    </div>
  );
}

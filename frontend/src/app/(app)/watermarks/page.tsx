"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { Page } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";

interface Watermark {
  id: number; name: string; is_default: boolean; text?: string;
  position: string; opacity: number; scale: number; logo_path?: string;
}

export default function WatermarksPage() {
  const { data } = useSWR<Page<Watermark>>("/watermarks?size=100", fetcher);
  return (
    <div>
      <PageHeader title="Водяной знак" />
      <div className="grid gap-4 md:grid-cols-3">
        {data?.items.map((w) => (
          <div key={w.id} className="card p-5">
            <div className="flex items-center justify-between">
              <h3 className="font-medium">{w.name}</h3>
              {w.is_default && <span className="badge bg-emerald-100 text-emerald-700">default</span>}
            </div>
            <dl className="mt-3 space-y-1 text-sm text-muted-foreground">
              <div>Текст: {w.text || "—"}</div>
              <div>Позиция: {w.position}</div>
              <div>Прозрачность: {Math.round(w.opacity * 100)}%</div>
              <div>Масштаб: {Math.round(w.scale * 100)}%</div>
              <div>Логотип: {w.logo_path ? "загружен" : "нет"}</div>
            </dl>
          </div>
        ))}
      </div>
    </div>
  );
}

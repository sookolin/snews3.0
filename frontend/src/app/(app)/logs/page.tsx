"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { Page } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { ResizableTable } from "@/components/ResizableTable";

interface AuditLog {
  id: number;
  action: string;
  actor?: string;
  entity_type?: string;
  entity_id?: string;
  ip_address?: string;
  created_at: string;
}

export default function LogsPage() {
  const { data } = useSWR<Page<AuditLog>>("/settings/audit/logs?size=100", fetcher);

  return (
    <div>
      <PageHeader title="Логи" />
      <div className="card overflow-hidden">
        <div className="table-wrap">
        <ResizableTable id="logs" columns={["Время", "Действие", "Кто", "Объект", "IP"]}>
            {data?.items.map((l) => (
              <tr key={l.id} className="border-t border-border">
                <td className="px-4 py-3 text-muted-foreground">{new Date(l.created_at).toLocaleString("ru-RU")}</td>
                <td className="px-4 py-3 font-mono text-xs">{l.action}</td>
                <td className="px-4 py-3">{l.actor ?? "—"}</td>
                <td className="px-4 py-3">{l.entity_type ? `${l.entity_type}:${l.entity_id}` : "—"}</td>
                <td className="px-4 py-3 text-muted-foreground">{l.ip_address ?? "—"}</td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-muted-foreground">Записей нет</td></tr>
            )}
        </ResizableTable>
        </div>
      </div>
    </div>
  );
}

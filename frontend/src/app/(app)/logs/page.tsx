"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { Page } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";

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
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-muted-foreground">
            <tr>
              <th className="px-4 py-3">Время</th>
              <th className="px-4 py-3">Действие</th>
              <th className="px-4 py-3">Кто</th>
              <th className="px-4 py-3">Объект</th>
              <th className="px-4 py-3">IP</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((l) => (
              <tr key={l.id} className="border-t border-border">
                <td className="px-4 py-3 text-muted-foreground">{new Date(l.created_at).toLocaleString("ru-RU")}</td>
                <td className="px-4 py-3 font-mono text-xs">{l.action}</td>
                <td className="px-4 py-3">{l.actor ?? "—"}</td>
                <td className="px-4 py-3">{l.entity_type ? `${l.entity_type}:${l.entity_id}` : "—"}</td>
                <td className="px-4 py-3 text-muted-foreground">{l.ip_address ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

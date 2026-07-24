"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import type { Page } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";

interface Channel {
  id: number; city_id: number; title: string; chat_id: string;
  topic_id?: number; publish_mode: string; is_active: boolean;
}

export default function ChannelsPage() {
  const { data } = useSWR<Page<Channel>>("/channels?size=100", fetcher);
  return (
    <div>
      <PageHeader title="Telegram каналы" />
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted text-left text-muted-foreground">
            <tr>
              <th className="px-4 py-3">Название</th>
              <th className="px-4 py-3">Chat ID</th>
              <th className="px-4 py-3">Город</th>
              <th className="px-4 py-3">Режим</th>
              <th className="px-4 py-3">Активен</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((c) => (
              <tr key={c.id} className="border-t border-border">
                <td className="px-4 py-3 font-medium">{c.title}</td>
                <td className="px-4 py-3 font-mono text-xs">{c.chat_id}</td>
                <td className="px-4 py-3">#{c.city_id}</td>
                <td className="px-4 py-3">{c.publish_mode}</td>
                <td className="px-4 py-3">{c.is_active ? "Да" : "Нет"}</td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-muted-foreground">Нет каналов</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { Page } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";

interface AIProfile {
  id: number; name: string; is_default: boolean; provider: string;
  model?: string; temperature: number; max_tokens: number;
}

export default function AIPage() {
  const { data } = useSWR<Page<AIProfile>>("/ai?size=100", fetcher);
  const [text, setText] = useState("В горсовете обсудили ремонт дорог в центре города.");
  const [result, setResult] = useState<{ title: string; text: string; provider: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const test = async () => {
    setError(null); setLoading(true); setResult(null);
    try {
      setResult(await api("/ai/test", { method: "POST", body: JSON.stringify({ text }) }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <PageHeader title="AI" />
      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <div className="mb-3 space-y-3">
            {data?.items.map((p) => (
              <div key={p.id} className="card p-4">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{p.name}</span>
                  {p.is_default && <span className="badge bg-emerald-100 text-emerald-700">default</span>}
                </div>
                <div className="mt-1 text-sm text-muted-foreground">
                  {p.provider} · {p.model || "модель по умолчанию"} · t={p.temperature} · {p.max_tokens} tok
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card space-y-3 p-5">
          <h3 className="font-medium">Тест обработки</h3>
          <textarea className="input min-h-[140px]" value={text} onChange={(e) => setText(e.target.value)} />
          <button className="btn-primary" disabled={loading} onClick={test}>
            {loading ? "Обработка…" : "Запустить"}
          </button>
          {error && <p className="text-sm text-red-600">{error}</p>}
          {result && (
            <div className="rounded-md bg-muted p-3 text-sm">
              <div className="font-semibold">{result.title}</div>
              <div className="mt-1 whitespace-pre-wrap">{result.text}</div>
              <div className="mt-2 text-xs text-muted-foreground">Провайдер: {result.provider}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

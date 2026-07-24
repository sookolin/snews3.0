"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  const load = async () => {
    try {
      setSettings(await api<Record<string, unknown>>("/settings"));
    } catch (e) {
      setError((e as Error).message);
    }
  };
  useEffect(() => { load(); }, []);

  const save = async (key: string, raw: string) => {
    let value: unknown = raw;
    if (raw === "true") value = true;
    else if (raw === "false") value = false;
    else if (raw !== "" && !isNaN(Number(raw))) value = Number(raw);
    try {
      await api(`/settings/${encodeURIComponent(key)}`, {
        method: "PUT",
        body: JSON.stringify({ value }),
      });
      setSaved(key);
      setTimeout(() => setSaved(null), 1500);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="max-w-3xl">
      <PageHeader title="Настройки" />
      {error && <p className="mb-4 text-red-600">{error}</p>}
      <div className="card divide-y divide-border">
        {Object.entries(settings).map(([key, value]) => (
          <div key={key} className="flex items-center gap-4 p-4">
            <div className="flex-1">
              <div className="font-mono text-sm">{key}</div>
            </div>
            <input
              className="input max-w-xs"
              defaultValue={String(value)}
              onBlur={(e) => save(key, e.target.value)}
            />
            {saved === key && <span className="text-sm text-green-600">✓</span>}
          </div>
        ))}
      </div>
      <p className="mt-3 text-sm text-muted-foreground">
        Значения сохраняются автоматически при потере фокуса.
      </p>
    </div>
  );
}

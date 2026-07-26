"use client";

import { useRef, useState } from "react";
import { Upload, Link2, Trash2, EyeOff, Eye } from "lucide-react";
import { api, getToken } from "@/lib/api";

export interface MediaAsset {
  id: number;
  type: string;
  caption?: string;
  is_spoiler: boolean;
  is_enabled: boolean;
  remote_url?: string;
  processed_path?: string;
  file_path?: string;
}

export function mediaUrl(m: MediaAsset): string | undefined {
  if (m.remote_url) return m.remote_url;
  const p = m.processed_path || m.file_path;
  return p ? `/media/${p}` : undefined;
}

interface Props {
  newsId: number;
  media: MediaAsset[];
  onChange: () => void;
}

/** Manage news media: upload from device, add by URL, per-asset spoiler/toggle. */
export function MediaManager({ newsId, media, onChange }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);

  const uploadFiles = async (files: FileList | null) => {
    if (!files || !files.length) return;
    setBusy(true);
    try {
      for (const file of Array.from(files)) {
        const fd = new FormData();
        fd.append("news_id", String(newsId));
        fd.append("file", file);
        await fetch(`/api/v1/media/upload`, {
          method: "POST",
          headers: { Authorization: `Bearer ${getToken()}` },
          body: fd,
        });
      }
      onChange();
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const addUrl = async () => {
    if (!url.trim()) return;
    setBusy(true);
    try {
      await api("/media/from-url", {
        method: "POST",
        body: JSON.stringify({ news_id: newsId, url: url.trim() }),
      });
      setUrl("");
      onChange();
    } finally {
      setBusy(false);
    }
  };

  const patch = async (id: number, body: Record<string, unknown>) => {
    await api(`/media/${id}`, { method: "PATCH", body: JSON.stringify(body) });
    onChange();
  };
  const remove = async (id: number) => {
    await api(`/media/${id}`, { method: "DELETE" });
    onChange();
  };

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2">
        <button className="btn-outline py-1" disabled={busy} onClick={() => fileRef.current?.click()}>
          <Upload className="h-4 w-4" /> С устройства
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/*,video/*"
          multiple
          className="hidden"
          onChange={(e) => uploadFiles(e.target.files)}
        />
        <div className="flex flex-1 gap-2">
          <input className="input" placeholder="или вставьте URL медиа" value={url} onChange={(e) => setUrl(e.target.value)} />
          <button className="btn-outline py-1" disabled={busy} onClick={addUrl}>
            <Link2 className="h-4 w-4" /> Добавить
          </button>
        </div>
      </div>

      {media.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {media.map((m) => {
            const src = mediaUrl(m);
            return (
              <div key={m.id} className={`rounded-md border p-2 ${m.is_enabled ? "border-border" : "border-dashed opacity-50"}`}>
                <div className="relative mb-1 aspect-video overflow-hidden rounded bg-muted">
                  {src && (m.type === "video" ? (
                    <video src={src} className="h-full w-full object-cover" controls />
                  ) : (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={src} alt="" className={`h-full w-full object-cover ${m.is_spoiler ? "blur-md" : ""}`} />
                  ))}
                </div>
                <div className="text-xs text-muted-foreground">{m.type}</div>
                <div className="mt-1 flex flex-wrap gap-1">
                  <button className="btn-outline px-2 py-0.5 text-xs" onClick={() => patch(m.id, { is_enabled: !m.is_enabled })}>
                    {m.is_enabled ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
                  </button>
                  <button
                    className={`px-2 py-0.5 text-xs rounded-md border ${m.is_spoiler ? "bg-primary text-primary-foreground border-primary" : "border-border"}`}
                    onClick={() => patch(m.id, { is_spoiler: !m.is_spoiler })}
                  >
                    Спойлер {m.is_spoiler ? "✓" : ""}
                  </button>
                  <button className="btn-danger px-2 py-0.5 text-xs" onClick={() => remove(m.id)}>
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

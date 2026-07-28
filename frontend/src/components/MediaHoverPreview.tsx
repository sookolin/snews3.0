"use client";

import { useState } from "react";
import { Film, ImageIcon, Paperclip } from "lucide-react";
import type { NewsMedia } from "@/lib/types";

/** Public URL of an attachment (processed file wins so watermarks show). */
function assetUrl(m: NewsMedia): string | undefined {
  if (m.remote_url) return m.remote_url;
  const p = m.processed_path || m.file_path;
  return p ? `/media/${p}` : undefined;
}

/**
 * Compact attachment indicator for table rows: shows the count, and reveals a
 * floating thumbnail strip on hover.
 *
 * The popup is absolutely positioned so it never affects row height — the table
 * layout stays exactly as it is without attachments.
 */
export function MediaHoverPreview({ media }: { media: NewsMedia[] }) {
  const [open, setOpen] = useState(false);
  const items = (media ?? []).filter((m) => m.is_enabled);
  if (items.length === 0) return null;

  const photos = items.filter((m) => m.type === "photo").length;
  const videos = items.length - photos;

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <span
        className="badge gap-1 cursor-default bg-slate-50 text-slate-600 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700"
        title={`Вложений: ${items.length}`}
      >
        {videos > 0 && photos === 0 ? (
          <Film className="h-3 w-3" />
        ) : photos > 0 ? (
          <ImageIcon className="h-3 w-3" />
        ) : (
          <Paperclip className="h-3 w-3" />
        )}
        {items.length}
      </span>

      {open && (
        <span className="absolute left-0 top-full z-30 mt-1 flex w-max max-w-[320px] gap-1.5 rounded-lg border border-border bg-card p-1.5 shadow-lg">
          {items.slice(0, 4).map((m) => {
            const src = assetUrl(m);
            return (
              <span
                key={m.id}
                className="block h-20 w-24 shrink-0 overflow-hidden rounded bg-muted"
              >
                {src ? (
                  m.type === "video" || m.type === "animation" ? (
                    <video
                      src={src}
                      className="h-full w-full object-cover"
                      muted
                      playsInline
                    />
                  ) : (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={src}
                      alt=""
                      className={`h-full w-full object-cover ${m.is_spoiler ? "blur-sm" : ""}`}
                    />
                  )
                ) : (
                  <span className="flex h-full w-full items-center justify-center text-xs text-muted-foreground">
                    {m.type}
                  </span>
                )}
              </span>
            );
          })}
          {items.length > 4 && (
            <span className="flex h-20 w-10 shrink-0 items-center justify-center rounded bg-muted text-xs text-muted-foreground">
              +{items.length - 4}
            </span>
          )}
        </span>
      )}
    </span>
  );
}

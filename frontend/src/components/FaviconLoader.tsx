"use client";

import { useEffect } from "react";
import { getToken } from "@/lib/api";

/**
 * Loads the custom favicon URL from the `site.favicon_url` runtime setting
 * (configured on the Settings page) and swaps the document favicon.
 */
export function FaviconLoader() {
  useEffect(() => {
    if (!getToken()) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/v1/settings", {
          headers: { Authorization: `Bearer ${getToken()}` },
        });
        if (!res.ok) return;
        const data = await res.json();
        const url = data?.["site.favicon_url"];
        if (!cancelled && typeof url === "string" && url.trim()) {
          let link = document.querySelector<HTMLLinkElement>("link[rel='icon']");
          if (!link) {
            link = document.createElement("link");
            link.rel = "icon";
            document.head.appendChild(link);
          }
          link.href = url;
        }
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return null;
}

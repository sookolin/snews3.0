"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";

/** Route → permission required to see/use it. Shared by the sidebar (which
 * tab to show) and the route guard (which URL to block outright). */
export const ROUTE_PERMISSION: Record<string, string> = {
  "/news": "news:view",
  "/compose": "news:edit",
  "/ads": "channel:manage",
  "/sources": "source:view",
  "/cities": "city:view",
  "/channels": "channel:manage",
  "/templates": "template:manage",
  "/watermarks": "watermark:manage",
  "/ai": "ai:manage",
  "/queue": "monitoring:view",
  "/users": "user:view",
  "/logs": "logs:view",
  "/settings": "settings:manage",
};

/** The current, real (non-preview) user's effective permission set. */
export function useMyPermissions(): { permissions: Set<string> | null; isLoading: boolean } {
  const { data, isLoading } = useSWR<string[]>("/auth/permissions", fetcher, {
    revalidateOnFocus: false,
  });
  return { permissions: data ? new Set(data) : null, isLoading };
}

/** Whether the real user may access ``pathname`` at all.
 *
 * Matches by prefix so nested routes (``/news/123``, ``/news/123/edit``)
 * inherit their section's permission — only top-level section keys are
 * listed in ``ROUTE_PERMISSION``. No matching entry = always visible.
 */
export function canAccessRoute(permissions: Set<string> | null, pathname: string): boolean {
  const entry = Object.entries(ROUTE_PERMISSION).find(
    ([base]) => pathname === base || pathname.startsWith(`${base}/`)
  );
  if (!entry) return true;
  const [, need] = entry;
  if (!permissions) return true; // still loading — don't flash a false block
  return permissions.has(need);
}

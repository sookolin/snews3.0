"use client";

import useSWR from "swr";
import { fetcher } from "./api";

/** Fallbacks used before the API responds; mirror `shared.enums.UserRole`. */
export const DEFAULT_ROLE_LABELS: Record<string, string> = {
  super_admin: "Супер-админ",
  admin: "Администратор",
  moderator: "Модератор",
  editor: "Редактор",
  reviewer: "Наблюдатель",
};

export const ROLE_ORDER = ["super_admin", "admin", "moderator", "editor", "reviewer"];

/**
 * Role display names, renamable in Пользователи. Cached by SWR so every page
 * that renders a role tag shares one request.
 */
export function useRoleLabels(): Record<string, string> {
  const { data } = useSWR<Record<string, string>>("/users/role-labels", fetcher, {
    revalidateOnFocus: false,
  });
  return { ...DEFAULT_ROLE_LABELS, ...(data ?? {}) };
}

/**
 * Role colors (hex codes). Cached by SWR.
 */
export function useRoleColors(): Record<string, string> {
  const { data } = useSWR<Record<string, string>>("/users/role-colors", fetcher, {
    revalidateOnFocus: false,
  });
  return data ?? {};
}

const PREVIEW_KEY = "snews.preview_role";

/** Role the site is being previewed as (super admin feature), or null. */
export function getPreviewRole(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(PREVIEW_KEY) || null;
}

export function setPreviewRole(role: string | null) {
  if (typeof window === "undefined") return;
  if (role) window.localStorage.setItem(PREVIEW_KEY, role);
  else window.localStorage.removeItem(PREVIEW_KEY);
  window.dispatchEvent(new Event("snews:preview-role"));
}

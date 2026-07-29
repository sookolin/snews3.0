"use client";

/**
 * Polls GET /profile every 60 s. If the user's role, full_name, is_active, or
 * permissions change (i.e. an admin edited the account), fires a toast so the
 * user knows their session state may have changed.
 */

import { useEffect, useRef } from "react";
import useSWR from "swr";
import { fetcher } from "./api";
import type { Profile } from "./types";
import { useToast } from "@/components/Toast";
import { DEFAULT_ROLE_LABELS } from "./roles";

const POLL_MS = 60_000; // 60 seconds

export function useProfileWatcher() {
  const { data } = useSWR<Profile>("/profile", fetcher, {
    refreshInterval: POLL_MS,
    revalidateOnFocus: false,
  });
  const toast = useToast();

  // Snapshot on first successful load.
  const snapshot = useRef<{
    role: string;
    full_name: string | undefined;
    is_active: boolean;
    permissions: string;
  } | null>(null);

  useEffect(() => {
    if (!data) return;
    const u = data.user;
    const current = {
      role: u.role,
      full_name: u.full_name,
      is_active: u.is_active,
      permissions: JSON.stringify(u.permissions ?? {}),
    };

    // First load — just store snapshot, don't notify.
    if (!snapshot.current) {
      snapshot.current = current;
      return;
    }

    const prev = snapshot.current;
    const changes: string[] = [];

    if (current.role !== prev.role) {
      const from = DEFAULT_ROLE_LABELS[prev.role] ?? prev.role;
      const to = DEFAULT_ROLE_LABELS[current.role] ?? current.role;
      changes.push(`Роль изменена: ${from} → ${to}`);
    }
    if (current.full_name !== prev.full_name) {
      changes.push(`Имя изменено: «${current.full_name ?? "—"}»`);
    }
    if (!current.is_active && prev.is_active) {
      changes.push("Ваш аккаунт деактивирован администратором");
    }
    if (current.permissions !== prev.permissions) {
      changes.push("Ваши права доступа были изменены администратором");
    }

    if (changes.length > 0) {
      snapshot.current = current;
      for (const msg of changes) {
        toast.info(`🔔 ${msg}`);
      }
    }
  }, [data, toast]);
}

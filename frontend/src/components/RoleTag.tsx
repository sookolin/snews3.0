"use client";

import { cn } from "@/lib/utils";
import { useRoleLabels, useRoleColors } from "@/lib/roles";

/**
 * Role labels and colours, ordered by access level: the higher the role, the
 * warmer the colour. Keys mirror `shared.enums.UserRole`.
 */
export const ROLE_META: Record<string, { label: string; short: string; className: string }> = {
  super_admin: {
    label: "Супер-админ",
    short: "SA",
    className:
      "bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-950/50 dark:text-rose-300 dark:ring-rose-900",
  },
  admin: {
    label: "Администратор",
    short: "A",
    className:
      "bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-950/50 dark:text-amber-300 dark:ring-amber-900",
  },
  moderator: {
    label: "Модератор",
    short: "M",
    className:
      "bg-violet-50 text-violet-700 ring-violet-200 dark:bg-violet-950/50 dark:text-violet-300 dark:ring-violet-900",
  },
  editor: {
    label: "Редактор",
    short: "E",
    className:
      "bg-sky-50 text-sky-700 ring-sky-200 dark:bg-sky-950/50 dark:text-sky-300 dark:ring-sky-900",
  },
  reviewer: {
    label: "Наблюдатель",
    short: "R",
    className:
      "bg-slate-50 text-slate-700 ring-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700",
  },
};

export const ROLE_LABELS: Record<string, string> = Object.fromEntries(
  Object.entries(ROLE_META).map(([key, meta]) => [key, meta.label])
);

/**
 * Person tag whose colour encodes the admin's access level, so it is obvious at
 * a glance who handled a news item.
 */
export function RoleTag({ name, role }: { name: string; role?: string }) {
  const labels = useRoleLabels();
  const colors = useRoleColors();
  const base = role ? ROLE_META[role] : undefined;
  // Role names are renamable, so the label comes from the API, not ROLE_META.
  const meta = base && role ? { ...base, label: labels[role] ?? base.label } : undefined;

  // Use dynamic colors from the API if available, otherwise fallback to static classes
  const color = role ? colors[role] : undefined;
  // .badge uses ring-1 ring-inset (box-shadow), not border — so borderColor has
  // no visual effect. Override with an inset box-shadow that matches the ring.
  const dynamicStyle = color
    ? {
        backgroundColor: `${color}22`,
        color: color,
        boxShadow: `0 0 0 1px ${color}55 inset`,
      }
    : undefined;

  return (
    <span
      className={cn(
        "badge whitespace-nowrap",
        // Only apply static className when no dynamic color is available
        !dynamicStyle && (meta?.className ?? "bg-slate-50 text-slate-700 ring-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700")
      )}
      style={dynamicStyle}
      title={meta ? `${name} · ${meta.label}` : name}
    >
      {name}
    </span>
  );
}

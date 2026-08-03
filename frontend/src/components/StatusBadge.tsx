import type { LucideIcon } from "lucide-react";
import {
  AlertTriangle,
  Clock,
  Loader2,
  Pencil,
  Send,
  Timer,
  Undo2,
  XCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * News lifecycle statuses, mirroring `shared.enums.NewsStatus`.
 *
 * processing → pending → approved (cleared, waiting for its publication slot)
 * or scheduled (queued for a set time) → published (live in the channel).
 * withdrawn = was live and taken down (can go out again).
 * rejected / failed are terminal.
 */
const STATUS_META: Record<string, { label: string; icon: LucideIcon; className: string }> = {
  processing: {
    label: "Обработка",
    icon: Loader2,
    className:
      "bg-blue-50 text-blue-700 ring-blue-200 dark:bg-blue-950/50 dark:text-blue-300 dark:ring-blue-900",
  },
  pending: {
    label: "На модерации",
    icon: Clock,
    className:
      "bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-950/50 dark:text-amber-300 dark:ring-amber-900",
  },
  approved: {
    label: "В очереди",
    icon: Timer,
    className:
      "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-300 dark:ring-emerald-900",
  },
  scheduled: {
    label: "Запланирована",
    icon: Timer,
    className:
      "bg-violet-50 text-violet-700 ring-violet-200 dark:bg-violet-950/50 dark:text-violet-300 dark:ring-violet-900",
  },
  published: {
    label: "Опубликована",
    icon: Send,
    className:
      "bg-green-50 text-green-700 ring-green-200 dark:bg-green-950/50 dark:text-green-300 dark:ring-green-900",
  },
  withdrawn: {
    label: "Отозвана",
    icon: Undo2,
    className:
      "bg-orange-50 text-orange-700 ring-orange-200 dark:bg-orange-950/50 dark:text-orange-300 dark:ring-orange-900",
  },
  rejected: {
    label: "Отклонена",
    icon: XCircle,
    className:
      "bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-950/50 dark:text-rose-300 dark:ring-rose-900",
  },
  failed: {
    label: "Ошибка",
    icon: AlertTriangle,
    className:
      "bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-950/50 dark:text-rose-300 dark:ring-rose-900",
  },
};

/** Statuses offered in filter dropdowns, in lifecycle order. */
export const STATUS_ORDER = [
  "processing",
  "pending",
  "approved",
  "scheduled",
  "published",
  "withdrawn",
  "rejected",
  "failed",
];

export const STATUS_LABELS: Record<string, string> = Object.fromEntries(
  Object.entries(STATUS_META).map(([key, meta]) => [key, meta.label])
);

/**
 * Subtle row-background tint per status, matching the status tag's colour but
 * much more transparent so the row is easy to scan without shouting. ``pending``
 * ("на модерации") intentionally has NO tint — it is the neutral default state.
 */
export const STATUS_ROW_TINT: Record<string, string> = {
  processing: "bg-blue-500/5 hover:bg-blue-500/10",
  pending: "",
  approved: "bg-emerald-500/5 hover:bg-emerald-500/10",
  scheduled: "bg-violet-500/5 hover:bg-violet-500/10",
  published: "bg-green-500/10 hover:bg-green-500/15",
  withdrawn: "bg-orange-500/5 hover:bg-orange-500/10",
  rejected: "bg-rose-500/5 hover:bg-rose-500/10",
  failed: "bg-rose-500/10 hover:bg-rose-500/15",
};

/** Compact status pill: coloured icon + label. */
export function StatusBadge({ status }: { status: string }) {
  const meta = STATUS_META[status];
  const Icon = meta?.icon;
  return (
    <span
      className={cn(
        "badge gap-1 whitespace-nowrap",
        meta?.className ?? "bg-slate-50 text-slate-700 ring-slate-200"
      )}
    >
      {Icon && <Icon className="h-3 w-3 shrink-0" />}
      {meta?.label ?? status}
    </span>
  );
}

/**
 * Extra state tag rendered under the status: "изменено" for a published post
 * edited afterwards, "отозвано" for one removed from the channel.
 */
export function StateTag({ kind }: { kind: "edited" | "withdrawn" }) {
  const map = {
    edited: {
      label: "Изменено",
      icon: Pencil,
      className:
        "bg-sky-50 text-sky-700 ring-sky-200 dark:bg-sky-950/50 dark:text-sky-300 dark:ring-sky-900",
    },
    withdrawn: {
      label: "Отозвано",
      icon: Undo2,
      className:
        "bg-orange-50 text-orange-700 ring-orange-200 dark:bg-orange-950/50 dark:text-orange-300 dark:ring-orange-900",
    },
  }[kind];
  const Icon = map.icon;
  return (
    <span className={cn("badge gap-1 whitespace-nowrap", map.className)}>
      <Icon className="h-3 w-3 shrink-0" />
      {map.label}
    </span>
  );
}

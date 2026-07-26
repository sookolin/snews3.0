import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  new: "bg-slate-100 text-slate-700",
  processing: "bg-blue-100 text-blue-700",
  pending: "bg-amber-100 text-amber-800",
  approved: "bg-emerald-100 text-emerald-700",
  rejected: "bg-red-100 text-red-700",
  scheduled: "bg-violet-100 text-violet-700",
  published: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  duplicate: "bg-gray-100 text-gray-600",
};

export const STATUS_LABELS: Record<string, string> = {
  new: "Новая",
  processing: "Обработка",
  pending: "На модерации",
  approved: "Одобрена",
  rejected: "Отклонена",
  scheduled: "Запланирована",
  published: "Опубликована",
  failed: "Ошибка",
  duplicate: "Дубликат",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={cn("badge", STATUS_STYLES[status] ?? "bg-slate-100 text-slate-700")}>
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

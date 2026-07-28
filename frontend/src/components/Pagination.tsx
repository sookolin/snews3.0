"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { Select } from "@/components/Controls";

/** Page-size options offered in every paginated table. */
export const PAGE_SIZES = [20, 50, 100, 200];

interface Props {
  page: number;
  size: number;
  total: number;
  onPage: (page: number) => void;
  onSize: (size: number) => void;
}

/**
 * Table footer with a configurable page size and page stepping.
 * Resets to page 1 whenever the size changes so the offset stays valid.
 */
export function Pagination({ page, size, total, onPage, onSize }: Props) {
  const pages = Math.max(1, Math.ceil(total / size));
  const from = total === 0 ? 0 : (page - 1) * size + 1;
  const to = Math.min(page * size, total);

  return (
    <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm">
      <div className="flex items-center gap-2 text-muted-foreground">
        <span>На странице</span>
        <Select
          className="w-[92px]"
          value={String(size)}
          onChange={(v) => {
            onSize(Number(v));
            onPage(1);
          }}
        >
          {PAGE_SIZES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
        <span>
          {from}–{to} из {total}
        </span>
      </div>

      <div className="flex items-center gap-1.5">
        <button
          className="btn-icon"
          title="Предыдущая страница"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span className="text-muted-foreground">
          {page} / {pages}
        </span>
        <button
          className="btn-icon"
          title="Следующая страница"
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
